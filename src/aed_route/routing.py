from __future__ import annotations

import math
from typing import Any

import networkx as nx
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from .config import (
    BIKE_SPEED_M_S,
    CRS_MAP,
    CRS_PROJECTED,
    MAX_SNAP_DISTANCE_M,
    SHORTLIST_EUCLIDEAN_K,
    TRANSPORT_PROFILES,
    WALK_SPEED_M_S,
)
from .nearest import find_candidate_aed_nodes


_WGS84_TO_PROJECTED = Transformer.from_crs(CRS_MAP, CRS_PROJECTED, always_xy=True)

_COST_ATTR = {"walk": "walk_cost_s", "bike": "bike_cost_s", "car": "drive_cost_s"}
_TIME_ATTR = {"walk": "walk_time_s", "bike": "bike_time_s", "car": "drive_time_s"}
_CAN_ATTR  = {"walk": "can_walk",    "bike": "can_bike",    "car": "can_drive"}

# Velocidad MÁXIMA alcanzable por modo en la red, usada para convertir la
# heurística de A* (distancia en metros) a la misma unidad que su peso
# (segundos) sin perder admisibilidad: cualquier arista real viaja a su
# velocidad real o menos, así que distancia_m / v_max siempre subestima (o
# iguala) el coste real mínimo — h(n) <= h*(n), la condición de
# admisibilidad. Dividir por la velocidad MEDIA, en cambio, sobreestimaría
# el coste de cualquier arista más rápida que la media y rompería esa
# garantía (ver docs/decisions.md, Fase 6, 2026-08-14, para el análisis
# completo de por qué "unificar CRS" por sí solo no basta).
#
# Walk y bike usan las constantes ya definidas en config.py, verificadas
# contra el grafo real antes de este fix (Fase 6, 2026-08-14): walk es
# exactamente 1.7 m/s en el 100% de 1.390.991 aristas can_walk=True medidas
# (min=max=1.7 m/s exacto); bike alcanza 4.5 m/s como máximo real de la red
# (algunas aristas de acceso a AED corren más lento, a 1.7 m/s — pregunta
# abierta de metodología ya registrada en docs/routing_methodology.md, no
# es un problema para esta fórmula: seguir usando el máximo real, 4.5,
# mantiene la heurística admisible también para esas aristas más lentas).
#
# Car NO tiene una velocidad única: varía por tipo de vía (límites de OSM).
# Se mide directamente del grafo cargado (ver _car_max_speed_m_s) en vez de
# inventar una constante, tal como se pidió explícitamente.
_MAX_SPEED_M_S: dict[str, float] = {
    "walk": WALK_SPEED_M_S,
    "bike": BIKE_SPEED_M_S,
}

# Margen de seguridad sobre la admisibilidad, añadido tras la revisión de
# código de la Fase 6 (2026-08-14, ver docs/decisions.md). Verificado
# empíricamente contra el grafo real: la distancia en línea recta calculada
# en coordenadas proyectadas EPSG:25832 puede superar levemente el
# `length_m` que OSMnx calculó para esa misma arista (geodésico sobre el
# elipsoide WGS84) — la proyección UTM introduce una distorsión de escala
# que no es exactamente 1. Medido sobre 20.000 aristas de muestra (y de
# nuevo sobre las 2.022 aristas del exclave de Neuwerk, la zona más alejada
# del meridiano central): sobreestimación máxima real ~0,298%. Sin este
# margen, h(n) podría superar h*(n) por ese margen en casos límite,
# violando admisibilidad estricta. Con este factor (1% de margen, más de 3
# veces el peor caso medido), h(n) queda garantizada por debajo del coste
# real incluso con esa distorsión.
#
# Esta calibración (0.99, el 1%) es ESPECÍFICA de Hamburgo en EPSG:25832
# (UTM zona 32N) — la magnitud de la distorsión de escala depende de cuán
# lejos esté el área cubierta del meridiano central de la proyección (9°E
# para esta zona) y de la zona/proyección UTM en sí. Si este código se
# reutiliza para otra ciudad, otra zona UTM o cualquier otro CRS
# proyectado, este margen NO se puede asumir válido sin repetir la
# medición (ver docs/decisions.md, Fase 7, para el procedimiento usado
# aquí): medir la distancia proyectada recta frente al `length_m`
# geodésico real sobre una muestra representativa de aristas de la nueva
# zona, y fijar el margen a partir del máximo medido allí, no de este
# valor.
_ADMISSIBILITY_SAFETY_MARGIN = 0.99

# Cachés a nivel de módulo, keyed por id(G)/id(nodes_df). El grafo se carga
# una sola vez al arranque de la app y no cambia durante su vida
# (Restricción Global 1: el grafo es inmutable), así que calcular esto una
# vez por bundle es válido y evita trabajo repetido caro en cada petición.
# Se cachea por id() (no de forma incondicional) para que, si alguna vez
# se cargara más de un bundle en el mismo proceso (p. ej. en tests), cada
# uno obtenga su propio valor en vez de reutilizar el de otro grafo — un
# bug real señalado en la revisión de código, no solo cosmético.
_car_max_speed_cache: dict[int, float] = {}
_coord_lookup_cache: dict[int, dict] = {}


