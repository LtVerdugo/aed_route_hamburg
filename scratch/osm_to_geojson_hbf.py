"""
Fase 3 — Conversion Overpass JSON -> GeoJSON para visualizar Hbf en 3D con
OpenIndoor (https://app.openindoor.io, drag&drop de GeoJSON).

Script de usar-y-tirar, SOLO LECTURA sobre datos, SIN RED. NO modifica
src/aed_route ni app/. osm2geojson no esta instalado en el venv del
proyecto y no se instala nada nuevo — conversion manual Overpass -> GeoJSON.

Fuente: data/interim/hbf_indoor_clean_v2.json (Overpass JSON, 0 relations
type=route, ya verificado en la fase anterior).

Uso:
    .venv/bin/python scratch/osm_to_geojson_hbf.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Reused ONLY for read-only level-range reporting (does not alter the
# `level` value stored in the GeoJSON properties themselves).
from aed_route.indoor import parse_level  # noqa: E402

from shapely.geometry import Polygon, mapping  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

SOURCE_JSON = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_clean_v2.json"
OUT_GEOJSON = PROJECT_ROOT / "scratch" / "hbf_indoor.geojson"

WINNER_AED_ID = 13948102741


def load_source():
    data = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    elements = data.get("elements") or []

    nodes, ways, relations = {}, {}, {}
    for el in elements:
        t = el.get("type")
        eid = el.get("id")
        if t == "node":
            existing = nodes.get(eid)
            if existing is None or (not existing.get("tags") and el.get("tags")):
                nodes[eid] = el
        elif t == "way":
            ways[eid] = el
        elif t == "relation":
            relations[eid] = el

    return nodes, ways, relations


def base_properties(el: dict) -> dict:
    props = dict(el.get("tags") or {})
    props["osm_id"] = el["id"]
    props["osm_type"] = el["type"]
    return props


def node_to_feature(node: dict) -> dict | None:
    if "lat" not in node or "lon" not in node:
        return None
    if not node.get("tags"):
        return None  # bare geometry-only nodes add no value as standalone points
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [node["lon"], node["lat"]]},
        "properties": base_properties(node),
    }


def way_coords(way: dict, nodes: dict) -> list[list[float]] | None:
    node_ids = way.get("nodes") or []
    coords = []
    missing = 0
    for nid in node_ids:
        n = nodes.get(nid)
        if n is None or "lat" not in n:
            missing += 1
            continue
        coords.append([n["lon"], n["lat"]])
    if len(coords) < 2:
        return None
    if missing:
        print(f"  aviso: way {way['id']} tiene {missing} nodo(s) sin coordenadas resueltas "
              f"(omitidos de la geometria)")
    return coords


def way_to_feature(way: dict, nodes: dict) -> dict | None:
    coords = way_coords(way, nodes)
    if coords is None:
        return None

    is_closed = len(coords) >= 4 and coords[0] == coords[-1]
    if is_closed:
        geometry = {"type": "Polygon", "coordinates": [coords]}
    else:
        geometry = {"type": "LineString", "coordinates": coords}

    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": base_properties(way),
    }


def relation_to_feature(rel: dict, ways: dict, nodes: dict) -> dict | None:
    tags = rel.get("tags") or {}
    if tags.get("type") != "multipolygon":
        return None

    outer_rings, inner_rings = [], []
    for m in rel.get("members") or []:
        if m.get("type") != "way":
            continue
        way = ways.get(m.get("ref"))
        if way is None:
            print(f"  aviso: relation {rel['id']} referencia way {m.get('ref')} "
                  f"no presente en el dataset — se omite ese miembro")
            continue
        coords = way_coords(way, nodes)
        if coords is None:
            continue
        if coords[0] != coords[-1]:
            coords = coords + [coords[0]]
        try:
            ring = Polygon(coords)
        except Exception as exc:
            print(f"  aviso: relation {rel['id']} miembro way {way['id']} geometria invalida "
                  f"({exc}) — se omite")
            continue
        (inner_rings if m.get("role") == "inner" else outer_rings).append(ring)

    if not outer_rings:
        print(f"  aviso: relation {rel['id']} (multipolygon) sin anillos exteriores validos — se omite")
        return None

    try:
        polygon = unary_union(outer_rings)
        if inner_rings:
            polygon = polygon.difference(unary_union(inner_rings))
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty:
            raise ValueError("geometria resultante vacia")
    except Exception as exc:
        print(f"  aviso: relation {rel['id']} no se pudo ensamblar como poligono valido "
              f"({exc}) — se omite")
        return None

    return {
        "type": "Feature",
        "geometry": mapping(polygon),
        "properties": base_properties(rel),
    }


def main():
    nodes, ways, relations = load_source()

    features = []
    geom_type_counter = Counter()

    for node in nodes.values():
        feat = node_to_feature(node)
        if feat is not None:
            features.append(feat)
            geom_type_counter[feat["geometry"]["type"]] += 1

    for way in ways.values():
        feat = way_to_feature(way, nodes)
        if feat is not None:
            features.append(feat)
            geom_type_counter[feat["geometry"]["type"]] += 1

    skipped_relations = 0
    for rel in relations.values():
        feat = relation_to_feature(rel, ways, nodes)
        if feat is not None:
            features.append(feat)
            geom_type_counter[feat["geometry"]["type"]] += 1
        elif (rel.get("tags") or {}).get("type") == "multipolygon":
            skipped_relations += 1

    fc = {"type": "FeatureCollection", "features": features}
    OUT_GEOJSON.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")

    # ── Verificacion ─────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("Verificacion")
    print("=" * 60)
    print(f"Total features: {len(features)}")
    for geom_type, count in geom_type_counter.most_common():
        print(f"  {geom_type}: {count}")
    print(f"Relations multipolygon omitidas (geometria no ensamblable): {skipped_relations}")

    with_level = [f for f in features if "level" in f["properties"]]
    print(f"\nFeatures con `level`: {len(with_level)} de {len(features)}")

    numeric_levels = []
    unparsed = []
    for f in with_level:
        raw = f["properties"]["level"]
        parsed = parse_level(raw)
        if parsed:
            numeric_levels.extend(parsed)
        else:
            unparsed.append(raw)
    if numeric_levels:
        print(f"Rango de niveles (parseado solo para este reporte, "
              f"NO se modifico el GeoJSON): {min(numeric_levels):g} a {max(numeric_levels):g}")
    if unparsed:
        print(f"Valores de `level` no parseables encontrados (se dejaron intactos en el "
              f"GeoJSON igualmente): {set(unparsed)}")

    dea_features = [
        f for f in features
        if f["properties"].get("osm_id") == WINNER_AED_ID
        and f["geometry"]["type"] == "Point"
        and f["properties"].get("emergency") == "defibrillator"
    ]
    if dea_features:
        print(f"\nDEA (node {WINNER_AED_ID}) presente como Point con "
              f"emergency=defibrillator: SI — level={dea_features[0]['properties'].get('level')}")
    else:
        print(f"\nDEA (node {WINNER_AED_ID}) presente como Point con "
              f"emergency=defibrillator: NO ENCONTRADO")

    print(f"\nGeoJSON guardado en: {OUT_GEOJSON} ({OUT_GEOJSON.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
