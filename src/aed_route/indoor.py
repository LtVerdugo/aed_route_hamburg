from __future__ import annotations

import json
import logging
import math
import pickle
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .config import (
    CRS_MAP,
    CRS_PROJECTED,
    WALK_SPEED_M_S,
    STAIR_SECONDS_PER_LEVEL,
    ESCALATOR_SECONDS_PER_LEVEL,
    ELEVATOR_SECONDS_PER_LEVEL,
    ELEVATOR_WAIT_SECONDS,
    INDOOR_IGNORE_LEVELS,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ISOLATED_JSON_REL_PATH = Path("data/interim/hbf_indoor_isolated.json")
INDOOR_GRAPH_REL_PATH = Path("data/interim/hbf_indoor_graph.pkl")

WINNER_AED_ID = 13948102741

_TO_PROJ = Transformer.from_crs(CRS_MAP, CRS_PROJECTED, always_xy=True)
_IGNORE_LEVELS = set(INDOOR_IGNORE_LEVELS)

_VERTICAL_COST_PER_LEVEL = {
    "steps": STAIR_SECONDS_PER_LEVEL,
    "conveying": ESCALATOR_SECONDS_PER_LEVEL,
    "elevator": ELEVATOR_SECONDS_PER_LEVEL,
}

_INT_RE = re.compile(r"^-?\d+$")
_DECIMAL_RE = re.compile(r"^-?\d+\.\d+$")
_RANGE_RE = re.compile(r"^(-?\d+)-(-?\d+)$")


# ── Parser de niveles ──────────────────────────────────────────────────


def parse_level(raw: Any) -> list[float]:
    """
    Parse an OSM `level` tag value into a list of floats.

    Handles the real cases seen in Hbf (integers, ';'-separated lists,
    decimals like "-0.5") plus '-' ranges for robustness, even though
    ranges did not appear in the Hbf dataset. Never raises: any
    unparseable value is logged as a warning and contributes nothing
    (empty list). Does NOT read the `layer` tag — that is a different
    OSM concept (rendering/stacking order, not a physical floor).
    """
    if raw is None:
        return []

    text = str(raw).strip()
    if not text:
        return []

    if ";" in text:
        result: list[float] = []
        for part in text.split(";"):
            result.extend(parse_level(part))
        return result

    # Plain integer or decimal FIRST — this is what distinguishes a
    # negative sign ("-1" is an integer) from a range separator
    # ("-1--1" or "0-2" are ranges) below.
    if _INT_RE.fullmatch(text):
        return [float(text)]

    if _DECIMAL_RE.fullmatch(text):
        return [float(text)]

    m = _RANGE_RE.fullmatch(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return [float(x) for x in range(lo, hi + 1)]

    logger.warning("parse_level: valor no parseable, ignorado: %r", raw)
    return []


def _levels_for_tags(tags: dict) -> list[float]:
    """Parsed, filtered (INDOOR_IGNORE_LEVELS removed) level list for an element's tags."""
    levels = parse_level(tags.get("level"))
    return [lv for lv in levels if lv not in _IGNORE_LEVELS]


def _node_key(osmid: int, level: float) -> str:
    return f"in_{osmid}_L{level:g}"


# ── Carga del dataset aislado ───────────────────────────────────────────


def _load_isolated(path: Path) -> tuple[dict[int, dict], dict[int, dict], dict[int, dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    elements = data.get("elements") or []

    nodes: dict[int, dict] = {}
    ways: dict[int, dict] = {}
    relations: dict[int, dict] = {}

    for el in elements:
        t = el.get("type")
        eid = el.get("id")
        if t == "node":
            nodes[eid] = el
        elif t == "way":
            ways[eid] = el
        elif t == "relation":
            relations[eid] = el

    return nodes, ways, relations


def _project(lon: float, lat: float) -> tuple[float, float]:
    x, y = _TO_PROJ.transform(lon, lat)
    return float(x), float(y)


def _anchor_ids(el: dict) -> list[int]:
    """Node ids that physically represent this element (itself if a node, its node list if a way)."""
    if el.get("type") == "node":
        return [el["id"]]
    return list(el.get("nodes") or [])


# ── Construccion del grafo ──────────────────────────────────────────────


@dataclass(frozen=True)
class IndoorRoom:
    id: int
    osm_type: str
    name: str | None
    levels: list[float]
    polygon: Any  # shapely Polygon, or None if geometry could not be reconstructed


def _ensure_node(G: nx.MultiGraph, node_id: int, level: float, node_data: dict) -> str:
    key = _node_key(node_id, level)
    if key not in G:
        lon = node_data.get("lon")
        lat = node_data.get("lat")
        x = y = None
        if lon is not None and lat is not None:
            x, y = _project(lon, lat)
        G.add_node(
            key,
            osmid=node_id,
            level=level,
            lon=lon,
            lat=lat,
            x=x,
            y=y,
            node_type="indoor_way",
        )
    return key


def _build_horizontal_edges(G: nx.MultiGraph, ways: dict, nodes: dict) -> int:
    n_edges = 0
    for way in ways.values():
        tags = way.get("tags") or {}
        if not (tags.get("highway") == "footway" and tags.get("indoor") == "yes"):
            continue

        levels = _levels_for_tags(tags)
        if not levels:
            continue

        node_ids = way.get("nodes") or []
        for level in levels:
            for a_id, b_id in zip(node_ids[:-1], node_ids[1:]):
                na = nodes.get(a_id)
                nb = nodes.get(b_id)
                if na is None or nb is None or "lat" not in na or "lat" not in nb:
                    continue

                ka = _ensure_node(G, a_id, level, na)
                kb = _ensure_node(G, b_id, level, nb)

                xa, ya = G.nodes[ka]["x"], G.nodes[ka]["y"]
                xb, yb = G.nodes[kb]["x"], G.nodes[kb]["y"]
                length_m = math.hypot(xb - xa, yb - ya)
                cost_s = length_m / WALK_SPEED_M_S

                geometry = LineString([
                    (na["lon"], na["lat"]),
                    (nb["lon"], nb["lat"]),
                ])

                G.add_edge(
                    ka, kb,
                    kind="horizontal",
                    level=level,
                    length_m=length_m,
                    cost_s=cost_s,
                    can_walk=True,
                    can_bike=False,
                    can_drive=False,
                    geometry=geometry,
                    source_way=way["id"],
                )
                n_edges += 1

    return n_edges


def _vertical_kind(tags: dict) -> str | None:
    highway = tags.get("highway")
    if highway == "steps":
        return "steps"
    if highway == "elevator":
        return "elevator"
    if tags.get("conveying") in ("yes", "forward", "backward", "reversible"):
        return "conveying"
    return None


def _build_vertical_edges(G: nx.MultiGraph, ways: dict, nodes: dict) -> dict[str, int]:
    counts = {"steps": 0, "elevator": 0, "conveying": 0}

    all_vertical_elements = list(ways.values()) + [
        n for n in nodes.values() if _vertical_kind(n.get("tags") or {}) is not None
    ]

    for el in all_vertical_elements:
        tags = el.get("tags") or {}
        kind = _vertical_kind(tags)
        if kind is None:
            continue

        levels = sorted(set(_levels_for_tags(tags)))
        if len(levels) < 2:
            continue

        anchor_ids = _anchor_ids(el)
        cost_per_level = _VERTICAL_COST_PER_LEVEL[kind]

        for node_id in anchor_ids:
            node_data = nodes.get(node_id) or (el if el.get("type") == "node" else None)
            if node_data is None or "lat" not in node_data:
                continue

            for lvl_from, lvl_to in zip(levels[:-1], levels[1:]):
                plantas = abs(lvl_to - lvl_from)
                if kind == "elevator":
                    cost_s = ELEVATOR_WAIT_SECONDS + cost_per_level * plantas
                else:
                    cost_s = cost_per_level * plantas

                k_from = _ensure_node(G, node_id, lvl_from, node_data)
                k_to = _ensure_node(G, node_id, lvl_to, node_data)

                G.add_edge(
                    k_from, k_to,
                    kind=kind,
                    level_from=lvl_from,
                    level_to=lvl_to,
                    plantas=plantas,
                    cost_s=cost_s,
                    can_walk=True,
                    can_bike=False,
                    can_drive=False,
                    source_id=el["id"],
                    source_type=el["type"],
                )
                counts[kind] += 1

    return counts


def _add_dea_node(G: nx.MultiGraph, nodes: dict, aed_id: int) -> str | None:
    dea = nodes.get(aed_id)
    if dea is None or "lat" not in dea:
        logger.warning("DEA %s no encontrado en el dataset aislado.", aed_id)
        return None

    tags = dea.get("tags") or {}
    levels = _levels_for_tags(tags) or [0.0]
    level = levels[0]

    x, y = _project(dea["lon"], dea["lat"])
    key = f"aed_{aed_id}"
    G.add_node(
        key,
        aed_id=aed_id,
        level=level,
        lon=dea["lon"],
        lat=dea["lat"],
        x=x,
        y=y,
        node_type="aed",
    )
    return key


def _build_rooms(ways: dict, nodes: dict, relations: dict) -> list[IndoorRoom]:
    rooms: list[IndoorRoom] = []
    SHAPE_VALUES = ("room", "area", "corridor")

    for way in ways.values():
        tags = way.get("tags") or {}
        if tags.get("indoor") not in SHAPE_VALUES:
            continue

        node_ids = way.get("nodes") or []
        coords = [
            (nodes[n]["lon"], nodes[n]["lat"])
            for n in node_ids
            if n in nodes and "lat" in nodes[n]
        ]
        polygon = None
        if len(coords) >= 3:
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            try:
                polygon = Polygon(coords)
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
            except Exception:
                polygon = None

        rooms.append(IndoorRoom(
            id=way["id"],
            osm_type="way",
            name=tags.get("name"),
            levels=_levels_for_tags(tags),
            polygon=polygon,
        ))

    for rel in relations.values():
        tags = rel.get("tags") or {}
        if tags.get("indoor") not in ("room", "area"):
            continue

        outer_rings, inner_rings = [], []
        for m in rel.get("members") or []:
            if m.get("type") != "way":
                continue
            way = ways.get(m.get("ref"))
            if way is None:
                continue
            node_ids = way.get("nodes") or []
            coords = [
                (nodes[n]["lon"], nodes[n]["lat"])
                for n in node_ids
                if n in nodes and "lat" in nodes[n]
            ]
            if len(coords) < 3:
                continue
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            try:
                ring = Polygon(coords)
            except Exception:
                continue
            if m.get("role") == "inner":
                inner_rings.append(ring)
            else:
                outer_rings.append(ring)

        polygon = None
        if outer_rings:
            try:
                polygon = unary_union(outer_rings)
                if inner_rings:
                    polygon = polygon.difference(unary_union(inner_rings))
            except Exception:
                polygon = None

        rooms.append(IndoorRoom(
            id=rel["id"],
            osm_type="relation",
            name=tags.get("name"),
            levels=_levels_for_tags(tags),
            polygon=polygon,
        ))

    return rooms


def build_indoor_graph(
    isolated_json_path: Path = PROJECT_ROOT / ISOLATED_JSON_REL_PATH,
) -> tuple[nx.MultiGraph, list[IndoorRoom]]:
    """
    Build the (currently disconnected-from-base) indoor graph for Hbf from
    the already-isolated dataset. Undirected MultiGraph: indoor pedestrian
    movement is bidirectional, and "Multi" allows several distinct paths
    between the same two nodes. Rooms/areas/corridors are returned
    separately as metadata only — they are not routeable yet.
    """
    nodes, ways, relations = _load_isolated(isolated_json_path)

    G = nx.MultiGraph()
    G.graph["crs"] = CRS_MAP
    G.graph["source"] = str(isolated_json_path)

    n_horizontal = _build_horizontal_edges(G, ways, nodes)
    vertical_counts = _build_vertical_edges(G, ways, nodes)
    dea_key = _add_dea_node(G, nodes, WINNER_AED_ID)

    G.graph["n_horizontal_edges"] = n_horizontal
    G.graph["n_vertical_edges_by_kind"] = vertical_counts
    G.graph["dea_node_key"] = dea_key

    rooms = _build_rooms(ways, nodes, relations)

    return G, rooms


# ── Verificacion / resumen ───────────────────────────────────────────────


def per_level_components(G: nx.MultiGraph) -> dict[float, dict]:
    """
    Connected components per level, using ONLY horizontal edges (vertical
    edges by construction join different levels and do not affect a
    same-level partition).

    Reports two views per level:
    - "footway_only": components among nodes that touch at least one
      horizontal (footway) edge at that level — this is what Fase 2c's
      bbox-based connectivity check measured, and is expected to
      reproduce those numbers exactly (regression sanity check).
    - "full": components among ALL indoor_way nodes at that level,
      including vertical-connector anchors (steps/elevator) that do not
      happen to share a node with any footway at that level. These show
      up as extra singleton components — a real finding about the raw
      OSM topology (most vertical connectors don't land on a mapped
      footway node), not a construction bug.
    """
    nodes_by_level: dict[float, set] = defaultdict(set)
    for n, data in G.nodes(data=True):
        lv = data.get("level")
        if lv is not None and data.get("node_type") == "indoor_way":
            nodes_by_level[lv].add(n)

    horizontal_touched: dict[float, set] = defaultdict(set)
    for u, v, d in G.edges(data=True):
        if d.get("kind") == "horizontal":
            lv = d.get("level")
            horizontal_touched[lv].add(u)
            horizontal_touched[lv].add(v)

    def _components(node_set: set) -> tuple[int, int]:
        H = nx.Graph()
        H.add_nodes_from(node_set)
        for u, v, d in G.edges(data=True):
            if d.get("kind") == "horizontal" and u in node_set and v in node_set:
                H.add_edge(u, v)
        comps = sorted((len(c) for c in nx.connected_components(H)), reverse=True)
        return len(comps), (comps[0] if comps else 0)

    result = {}
    for lv, node_set in nodes_by_level.items():
        full_n_comp, full_largest = _components(node_set)
        fw_set = horizontal_touched.get(lv, set())
        fw_n_comp, fw_largest = _components(fw_set)
        result[lv] = {
            "n_nodes": len(node_set),
            "n_components": full_n_comp,
            "largest_component": full_largest,
            "footway_only_n_nodes": len(fw_set),
            "footway_only_n_components": fw_n_comp,
            "footway_only_largest_component": fw_largest,
            "vertical_only_anchor_nodes": len(node_set) - len(fw_set),
        }
    return result


def locate_dea_anchor(G: nx.MultiGraph, level: float = 0.0) -> tuple[str | None, float | None]:
    """
    Find the nearest level-0 routeable (indoor_way) node to the DEA, by
    straight-line distance in the projected CRS. Reports only — does not
    create the hookup edge (that belongs to the next phase).
    """
    dea_key = G.graph.get("dea_node_key")
    if dea_key is None or dea_key not in G:
        return None, None

    dea_x = G.nodes[dea_key]["x"]
    dea_y = G.nodes[dea_key]["y"]

    best_key, best_dist = None, None
    for n, data in G.nodes(data=True):
        if data.get("node_type") != "indoor_way" or data.get("level") != level:
            continue
        if data.get("x") is None:
            continue
        d = math.hypot(data["x"] - dea_x, data["y"] - dea_y)
        if best_dist is None or d < best_dist:
            best_key, best_dist = n, d

    return best_key, best_dist


def summarize(G: nx.MultiGraph, rooms: list[IndoorRoom]) -> str:
    lines: list[str] = []

    lines.append(f"Nodos totales: {G.number_of_nodes()}, aristas totales: {G.number_of_edges()}")

    nodes_by_level = defaultdict(int)
    edges_by_level = defaultdict(int)
    for _, data in G.nodes(data=True):
        if data.get("node_type") == "indoor_way":
            nodes_by_level[data["level"]] += 1
    for _, _, data in G.edges(data=True):
        if data.get("kind") == "horizontal":
            edges_by_level[data["level"]] += 1

    lines.append("\nNodos y aristas horizontales por nivel:")
    for lv in sorted(set(nodes_by_level) | set(edges_by_level)):
        lines.append(f"  level {lv:g}: {nodes_by_level.get(lv, 0)} nodos, "
                      f"{edges_by_level.get(lv, 0)} aristas horizontales")

    lines.append(f"\nAristas verticales por tipo: {G.graph.get('n_vertical_edges_by_kind')}")

    lines.append("\nComponentes conexas por nivel (solo red horizontal, dos vistas):")
    comps = per_level_components(G)
    for lv in sorted(comps):
        c = comps[lv]
        lines.append(
            f"  level {lv:g}: "
            f"footway-only = {c['footway_only_n_nodes']} nodos / "
            f"{c['footway_only_n_components']} componentes / "
            f"mayor {c['footway_only_largest_component']}  |  "
            f"full (+ anclas verticales) = {c['n_nodes']} nodos / "
            f"{c['n_components']} componentes / mayor {c['largest_component']} "
            f"({c['vertical_only_anchor_nodes']} anclas verticales sin footway propio)"
        )

    lines.append(f"\nSalas/areas/corridors cargados como metadato (no routeable): {len(rooms)}")
    with_name = sum(1 for r in rooms if r.name)
    with_geom = sum(1 for r in rooms if r.polygon is not None)
    lines.append(f"  con nombre: {with_name}, con geometria reconstruida: {with_geom}")

    dea_key = G.graph.get("dea_node_key")
    if dea_key:
        anchor_key, anchor_dist = locate_dea_anchor(G, level=0.0)
        lines.append(f"\nDEA (nodo {WINNER_AED_ID} -> '{dea_key}') level="
                      f"{G.nodes[dea_key]['level']:g}")
        if anchor_key is not None:
            lines.append(f"  Nodo routeable de nivel 0 mas cercano: '{anchor_key}' "
                          f"a {anchor_dist:.2f} m (NO enganchado todavia — solo reportado)")
        else:
            lines.append("  No se encontro ningun nodo routeable de nivel 0 en el grafo.")
    else:
        lines.append(f"\nDEA (nodo {WINNER_AED_ID}) NO esta presente en el grafo.")

    return "\n".join(lines)


def save_graph(G: nx.MultiGraph, rooms: list[IndoorRoom], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        pickle.dump({"graph": G, "rooms": rooms}, f, protocol=pickle.HIGHEST_PROTOCOL)


def main() -> None:
    isolated_path = PROJECT_ROOT / ISOLATED_JSON_REL_PATH
    out_path = PROJECT_ROOT / INDOOR_GRAPH_REL_PATH

    G, rooms = build_indoor_graph(isolated_path)
    save_graph(G, rooms, out_path)

    print(summarize(G, rooms))
    print(f"\nGrafo guardado en: {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