def _car_max_speed_m_s(G: nx.MultiDiGraph) -> float:
    """
    Velocidad máxima real medida sobre las aristas can_drive=True del grafo
    cargado (max(length_m / drive_cost_s)). Medida una vez sobre el pickle
    real antes de escribir este fix: min=2.778 m/s, max=33.333 m/s (120
    km/h) sobre 645.996 aristas — el máximo se repite en muchas aristas
    (categoría de vía real, no un valor atípico de datos). Cacheada por
    id(G): recorrer ~646.000 aristas en cada petición de modo "car" sería
    demasiado caro para hacerlo por consulta.
    """
    key = id(G)
    cached = _car_max_speed_cache.get(key)
    if cached is not None:
        return cached

    max_speed = 0.0
    for _u, _v, _k, data in G.edges(keys=True, data=True):
        if data.get("can_drive") is not True:
            continue
        length_m = data.get("length_m")
        cost_s = data.get("drive_cost_s")
        if not length_m or not cost_s or cost_s <= 0:
            continue
        speed = length_m / cost_s
        if speed > max_speed:
            max_speed = speed

    if max_speed <= 0:
        raise ValueError(
            "No se pudo medir una velocidad máxima válida para el modo "
            "'car' en el grafo cargado (¿faltan aristas can_drive=True "
            "con length_m y drive_cost_s positivos?)."
        )

    _car_max_speed_cache[key] = max_speed
    return max_speed


def _max_speed_for_mode(G: nx.MultiDiGraph, mode: str) -> float:
    if mode == "car":
        return _car_max_speed_m_s(G)
    return _MAX_SPEED_M_S[mode]


def _coord_lookup(nodes_df: pd.DataFrame) -> dict:
    """
    Diccionario node_key -> (x, y) en EPSG:25832 (metros), construido desde
    nodes_df — NUNCA desde los atributos x/y del propio grafo
    (`G.nodes[...]`), que para los nodos de carretera regulares siguen en
    grados WGS84 (bug de CRS ya documentado, hallazgo C2). nodes_df, en
    cambio, proyecta TODOS los nodos de forma consistente a metros —tanto
    los de carretera como los `aed_*`— verificado empíricamente contra el
    pickle real antes de escribir este fix (Fase 6, 2026-08-14: 100% de
    657.870 nodos de carretera y 139 nodos AED caen dentro de un rango de
    metros plausible para EPSG:25832 en el norte de Europa; cero valores en
    escala de grados).

    Cacheada a nivel de módulo por `id(nodes_df)`: el bundle se carga una
    sola vez al arranque y se reutiliza en todas las peticiones.
    """
    key = id(nodes_df)
    cached = _coord_lookup_cache.get(key)
    if cached is not None:
        return cached

    lookup = dict(
        zip(
            nodes_df["node_key"].values,
            zip(nodes_df["x"].values, nodes_df["y"].values),
        )
    )
    _coord_lookup_cache[key] = lookup
    return lookup


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

    coord_lookup = _coord_lookup(nodes_df)
    max_speed_m_s = _max_speed_for_mode(G, mode)

    def heuristic(u: str, v: str) -> float:
        # Coordenadas leídas de nodes_df (vía coord_lookup), NUNCA de
        # G.nodes[...] — ver _coord_lookup(). Fallo ruidoso (no un default
        # silencioso a (0,0)) si un nodo del grafo no está en nodes_df: ya
        # se verificó que hoy esa cobertura es del 100% (Fase 6), así que
        # un "miss" aquí solo puede significar una regresión futura real —
        # degradar en silencio a un punto fuera de Hamburgo (0,0) es
        # exactamente el patrón que hizo posible el bug original de esta
        # fase, según señaló la revisión de código.
        try:
            ux, uy = coord_lookup[u]
            vx, vy = coord_lookup[v]
        except KeyError as exc:
            raise KeyError(
                f"Nodo {exc} ausente en nodes_df — la heurística no puede "
                "calcular su distancia. Esto no debería ocurrir (Fase 6 "
                "verificó cobertura del 100%); si ocurre, es una regresión "
                "real en la construcción del grafo o de nodes_df, no un "
                "caso a ignorar en silencio."
            ) from exc
        distance_m = math.hypot(vx - ux, vy - uy)
        # Velocidad MÁXIMA del modo (no la media) + margen de seguridad de
        # admisibilidad (ver _ADMISSIBILITY_SAFETY_MARGIN arriba) para que
        # la heurística quede en la misma unidad que el peso de A*
        # (segundos) sin superar nunca el coste real mínimo.
        return (distance_m * _ADMISSIBILITY_SAFETY_MARGIN) / max_speed_m_s

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
