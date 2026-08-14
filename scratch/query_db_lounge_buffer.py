"""
Fase 3 — Re-consulta dirigida de Overpass alrededor de la DB Lounge (way
733736697) para verificar si tiene una puerta mapeada que el dataset
filtrado por `level` no capturo. Script de usar-y-tirar. NO modifica
src/aed_route ni app/. Reutiliza el cliente Overpass del proyecto.

Uso:
    .venv/bin/python scratch/query_db_lounge_buffer.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aed_route.io import call_overpass  # noqa: E402
from aed_route.config import CRS_MAP, CRS_PROJECTED  # noqa: E402
from pyproj import Transformer  # noqa: E402
from shapely.geometry import LineString, Point, Polygon  # noqa: E402

ISOLATED_JSON = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_isolated.json"
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "db_lounge_buffer.json"

DB_LOUNGE_ID = 733736697
BUFFER_M = 10.0
CLOSE_THRESHOLD_M = 3.0

_TO_PROJ = Transformer.from_crs(CRS_MAP, CRS_PROJECTED, always_xy=True)
_TO_WGS = Transformer.from_crs(CRS_PROJECTED, CRS_MAP, always_xy=True)


# ── Parte 1 — bbox con buffer correcto ──────────────────────────────────


def load_db_lounge_ring():
    data = json.loads(ISOLATED_JSON.read_text(encoding="utf-8"))
    elements = data.get("elements") or []
    nodes = {e["id"]: e for e in elements if e.get("type") == "node"}
    way = next((e for e in elements if e.get("type") == "way" and e.get("id") == DB_LOUNGE_ID), None)
    if way is None:
        raise RuntimeError(f"Way {DB_LOUNGE_ID} no encontrado en {ISOLATED_JSON}")

    ring = [(nodes[n]["lon"], nodes[n]["lat"]) for n in (way.get("nodes") or []) if n in nodes]
    return ring


def compute_buffered_bbox(ring):
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    x0, y0 = _TO_PROJ.transform(min_lon, min_lat)
    x1, y1 = _TO_PROJ.transform(max_lon, max_lat)

    x0 -= BUFFER_M
    y0 -= BUFFER_M
    x1 += BUFFER_M
    y1 += BUFFER_M

    buf_min_lon, buf_min_lat = _TO_WGS.transform(x0, y0)
    buf_max_lon, buf_max_lat = _TO_WGS.transform(x1, y1)

    return {
        "raw_bbox": {"min_lat": min_lat, "min_lon": min_lon, "max_lat": max_lat, "max_lon": max_lon},
        "buffered_bbox": {
            "south": buf_min_lat, "west": buf_min_lon,
            "north": buf_max_lat, "east": buf_max_lon,
        },
    }


# ── Parte 2 — re-consulta Overpass ──────────────────────────────────────


def download_buffer(bbox: dict) -> dict:
    if OUT_PATH.exists():
        print(f"Ya existe {OUT_PATH}, no se vuelve a descargar.")
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))

    query = f"""
    [out:json][timeout:60];
    (
      nwr({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
    );
    (._; >;);
    out body qt;
    """
    print("Consultando Overpass — buffer de 10 m alrededor de la DB Lounge...")
    resp = call_overpass(query)
    OUT_PATH.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    return resp


# ── Parte 3 — veredicto de la puerta ────────────────────────────────────


def analyze(resp: dict, db_lounge_ring, isolated_data):
    elements = resp.get("elements") or []
    nodes = {e["id"]: e for e in elements if e.get("type") == "node"}
    ways = {e["id"]: e for e in elements if e.get("type") == "way"}
    relations = [e for e in elements if e.get("type") == "relation"]

    route_rels = [r for r in relations if (r.get("tags") or {}).get("type") == "route"]

    # DB Lounge boundary in projected coords, for accurate metric distance
    proj_ring = [_TO_PROJ.transform(lon, lat) for lon, lat in db_lounge_ring]
    boundary = LineString(proj_ring)

    db_lounge_node_ids = set()
    isolated_elements = isolated_data.get("elements") or []
    for e in isolated_elements:
        if e.get("type") == "way" and e.get("id") == DB_LOUNGE_ID:
            db_lounge_node_ids = set(e.get("nodes") or [])
            break

    close_nodes = []
    for n in nodes.values():
        if "lat" not in n:
            continue
        x, y = _TO_PROJ.transform(n["lon"], n["lat"])
        dist = boundary.distance(Point(x, y))
        if dist <= CLOSE_THRESHOLD_M:
            close_nodes.append((dist, n))
    close_nodes.sort(key=lambda t: t[0])

    # shared-vertex check: any footway/corridor way in the buffer sharing a
    # node id with the DB Lounge's own ring (a "doorless opening")
    shared_vertex_ways = []
    for way in ways.values():
        tags = way.get("tags") or {}
        is_routeable = (
            (tags.get("highway") == "footway" and tags.get("indoor") == "yes")
            or tags.get("highway") == "corridor"
            or tags.get("indoor") == "corridor"
        )
        if not is_routeable:
            continue
        shared = db_lounge_node_ids & set(way.get("nodes") or [])
        if shared:
            shared_vertex_ways.append((way, shared))

    # what door/entrance nodes did the OLD filtered dataset already have,
    # anywhere (not just near DB Lounge) -- for the "brought something new" comparison
    old_door_entrance_ids = set()
    for e in isolated_elements:
        if e.get("type") != "node":
            continue
        tags = e.get("tags") or {}
        if "door" in tags or tags.get("indoor") == "door" or "entrance" in tags:
            old_door_entrance_ids.add(e["id"])

    new_door_entrance_nodes = []
    for n in nodes.values():
        tags = n.get("tags") or {}
        if "door" in tags or tags.get("indoor") == "door" or "entrance" in tags:
            if n["id"] not in old_door_entrance_ids:
                new_door_entrance_nodes.append(n)

    return {
        "route_relations": route_rels,
        "close_nodes": close_nodes,
        "shared_vertex_ways": shared_vertex_ways,
        "new_door_entrance_nodes": new_door_entrance_nodes,
        "n_nodes": len(nodes),
        "n_ways": len(ways),
        "n_relations": len(relations),
    }


def main():
    ring = load_db_lounge_ring()
    bbox_info = compute_buffered_bbox(ring)

    print("Parte 1 — bbox con buffer de 10 m (proyectado correctamente):")
    print(f"  bbox original (sin buffer): {bbox_info['raw_bbox']}")
    print(f"  bbox con buffer +{BUFFER_M} m: {bbox_info['buffered_bbox']}")
    print()

    resp = download_buffer(bbox_info["buffered_bbox"])

    print(f"Parte 2 — descarga: {resp.get('elements') and len(resp['elements'])} elementos crudos.")

    isolated_data = json.loads(ISOLATED_JSON.read_text(encoding="utf-8"))
    result = analyze(resp, ring, isolated_data)

    print(f"  nodes={result['n_nodes']}, ways={result['n_ways']}, relations={result['n_relations']}")
    if result["route_relations"]:
        print(f"  ALERTA: {len(result['route_relations'])} relations type=route encontradas: " +
              ", ".join(str(r["id"]) for r in result["route_relations"]))
    else:
        print("  Confirmado: 0 relations type=route.")
    print()

    print(f"Parte 3 — nodos a <= {CLOSE_THRESHOLD_M} m del perimetro de la DB Lounge: "
          f"{len(result['close_nodes'])}")
    for dist, n in result["close_nodes"]:
        print(f"  node {n['id']} — dist={dist:.2f} m, lat={n.get('lat')}, lon={n.get('lon')}, "
              f"tags={json.dumps(n.get('tags'), ensure_ascii=False)}")

    print()
    print("Ways routeable (footway+indoor / corridor) que comparten node id con la DB Lounge "
          "(posible apertura sin puerta):")
    if result["shared_vertex_ways"]:
        for way, shared in result["shared_vertex_ways"]:
            print(f"  way {way['id']} tags={way.get('tags')} — nodos compartidos: {shared}")
    else:
        print("  Ninguno.")

    print()
    print("Nodos door/entrance en el buffer que NO estaban en el dataset filtrado por level:")
    if result["new_door_entrance_nodes"]:
        for n in result["new_door_entrance_nodes"]:
            print(f"  NUEVO node {n['id']} — lat={n.get('lat')}, lon={n.get('lon')}, "
                  f"tags={json.dumps(n.get('tags'), ensure_ascii=False)}")
    else:
        print("  Ninguno — el buffer no trajo ninguna puerta/entrada nueva.")

    print()
    has_door_like = any(
        "door" in (n.get("tags") or {}) or (n.get("tags") or {}).get("indoor") == "door"
        or "entrance" in (n.get("tags") or {})
        for _, n in result["close_nodes"]
    )
    if has_door_like:
        print("VEREDICTO: SI hay un nodo door/entrance cerca del perimetro (ver lista arriba).")
    elif result["shared_vertex_ways"]:
        print("VEREDICTO: NO hay nodo door/entrance explicito, pero SI hay una apertura sin "
              "puerta (vertice compartido con footway/corridor) — ver ways listados arriba.")
    else:
        print("VEREDICTO: NO se encontro ninguna puerta, entrada, ni apertura compartida con "
              "un footway/corridor a <= 3 m del perimetro de la DB Lounge, ni siquiera "
              "ampliando la consulta a un buffer de 10 m sin filtro de tag ni de level.")


if __name__ == "__main__":
    main()
