from __future__ import annotations

import pickle
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import LineString, mapping

from .config import (
    CRS_MAP,
    CRS_PROJECTED,
    GRAPH_CACHE_REL_PATH,
    MAX_SNAP_DISTANCE_M,
    WALK_SPEED_M_S,
    BIKE_SPEED_M_S,
)
from .boundary import load_or_build_boundary_geojson

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GraphBuildReport:
    used_cache: bool
    out_path: str
    n_nodes: int
    n_edges: int


_TO_PROJ = Transformer.from_crs(CRS_MAP, CRS_PROJECTED, always_xy=True)


def load_or_build_graph_bundle(
    *,
    project_root: Path,
    graph_rel_path: Path = GRAPH_CACHE_REL_PATH,
    force_rebuild: bool = False,
    aeds_fc: dict | None = None,
) -> tuple[dict[str, Any], GraphBuildReport]:
    """
    Load the unified OSMnx graph bundle from cache or build it.
    """
    out_path = project_root / graph_rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not force_rebuild:
        bundle = _load_bundle(out_path)
        if "graph" in bundle:
            return bundle, _make_report(bundle, True, out_path)

    logger.info("Building graph from OSMnx...")
    boundary_fc, _ = load_or_build_boundary_geojson(
        project_root=project_root,
        force_rebuild=False,
    )

    G = build_unified_graph_osmnx(boundary_fc)

    nodes_df = _build_nodes_df(G)

    bundle = {
        "graph": G,
        "nodes_df": nodes_df,
        "metadata": {"source": "osmnx"},
    }

    if aeds_fc is not None:
        bundle["graph"] = add_aed_nodes_to_graph(
            G=bundle["graph"],
            aeds_fc=aeds_fc,
            nodes_df=bundle["nodes_df"],
        )
        aed_rows = [
            {
                "node_key": nk,
                "lon": d.get("lon"),
                "lat": d.get("lat"),
                "x": d.get("x"),
                "y": d.get("y"),
            }
            for nk, d in bundle["graph"].nodes(data=True)
            if str(nk).startswith("aed_")
        ]
        if aed_rows:
            bundle["nodes_df"] = pd.concat(
                [bundle["nodes_df"], pd.DataFrame(aed_rows)],
                ignore_index=True,
            )

    _save_bundle(bundle, out_path)
    return bundle, _make_report(bundle, False, out_path)


def build_unified_graph_osmnx(boundary_fc: dict) -> nx.MultiDiGraph:
    """
    Build a unified multimodal graph from OSMnx using the Hamburg boundary.

    Downloads walk, bike and car networks separately, then merges them
    into a single MultiDiGraph where each edge carries can_walk, can_bike,
    can_drive flags and mode-specific travel times.

    Directionality decisions:
    - Walk: 100% bidirectional (OSMnx default)
    - Bike: 100% bidirectional by design (emergency context)
    - Car: respects oneway (OSMnx default)
    """
    from shapely.geometry import shape

    feature = boundary_fc["features"][0]
    polygon = shape(feature["geometry"])

    # Walk custom filter for emergency context:
    # Includes cycleways and *_link roads which OSMnx
    # network_type="walk" excludes by default.
    # In an emergency, a person will cross any infrastructure
    # to reach an AED. Only motorway/trunk excluded due to
    # physical danger at high speeds.
    WALK_CUSTOM_FILTER = (
        '["highway"~"motorway_link|trunk_link|primary|primary_link|'
        'secondary|secondary_link|tertiary|tertiary_link|'
        'unclassified|residential|service|living_street|'
        'pedestrian|footway|path|cycleway|track|steps|road"]'
        '["access"!~"no|private"]'
    )

    logger.info("Downloading walk network (custom filter)...")
    G_walk = ox.graph_from_polygon(
        polygon,
        custom_filter=WALK_CUSTOM_FILTER,
        retain_all=True,
        simplify=False,
    )
    G_walk = ox.add_edge_speeds(G_walk)
    G_walk = ox.add_edge_travel_times(G_walk)

    # Bike custom filter for emergency context:
    # Includes pedestrian zones and footways which OSMnx
    # network_type="bike" excludes by default.
    # In an emergency, a cyclist will use any available
    # infrastructure. Only motorway/trunk excluded.
    BIKE_CUSTOM_FILTER = (
        '["highway"~"primary|primary_link|'
        'secondary|secondary_link|tertiary|tertiary_link|'
        'unclassified|residential|service|living_street|'
        'pedestrian|footway|path|cycleway|track|road"]'
        '["access"!~"no|private"]'
    )

    logger.info("Downloading bike network (custom filter)...")
    G_bike = ox.graph_from_polygon(
        polygon,
        custom_filter=BIKE_CUSTOM_FILTER,
        retain_all=True,
        simplify=False,
    )
    G_bike = ox.add_edge_speeds(G_bike)
    G_bike = ox.add_edge_travel_times(G_bike)

    # Custom filter for drive network in emergency context.
    # OSMnx network_type="drive" excludes service and track roads
    # by default. In an emergency context, a vehicle may need to
    # use service roads (e.g. hospital car parks, private access
    # roads) and tracks. We override the default filter to include
    # these highway classes explicitly.
    DRIVE_CUSTOM_FILTER = (
        '["highway"~"motorway|motorway_link|trunk|trunk_link|'
        'primary|primary_link|secondary|secondary_link|'
        'tertiary|tertiary_link|unclassified|residential|'
        'living_street|service|track|road"]'
        '["access"!~"no|private"]'
    )

    logger.info("Downloading drive network (custom filter)...")
    G_drive = ox.graph_from_polygon(
        polygon,
        custom_filter=DRIVE_CUSTOM_FILTER,
        retain_all=True,
        simplify=False,
    )
    G_drive = ox.add_edge_speeds(G_drive)
    G_drive = ox.add_edge_travel_times(G_drive)

    logger.info("Making bike graph fully bidirectional...")
    # In emergency context cyclists ignore oneway restrictions
    G_bike = _make_bidirectional(G_bike)

    logger.info("Merging into unified graph...")
    G_unified = _merge_graphs(G_walk, G_bike, G_drive)

    logger.info(
        "Unified graph: %d nodes, %d edges",
        G_unified.number_of_nodes(),
        G_unified.number_of_edges(),
    )
    return G_unified


