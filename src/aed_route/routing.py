from __future__ import annotations

import math
from typing import Any

import networkx as nx
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from .config import (
    CRS_MAP,
    CRS_PROJECTED,
    MAX_SNAP_DISTANCE_M,
    SHORTLIST_EUCLIDEAN_K,
    TRANSPORT_PROFILES,
)
from .nearest import find_candidate_aed_nodes


_WGS84_TO_PROJECTED = Transformer.from_crs(CRS_MAP, CRS_PROJECTED, always_xy=True)

_COST_ATTR = {"walk": "walk_cost_s", "bike": "bike_cost_s", "car": "drive_cost_s"}
_TIME_ATTR = {"walk": "walk_time_s", "bike": "bike_time_s", "car": "drive_time_s"}
_CAN_ATTR  = {"walk": "can_walk",    "bike": "can_bike",    "car": "can_drive"}


def snap_origin_to_graph(
    origin_lon: float,
    origin_lat: float,
    nodes_df: pd.DataFrame,
    node_index: dict | None = None,
) -> dict | None:
    """
    Snap a WGS84 origin point to the nearest graph node.

    Projects the origin to EPSG:25832 and finds the nearest node using
    cKDTree. Returns None if the nearest node exceeds MAX_SNAP_DISTANCE_M.

    Parameters
    ----------
    origin_lon : float
        Origin longitude in WGS84.
    origin_lat : float
        Origin latitude in WGS84.
    nodes_df : pd.DataFrame
        Node table from the graph bundle (columns: node_key, x, y).
        Used only when node_index is None.
    node_index : dict | None
        Prebuilt index from build_node_index (nearest.py). If provided,
        its cKDTree is reused directly. If None, a tree is built from
        nodes_df on every call (fallback for tests and one-off use).

    Returns
    -------
    dict with keys node_key, x, y, snap_distance_m, or None if the
    nearest node exceeds MAX_SNAP_DISTANCE_M.
    """
    x, y = _WGS84_TO_PROJECTED.transform(origin_lon, origin_lat)

    if node_index is not None:
        tree = node_index["tree"]
        node_keys = node_index["node_keys"]
        node_coords = node_index["coords"]
    else:
        node_coords = nodes_df[["x", "y"]].values
        node_keys = nodes_df["node_key"].values
        tree = cKDTree(node_coords)

    dist, idx = tree.query([x, y], k=1)

    dist = float(dist)
    idx = int(idx)

    if dist > MAX_SNAP_DISTANCE_M:
        return None

    return {
        "node_key": node_keys[idx],
        "x": float(node_coords[idx, 0]),
        "y": float(node_coords[idx, 1]),
        "snap_distance_m": dist,
    }


def find_nearest_aeds(
    origin_lon: float,
    origin_lat: float,
    mode: str,
    graph_bundle: dict[str, Any],
    aed_index: dict,
    k: int = SHORTLIST_EUCLIDEAN_K,
    node_index: dict | None = None,
) -> list[dict]:
    """
    Find the nearest AEDs from an origin point by network distance.

    Stage 1: snaps the origin to the graph.
    Stage 2: prefilters K AED candidates by Euclidean distance.
    Stage 3: runs A* from the origin to each candidate on a mode-filtered
             subgraph view. Results are ordered by total routing cost.

    Parameters
    ----------
    origin_lon : float
        Origin longitude in WGS84.
    origin_lat : float
        Origin latitude in WGS84.
    mode : str
        Transport profile: "walk", "bike", or "car".
    graph_bundle : dict
        Bundle from load_or_build_graph_bundle (keys: graph, nodes_df).
    aed_index : dict
        Output of build_aed_index from nearest.py.
    k : int
        Number of Euclidean candidates to evaluate with A*.
    node_index : dict | None
        Prebuilt index from build_node_index (nearest.py). Pass this at
        app startup to avoid rebuilding the cKDTree on every query.

    Returns
    -------
    list[dict] ordered by total_cost_s ascending (rank 1 = network nearest).
    Each dict contains:
        rank                 : int
        aed_properties       : dict
        euclidean_distance_m : float
        total_cost_s         : float
        total_time_s         : float
        total_length_m       : float
        path_nodes           : list[str]
        path_edges           : list[dict]
    """
    if mode not in TRANSPORT_PROFILES:
        raise ValueError(
            f"Invalid mode '{mode}'. Must be one of {TRANSPORT_PROFILES}."
        )

    G: nx.MultiDiGraph = graph_bundle["graph"]
    nodes_df: pd.DataFrame = graph_bundle["nodes_df"]

    origin = snap_origin_to_graph(origin_lon, origin_lat, nodes_df, node_index)
    if origin is None:
        return []

    origin_node = origin["node_key"]
    origin_xy = (origin["x"], origin["y"])

    candidates = find_candidate_aed_nodes(origin_xy, aed_index, k)

    can_attr  = _CAN_ATTR[mode]
    cost_attr = _COST_ATTR[mode]
    time_attr = _TIME_ATTR[mode]

    G_mode = nx.subgraph_view(
        G,
        filter_edge=lambda u, v, ek: G[u][v][ek].get(can_attr) is True,
    )

    def heuristic(u: str, v: str) -> float:
        ux = G_mode.nodes[u].get("x", 0.0)
        uy = G_mode.nodes[u].get("y", 0.0)
        vx = G_mode.nodes[v].get("x", 0.0)
        vy = G_mode.nodes[v].get("y", 0.0)
        return math.hypot(vx - ux, vy - uy)

    results = []

    for candidate in candidates:
        target_node = candidate["node_key"]
        if target_node == origin_node:
            continue

        try:
            path_nodes = nx.astar_path(
                G_mode,
                origin_node,
                target_node,
                heuristic=heuristic,
                weight=cost_attr,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

        total_cost_s = 0.0
        total_time_s = 0.0
        total_length_m = 0.0
        path_edges = []

        for u, v in zip(path_nodes[:-1], path_nodes[1:]):
            edges_uv = G_mode[u][v]  # dict of {key: attr_dict}
            best_key = min(
                edges_uv,
                key=lambda ek: edges_uv[ek].get(cost_attr, float("inf")),
            )
            edge_data = dict(edges_uv[best_key])
            total_cost_s   += edge_data.get(cost_attr)  or 0.0
            total_time_s   += edge_data.get(time_attr)  or 0.0
            total_length_m += edge_data.get("length_m") or 0.0

            path_edges.append({
                "highway":    edge_data.get("highway"),
                "name":       edge_data.get("name"),
                "length_m":   edge_data.get("length_m"),
                "cost_s":     edge_data.get(cost_attr),
                "time_s":     edge_data.get(time_attr),
                "geometry":   edge_data.get("geometry"),
            })

        # Copy to avoid mutating the shared aed_index data
        aed_props = dict(candidate["aed_properties"])

        # Read real AED coordinates directly from the graph node attributes.
        # AED nodes are permanent graph nodes with lon/lat set at build time.
        aed_node_attrs = G_mode.nodes.get(candidate["node_key"], {})
        aed_props["lat"] = aed_node_attrs.get("lat")
        aed_props["lon"] = aed_node_attrs.get("lon")

        results.append({
            "rank":                 0,  # assigned after sorting
            "aed_properties":       aed_props,
            "euclidean_distance_m": candidate["euclidean_distance_m"],
            "total_cost_s":         total_cost_s,
            "total_time_s":         total_time_s,
            "total_length_m":       total_length_m,
            "path_nodes":           path_nodes,
            "path_edges":           path_edges,
        })

    results.sort(key=lambda r: r["total_cost_s"])
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results
