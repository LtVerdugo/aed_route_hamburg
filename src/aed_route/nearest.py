from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


def build_aed_index(
    aeds_fc: dict,
    nodes_df: pd.DataFrame,
) -> dict:
    """
    Build spatial index over AED nodes already present in the graph.

    AED nodes are identified by node_key starting with 'aed_' and were
    added to the graph at build time via add_aed_nodes_to_graph().
    Properties are matched from aeds_fc by aed_id.

    Parameters
    ----------
    aeds_fc : dict
        GeoJSON FeatureCollection of AED locations.
    nodes_df : pd.DataFrame
        Node table from the graph bundle, including AED nodes
        (node_key, x, y, lon, lat).

    Returns
    -------
    dict with keys:
        aed_nodes       : list[str]   — node_key for each AED node
        aed_coords      : np.ndarray  — (N, 2) x/y in EPSG:25832
        aed_properties  : list[dict]  — original GeoJSON properties per AED
        tree            : cKDTree     — spatial index over aed_coords
    """
    aed_rows = nodes_df[
        nodes_df["node_key"].astype(str).str.startswith("aed_")
    ]

    aed_nodes = aed_rows["node_key"].tolist()
    aed_coords = aed_rows[["x", "y"]].values

    props_by_id = {}
    for feature in (aeds_fc.get("features") or []):
        pid = str(feature.get("properties", {}).get("id", ""))
        props_by_id[pid] = feature.get("properties", {})

    aed_properties = []
    for nk in aed_nodes:
        aed_id = nk.replace("aed_", "", 1)
        props = props_by_id.get(str(aed_id), {"id": aed_id})
        aed_properties.append(props)

    tree = cKDTree(aed_coords)

    return {
        "aed_nodes": aed_nodes,
        "aed_coords": aed_coords,
        "aed_properties": aed_properties,
        "tree": tree,
    }


def build_node_index(nodes_df: pd.DataFrame) -> dict:
    """
    Build a spatial index over all graph nodes for fast origin snapping.

    Call this once at app startup and pass the result to
    snap_origin_to_graph via the node_index parameter to avoid
    rebuilding the cKDTree on every query.

    Parameters
    ----------
    nodes_df : pd.DataFrame
        Node table from the graph bundle (columns: node_key, x, y).

    Returns
    -------
    dict with keys:
        tree       : cKDTree     — spatial index over node coordinates
        node_keys  : np.ndarray  — node_key string for each node
        coords     : np.ndarray  — (N, 2) x/y coordinates in EPSG:25832
    """
    coords = nodes_df[["x", "y"]].values
    node_keys = nodes_df["node_key"].values
    return {
        "tree": cKDTree(coords),
        "node_keys": node_keys,
        "coords": coords,
    }


def find_candidate_aed_nodes(
    origin_xy: tuple[float, float],
    aed_index: dict,
    k: int,
) -> list[dict]:
    """
    Return the K nearest AEDs to the origin by Euclidean distance.

    Uses the prebuilt cKDTree from aed_index for an O(log n) lookup.

    Parameters
    ----------
    origin_xy : tuple[float, float]
        Origin coordinates (x, y) in EPSG:25832.
    aed_index : dict
        Output of build_aed_index.
    k : int
        Number of candidates to return.

    Returns
    -------
    list[dict] ordered by euclidean_distance_m ascending, each with:
        node_key             : str
        euclidean_distance_m : float
        aed_properties       : dict
    """
    k_actual = min(k, len(aed_index["aed_nodes"]))
    distances, indices = aed_index["tree"].query(
        [origin_xy[0], origin_xy[1]], k=k_actual
    )

    # query returns scalars when k=1; normalise to arrays
    distances = np.atleast_1d(distances)
    indices = np.atleast_1d(indices)

    return [
        {
            "node_key": aed_index["aed_nodes"][idx],
            "euclidean_distance_m": float(dist),
            "aed_properties": aed_index["aed_properties"][idx],
        }
        for dist, idx in zip(distances, indices)
    ]
