from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox
from shapely.geometry import mapping
from shapely.ops import transform
import pyproj

from .config import (
    ISOCHRONE_TIMES_S,
    ISOCHRONE_CACHE_REL_PATH,
)

logger = logging.getLogger(__name__)

_TO_WGS84 = pyproj.Transformer.from_crs(
    "EPSG:25832", "EPSG:4326", always_xy=True
)


def compute_isochrones(
    G: nx.MultiDiGraph,
    aeds_fc: dict,
    project_root: Path,
    force_rebuild: bool = False,
) -> dict[str, Any]:
    """
    Compute walk isochrones for each AED and cache as GeoJSON.

    For each AED node and each time threshold in ISOCHRONE_TIMES_S,
    finds all reachable edges within that travel time using Dijkstra
    (nx.ego_graph with walk_cost_s as weight), converts them to a
    GeoDataFrame, projects to EPSG:25832, buffers each edge by 25 m,
    and unions all buffers to produce an isochrone that follows the
    street network geometry.

    Returns a GeoJSON FeatureCollection where each feature is one
    isochrone polygon with properties:
        aed_id   : str
        time_s   : int  (120 or 240)
        minutes  : int  (2 or 4)
    """
    out_path = project_root / ISOCHRONE_CACHE_REL_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not force_rebuild:
        logger.info("Loading isochrones from cache: %s", out_path)
        with out_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    logger.info(
        "Computing isochrones for %d AEDs...",
        len(aeds_fc.get("features", [])),
    )

    # Walk subgraph — filter to walk-accessible edges only
    G_walk = nx.subgraph_view(
        G,
        filter_edge=lambda u, v, k: G[u][v][k].get("can_walk") is True,
    )

    # Build undirected view once — ego_graph(undirected=True) rebuilds
    # this on every call which is O(N+E) per AED and too slow at scale.
    G_walk_undirected = G_walk.to_undirected(as_view=True)

    features = []
    aed_nodes = [n for n in G.nodes() if str(n).startswith("aed_")]

    for i, aed_node in enumerate(aed_nodes):
        aed_id = str(aed_node).replace("aed_", "")
        aed_data = G.nodes[aed_node]

        if aed_data.get("x") is None:
            continue

        for time_s in ISOCHRONE_TIMES_S:
            try:
                # Find all nodes reachable within time_s seconds.
                # Use the pre-built undirected graph directly to avoid
                # rebuilding it on every ego_graph call.
                subgraph = nx.ego_graph(
                    G_walk_undirected,
                    aed_node,
                    radius=time_s,
                    distance="walk_cost_s",
                )
            except nx.NodeNotFound:
                continue

            # Convert subgraph edges to GeoDataFrame
            # Project to EPSG:25832 for accurate metric buffering
            try:
                edges_gdf = ox.graph_to_gdfs(
                    subgraph.to_directed(),
                    nodes=False,
                    edges=True,
                )
            except Exception:
                continue

            if edges_gdf.empty:
                continue

            # Project to metric CRS for accurate buffer in metres
            edges_projected = edges_gdf.to_crs("EPSG:25832")

            # Buffer each edge by 25 metres and union all
            # This produces an isochrone that follows the street network
            polygon = edges_projected.geometry.buffer(25).union_all()

            # Simplify slightly to reduce polygon complexity
            polygon = polygon.simplify(5)

            # Convert to EPSG:4326 for GeoJSON
            polygon_wgs84 = transform(_TO_WGS84.transform, polygon)

            features.append({
                "type": "Feature",
                "geometry": mapping(polygon_wgs84),
                "properties": {
                    "aed_id": aed_id,
                    "time_s": time_s,
                    "minutes": time_s // 60,
                },
            })

        if i % 20 == 0:
            logger.info("Processed %d / %d AEDs", i + 1, len(aed_nodes))

    fc = {"type": "FeatureCollection", "features": features}

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)

    logger.info(
        "Isochrones saved: %d features → %s", len(features), out_path
    )
    return fc