def _make_bidirectional(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """
    Make all edges bidirectional by adding reverse edges where missing.
    Used for bike graph in emergency context.
    """
    edges_to_add = []
    for u, v, k, data in G.edges(keys=True, data=True):
        if not G.has_edge(v, u):
            reverse_data = dict(data)
            reverse_data["reversed"] = True
            geom = reverse_data.get("geometry")
            if geom is not None:
                try:
                    reverse_data["geometry"] = LineString(
                        list(geom.coords)[::-1]
                    )
                except Exception:
                    pass
            edges_to_add.append((v, u, k, reverse_data))

    for v, u, k, data in edges_to_add:
        G.add_edge(v, u, key=k, **data)

    return G


def _merge_graphs(
    G_walk: nx.MultiDiGraph,
    G_bike: nx.MultiDiGraph,
    G_drive: nx.MultiDiGraph,
) -> nx.MultiDiGraph:
    """
    Merge three modal graphs into a single unified MultiDiGraph.

    Each edge in the unified graph carries:
    - can_walk, can_bike, can_drive flags
    - walk_cost_s, bike_cost_s, drive_cost_s
    - walk_time_s, bike_time_s, drive_time_s
    - geometry, highway, name, length_m
    """
    # Build sets of (u, v) pairs per mode — use sets to avoid duplicates
    # For MultiDiGraph we use (u,v) pairs, not (u,v,k)
    # because we want one unified edge per physical direction
    walk_pairs  = {(u, v): d for u, v, k, d
                   in G_walk.edges(keys=True, data=True)}
    bike_pairs  = {(u, v): d for u, v, k, d
                   in G_bike.edges(keys=True, data=True)}
    drive_pairs = {(u, v): d for u, v, k, d
                   in G_drive.edges(keys=True, data=True)}

    all_edge_pairs = (
        set(walk_pairs.keys()) |
        set(bike_pairs.keys()) |
        set(drive_pairs.keys())
    )

    # Collect all nodes from all three graphs
    all_nodes = {}
    for G in [G_walk, G_bike, G_drive]:
        for node, data in G.nodes(data=True):
            if node not in all_nodes:
                all_nodes[node] = data

    G_unified = nx.MultiDiGraph()
    G_unified.graph["crs"] = "EPSG:4326"

    for node, data in all_nodes.items():
        G_unified.add_node(node, **data)

    for (u, v) in all_edge_pairs:
        w_data  = walk_pairs.get((u, v), {})
        b_data  = bike_pairs.get((u, v), {})
        d_data  = drive_pairs.get((u, v), {})

        can_walk  = bool(w_data)
        can_bike  = bool(b_data)
        can_drive = bool(d_data)

        base = w_data or b_data or d_data
        length_m = float(base.get("length", 0.0))

        # Reconstruct geometry from node coordinates if missing.
        # OSMnx only stores geometry for curved edges.
        # Straight edges have no geometry key — we rebuild it
        # from the node x/y attributes stored in the graph nodes.
        geom = base.get("geometry")
        if geom is None:
            u_data = (
                G_walk.nodes.get(u) or
                G_bike.nodes.get(u) or
                G_drive.nodes.get(u) or {}
            )
            v_data = (
                G_walk.nodes.get(v) or
                G_bike.nodes.get(v) or
                G_drive.nodes.get(v) or {}
            )
            u_x = u_data.get("x")
            u_y = u_data.get("y")
            v_x = v_data.get("x")
            v_y = v_data.get("y")
            if (u_x is not None and u_y is not None and
                    v_x is not None and v_y is not None):
                geom = LineString([(u_x, u_y), (v_x, v_y)])

        # Walk and bike: always use our constants from config.
        # OSMnx travel_time is computed from road speed tags
        # and is not valid for pedestrian or cycling speeds.
        # Car: use OSMnx travel_time which is based on maxspeed.
        walk_time_s = (
            length_m / WALK_SPEED_M_S if can_walk else None
        )
        bike_time_s = (
            length_m / BIKE_SPEED_M_S if can_bike else None
        )
        drive_time_s = (
            float(d_data.get("travel_time") or 0)
            if can_drive else None
        )
        if can_drive and not drive_time_s:
            speed_mps = float(
                d_data.get("speed_kph", 30.0)
            ) / 3.6
            drive_time_s = (
                length_m / speed_mps if speed_mps > 0 else None
            )

        G_unified.add_edge(
            u, v,
            key=0,
            can_walk=can_walk,
            can_bike=can_bike,
            can_drive=can_drive,
            walk_cost_s=walk_time_s,
            bike_cost_s=bike_time_s,
            drive_cost_s=drive_time_s,
            walk_time_s=walk_time_s,
            bike_time_s=bike_time_s,
            drive_time_s=drive_time_s,
            length_m=length_m,
            highway=base.get("highway"),
            name=base.get("name"),
            geometry=geom,
            osmid=base.get("osmid"),
        )

    return G_unified


def _build_nodes_df(G: nx.MultiDiGraph) -> pd.DataFrame:
    """
    Build a node DataFrame from the unified graph.
    OSMnx nodes have integer IDs and x/y in WGS84.
    """
    rows = []
    for node, data in G.nodes(data=True):
        lon = data.get("x")
        lat = data.get("y")
        if lon is None or lat is None:
            continue
        x, y = _TO_PROJ.transform(float(lon), float(lat))
        rows.append({
            "node_key": node,
            "lon": float(lon),
            "lat": float(lat),
            "x": float(x),
            "y": float(y),
        })
    return pd.DataFrame(rows)


def add_aed_nodes_to_graph(
    G: nx.MultiDiGraph,
    aeds_fc: dict,
    nodes_df: pd.DataFrame,
) -> nx.MultiDiGraph:
    """
    Add AED locations as permanent nodes in the unified graph.
    AED nodes use string keys: "aed_{osm_id}".
    Road nodes use integer OSM IDs.
    """
    road_mask = nodes_df["node_key"].apply(
        lambda k: not str(k).startswith("aed_")
    )
    node_coords = nodes_df[road_mask][["x", "y"]].values
    node_keys_road = nodes_df[road_mask]["node_key"].values

    tree = cKDTree(node_coords)

    features = aeds_fc.get("features", []) or []
    added = 0
    skipped = 0

    for feature in features:
        geom = feature.get("geometry") or {}
        props = feature.get("properties") or {}

        if geom.get("type") != "Point":
            continue

        lon, lat = geom["coordinates"]
        aed_id = props.get("id", f"aed_{added}")
        node_key = f"aed_{aed_id}"

        x, y = _TO_PROJ.transform(float(lon), float(lat))
        dist_m, idx = tree.query([x, y], k=1)

        if dist_m > MAX_SNAP_DISTANCE_M:
            skipped += 1
            continue

        nearest_node_key = node_keys_road[idx]
        nearest_row = nodes_df[
            nodes_df["node_key"] == nearest_node_key
        ].iloc[0]
        nearest_lon = float(nearest_row["lon"])
        nearest_lat = float(nearest_row["lat"])

        access_time_s = float(dist_m) / WALK_SPEED_M_S

        G.add_node(
            node_key,
            node_key=node_key,
            lon=float(lon),
            lat=float(lat),
            x=float(x),
            y=float(y),
            node_type="aed",
            aed_id=aed_id,
        )

        base_attrs = {
            "highway": "aed_access",
            "name": None,
            "length_m": float(dist_m),
            "can_walk": True,
            "can_bike": True,
            "can_drive": False,
            "walk_cost_s": access_time_s,
            "bike_cost_s": access_time_s,
            "drive_cost_s": None,
            "walk_time_s": access_time_s,
            "bike_time_s": access_time_s,
            "drive_time_s": None,
        }

        G.add_edge(
            node_key,
            nearest_node_key,
            key=0,
            **base_attrs,
            geometry=LineString([(lon, lat), (nearest_lon, nearest_lat)]),
        )
        G.add_edge(
            nearest_node_key,
            node_key,
            key=0,
            **base_attrs,
            geometry=LineString([(nearest_lon, nearest_lat), (lon, lat)]),
        )

        added += 1

    logger.info("AED nodes added: %d, skipped: %d", added, skipped)
    return G


def _save_bundle(bundle: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        pickle.dump(bundle, f, protocol=pickle.HIGHEST_PROTOCOL)


def _load_bundle(out_path: Path) -> dict:
    with out_path.open("rb") as f:
        return pickle.load(f)


def _make_report(
    bundle: dict, used_cache: bool, out_path: Path
) -> GraphBuildReport:
    G = bundle["graph"]
    return GraphBuildReport(
        used_cache=used_cache,
        out_path=str(out_path),
        n_nodes=G.number_of_nodes(),
        n_edges=G.number_of_edges(),
    )
