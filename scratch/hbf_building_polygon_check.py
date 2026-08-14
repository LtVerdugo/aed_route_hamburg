"""
Fase 2a.4 — Diagnostico del poligono de edificio de Hamburg Hbf.

Script de usar-y-tirar, SOLO LECTURA sobre el codigo del proyecto (no
modifica src/aed_route ni app/). Red: solo dos queries pequenas
(enumeracion de candidatos + geometria de UN elemento). El test de
contencion usa el archivo ya en disco data/interim/hbf_osm_full.json
(no se vuelve a descargar el bbox completo).

Uso:
    .venv/bin/python scratch/hbf_building_polygon_check.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aed_route.io import call_overpass  # noqa: E402

from shapely.geometry import Polygon, Point, shape  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

FULL_JSON_PATH = PROJECT_ROOT / "data" / "interim" / "hbf_osm_full.json"
REPORT_PATH = PROJECT_ROOT / "scratch" / "hbf_building_polygon_report.md"
CANDIDATES_RAW_PATH = PROJECT_ROOT / "data" / "interim" / "hbf_building_candidates.json"
CHOSEN_GEOM_RAW_PATH_TMPL = PROJECT_ROOT / "data" / "interim" / "hbf_building_geom_{kind}_{id}.json"

BBOX = "53.5515,10.0035,53.5545,10.0095"

QUERY_A = f"""
[out:json][timeout:60];
(
  way["building"]({BBOX});
  relation["building"]({BBOX});
  nwr["railway"="station"]({BBOX});
  nwr["public_transport"="station"]({BBOX});
  way["building:part"]({BBOX});
);
out tags bb;
"""


# ── Parte A ──────────────────────────────────────────────────────────


def run_part_a() -> dict:
    if CANDIDATES_RAW_PATH.exists():
        print(f"Ya existe {CANDIDATES_RAW_PATH}, no se vuelve a consultar Overpass.")
        return json.loads(CANDIDATES_RAW_PATH.read_text(encoding="utf-8"))

    print("Consultando Overpass — Parte A (enumeracion de candidatos)...")
    resp = call_overpass(QUERY_A)
    CANDIDATES_RAW_PATH.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    return resp


def bbox_of(el: dict) -> tuple[float, float, float, float] | None:
    b = el.get("bounds")
    if not b:
        return None
    return b["minlat"], b["minlon"], b["maxlat"], b["maxlon"]


def bbox_area_deg2(bb) -> float:
    minlat, minlon, maxlat, maxlon = bb
    return (maxlat - minlat) * (maxlon - minlon)


def analyze_part_a(resp: dict, lines: list[str]):
    elements = resp.get("elements") or []

    buildings = [
        e for e in elements
        if (e["type"] in ("way", "relation")) and "building" in (e.get("tags") or {})
    ]
    stations = [
        e for e in elements
        if (e.get("tags") or {}).get("railway") == "station"
        or (e.get("tags") or {}).get("public_transport") == "station"
    ]
    building_parts = [e for e in elements if e["type"] == "way" and "building:part" in (e.get("tags") or {})]

    lines.append("## Parte A — Candidatos a edificio/estacion\n")
    lines.append(f"Total elementos devueltos: {len(elements)} "
                 f"(buildings={len(buildings)}, stations={len(stations)}, "
                 f"building:part={len(building_parts)})\n")

    lines.append("### Candidatos `building` (way/relation)\n")
    lines.append("| id | tipo | building | name | ref | bbox (minlat,minlon,maxlat,maxlon) | area bbox (deg2) |")
    lines.append("|---|---|---|---|---|---|---|")
    building_rows = []
    for e in buildings:
        tags = e.get("tags") or {}
        bb = bbox_of(e)
        area = bbox_area_deg2(bb) if bb else None
        building_rows.append((e, bb, area))
        bb_str = f"{bb[0]:.5f},{bb[1]:.5f},{bb[2]:.5f},{bb[3]:.5f}" if bb else "n/a"
        area_str = f"{area:.2e}" if area else "n/a"
        lines.append(
            f"| {e['id']} | {e['type']} | {tags.get('building')} | {tags.get('name')} | "
            f"{tags.get('ref')} | {bb_str} | {area_str} |"
        )
    lines.append("")

    lines.append("### Elementos `railway=station` / `public_transport=station` (A EVITAR)\n")
    lines.append("| id | tipo | tags clave | bbox |")
    lines.append("|---|---|---|---|")
    for e in stations:
        tags = e.get("tags") or {}
        bb = bbox_of(e)
        bb_str = f"{bb[0]:.5f},{bb[1]:.5f},{bb[2]:.5f},{bb[3]:.5f}" if bb else "n/a"
        lines.append(
            f"| {e['id']} | {e['type']} | railway={tags.get('railway')} "
            f"public_transport={tags.get('public_transport')} name={tags.get('name')} | {bb_str} |"
        )
    lines.append("")
    if stations:
        biggest_station = max(
            (e for e in stations if bbox_of(e)),
            key=lambda e: bbox_area_deg2(bbox_of(e)),
            default=None,
        )
        if biggest_station:
            bb = bbox_of(biggest_station)
            lines.append(
                f"**Area grande de estacion a evitar:** {biggest_station['type']} "
                f"{biggest_station['id']} (`{(biggest_station.get('tags') or {}).get('name')}`), "
                f"bbox area = {bbox_area_deg2(bb):.2e} deg2 — "
                f"{bbox_area_deg2(bb) / max((a for _, _, a in building_rows if a), default=1):.1f}x "
                f"mas grande que el mayor candidato `building`.\n"
            )

    lines.append(f"### `building:part`\n")
    lines.append(f"Total `building:part` en el bbox: **{len(building_parts)}**\n")

    return building_rows, stations, building_parts


# ── Parte B ──────────────────────────────────────────────────────────


def load_full_json() -> tuple[dict, dict]:
    data = json.loads(FULL_JSON_PATH.read_text(encoding="utf-8"))
    elements = data.get("elements") or []
    nodes = {}
    ways = {}
    for el in elements:
        if el["type"] == "node":
            existing = nodes.get(el["id"])
            if existing is None or (not existing.get("tags") and el.get("tags")):
                nodes[el["id"]] = el
        elif el["type"] == "way":
            ways[el["id"]] = el
    return nodes, ways


def compute_indoor_extent(nodes: dict, ways: dict):
    """Bounding box of all indoor-semantics elements, for choosing the best building candidate."""
    lats, lons = [], []
    for w in ways.values():
        tags = w.get("tags") or {}
        is_indoor_relevant = (
            "indoor" in tags
            or tags.get("highway") in ("footway", "steps", "elevator", "corridor")
            or tags.get("conveying") in ("yes", "forward", "backward", "reversible")
        )
        if not is_indoor_relevant:
            continue
        for nid in (w.get("nodes") or []):
            n = nodes.get(nid)
            if n and "lat" in n:
                lats.append(n["lat"])
                lons.append(n["lon"])
    for n in nodes.values():
        tags = n.get("tags") or {}
        if "door" in tags or "entrance" in tags or tags.get("emergency") == "defibrillator":
            if "lat" in n:
                lats.append(n["lat"])
                lons.append(n["lon"])
    if not lats:
        return None
    return min(lats), min(lons), max(lats), max(lons)


def choose_building(building_rows, indoor_extent, lines):
    lines.append("## Parte B.1 — Eleccion del poligono\n")

    ilat0, ilon0, ilat1, ilon1 = indoor_extent
    lines.append(
        f"Dispersion (bbox) de todos los elementos indoor en `hbf_osm_full.json`: "
        f"lat [{ilat0:.5f}, {ilat1:.5f}], lon [{ilon0:.5f}, {ilon1:.5f}] "
        f"(area = {(ilat1-ilat0)*(ilon1-ilon0):.2e} deg2).\n"
    )

    scored = []
    for e, bb, area in building_rows:
        if bb is None:
            continue
        blat0, blon0, blat1, blon1 = bb
        # coverage: fraction of indoor extent's bbox area covered by intersection with building bbox
        ilat_lo, ilat_hi = max(ilat0, blat0), min(ilat1, blat1)
        ilon_lo, ilon_hi = max(ilon0, blon0), min(ilon1, blon1)
        inter_h = max(0.0, ilat_hi - ilat_lo)
        inter_w = max(0.0, ilon_hi - ilon_lo)
        inter_area = inter_h * inter_w
        indoor_area = (ilat1 - ilat0) * (ilon1 - ilon0)
        coverage = inter_area / indoor_area if indoor_area > 0 else 0.0
        scored.append((coverage, area, e, bb))

    scored.sort(key=lambda x: (-x[0], x[1] or 0))

    lines.append("Cobertura de cada candidato `building` sobre la dispersion indoor "
                 "(interseccion de bboxes / area de la dispersion indoor):\n")
    lines.append("| id | tipo | name | cobertura indoor | area bbox candidato |")
    lines.append("|---|---|---|---|---|")
    for coverage, area, e, bb in scored:
        tags = e.get("tags") or {}
        area_str = f"{area:.2e}" if area else "n/a"
        lines.append(f"| {e['id']} | {e['type']} | {tags.get('name')} | {coverage:.1%} | {area_str} |")
    lines.append("")

    best = scored[0]
    _, _, best_el, best_bb = best
    tags = best_el.get("tags") or {}
    lines.append(
        f"**Elegido: {best_el['type']} `{best_el['id']}`** (`building={tags.get('building')}`, "
        f"name=`{tags.get('name')}`) — cobertura {best[0]:.1%} de la dispersion indoor, "
        f"es el candidato `building` (no estacion) con mayor solapamiento con donde realmente "
        f"estan los elementos indoor mapeados. Se descartan los `railway=station`/"
        f"`public_transport=station` explicitamente porque son el area grande a evitar "
        f"(incluyen anden al aire libre, no la huella del edificio)."
    )
    lines.append("")
    return best_el


def download_geometry(el: dict) -> dict:
    kind = "way" if el["type"] == "way" else "rel"
    out_path = Path(str(CHOSEN_GEOM_RAW_PATH_TMPL).format(kind=el["type"], id=el["id"]))
    if out_path.exists():
        print(f"Ya existe {out_path}, no se vuelve a descargar.")
        return json.loads(out_path.read_text(encoding="utf-8"))

    query = f"""
    [out:json][timeout:60];
    {kind}({el['id']});
    out geom;
    """
    print(f"Consultando Overpass — Parte B.2 (geometria de {el['type']} {el['id']})...")
    resp = call_overpass(query)
    out_path.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    return resp


def build_polygon(geom_resp: dict, root_el: dict):
    elements = geom_resp.get("elements") or []

    if root_el["type"] == "way":
        way = next(e for e in elements if e["type"] == "way" and e["id"] == root_el["id"])
        coords = [(pt["lon"], pt["lat"]) for pt in way.get("geometry") or [] if pt is not None]
        return Polygon(coords)

    # relation (multipolygon): assemble outer(s) minus inner(s)
    rel = next(e for e in elements if e["type"] == "relation" and e["id"] == root_el["id"])
    outer_rings = []
    inner_rings = []
    for m in rel.get("members") or []:
        if m.get("type") != "way":
            continue
        geom = m.get("geometry") or []
        coords = [(pt["lon"], pt["lat"]) for pt in geom if pt is not None]
        if len(coords) < 3:
            continue
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        ring = Polygon(coords)
        if m.get("role") == "inner":
            inner_rings.append(ring)
        else:
            outer_rings.append(ring)

    if not outer_rings:
        return None
    outer_union = unary_union(outer_rings)
    if inner_rings:
        inner_union = unary_union(inner_rings)
        outer_union = outer_union.difference(inner_union)
    return outer_union


def collect_indoor_elements(nodes: dict, ways: dict):
    """Reconstruct point/centroid geometry for indoor-semantics elements, grouped by level."""
    items = []  # (level, kind, id, Point)

    for w in ways.values():
        tags = w.get("tags") or {}
        is_relevant = (
            "indoor" in tags
            or tags.get("highway") in ("footway", "steps", "elevator", "corridor")
            or tags.get("conveying") in ("yes", "forward", "backward", "reversible")
        )
        if not is_relevant:
            continue
        node_ids = w.get("nodes") or []
        pts = [(nodes[n]["lon"], nodes[n]["lat"]) for n in node_ids if n in nodes and "lat" in nodes[n]]
        if not pts:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        level = tags.get("level", "sin level")
        items.append((str(level), "way", w["id"], Point(cx, cy)))

    for n in nodes.values():
        tags = n.get("tags") or {}
        if "door" in tags or "entrance" in tags or tags.get("emergency") == "defibrillator":
            if "lat" not in n:
                continue
            level = tags.get("level", "sin level")
            items.append((str(level), "node", n["id"], Point(n["lon"], n["lat"])))

    return items


def containment_test(polygon, items, lines):
    lines.append("## Parte B.4 — Test de contencion por nivel\n")

    by_level = defaultdict(lambda: [0, 0])  # level -> [inside, total]
    outside_examples = defaultdict(list)

    for level, kind, eid, pt in items:
        inside = polygon.contains(pt) or polygon.touches(pt)
        by_level[level][1] += 1
        if inside:
            by_level[level][0] += 1
        else:
            if len(outside_examples[level]) < 3:
                outside_examples[level].append((kind, eid, pt.y, pt.x))

    lines.append("| level | dentro | total | % dentro |")
    lines.append("|---|---|---|---|")

    def level_sort_key(lv):
        try:
            return (0, float(lv.split(";")[0]))
        except ValueError:
            return (1, lv)

    for level in sorted(by_level.keys(), key=level_sort_key):
        inside, total = by_level[level]
        pct = inside / total * 100 if total else 0.0
        lines.append(f"| {level} | {inside} | {total} | {pct:.1f}% |")
    lines.append("")

    lines.append("Ejemplos de elementos FUERA del poligono (hasta 3 por nivel, solo niveles con fugas):\n")
    any_leak = False
    for level in sorted(outside_examples.keys(), key=level_sort_key):
        exs = outside_examples[level]
        if not exs:
            continue
        any_leak = True
        lines.append(f"- level `{level}`:")
        for kind, eid, lat, lon in exs:
            lines.append(f"  - {kind} {eid} — lat={lat:.6f}, lon={lon:.6f}")
    if not any_leak:
        lines.append("(ninguno — todos los elementos cayeron dentro del poligono)")
    lines.append("")

    return by_level


def main():
    lines: list[str] = []
    lines.append("# Diagnostico del poligono de edificio — Hamburg Hbf (Fase 2a.4)\n")

    resp_a = run_part_a()
    building_rows, stations, building_parts = analyze_part_a(resp_a, lines)

    nodes, ways = load_full_json()
    indoor_extent = compute_indoor_extent(nodes, ways)
    if indoor_extent is None:
        print("No se encontraron elementos indoor en hbf_osm_full.json — abortando.")
        return

    best_el = choose_building(building_rows, indoor_extent, lines)

    geom_resp = download_geometry(best_el)
    polygon = build_polygon(geom_resp, best_el)

    if polygon is None or polygon.is_empty:
        lines.append("**No se pudo construir el poligono del elemento elegido (geometria vacia).**\n")
        report = "\n".join(lines) + "\n"
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(report)
        return

    lines.append("## Parte B.2/B.3 — Poligono descargado y elementos indoor cargados\n")
    lines.append(
        f"Poligono construido a partir de {best_el['type']} {best_el['id']}: "
        f"area = {polygon.area:.2e} deg2, valido={polygon.is_valid}, "
        f"tipo shapely={polygon.geom_type}.\n"
    )

    items = collect_indoor_elements(nodes, ways)
    lines.append(f"Elementos indoor reconstruidos desde `hbf_osm_full.json` para el test: **{len(items)}**\n")

    by_level = containment_test(polygon, items, lines)

    lines.append("## Conclusion\n")
    total_inside = sum(v[0] for v in by_level.values())
    total_all = sum(v[1] for v in by_level.values())
    overall_pct = total_inside / total_all * 100 if total_all else 0.0

    basement_levels = [lv for lv in by_level if lv not in ("0", "sin level") and not lv.startswith("1") and lv != "1"]
    worst_level = min(
        (lv for lv in by_level if by_level[lv][1] >= 3),
        key=lambda lv: by_level[lv][0] / by_level[lv][1],
        default=None,
    )

    lines.append(f"- Contencion global: **{overall_pct:.1f}%** ({total_inside}/{total_all}) de los "
                 f"elementos indoor caen dentro del poligono elegido.")
    if worst_level is not None:
        wi, wt = by_level[worst_level]
        lines.append(f"- Peor nivel: `{worst_level}` con solo {wi}/{wt} "
                     f"({wi/wt*100:.1f}%) dentro del poligono.")

    if overall_pct >= 98:
        verdict = "SUFICIENTE"
    elif overall_pct >= 90:
        verdict = "CASI SUFICIENTE (fugas menores, revisar niveles concretos)"
    else:
        verdict = "INSUFICIENTE"

    lines.append(f"\n**Veredicto: el poligono es {verdict} como recorte para un dataset indoor completo.**")
    lines.append(
        "Alternativas a considerar si hay fugas relevantes en sotano: (a) usar la relation del "
        "edificio en vez del way si esta incluye partes subterraneas explicitas via `building:part`; "
        "(b) unir el poligono building con los building:part que se extiendan mas alla del contorno "
        "principal; (c) aplicar un buffer pequeno (p. ej. 5-10 m) al poligono para absorber "
        "desalineaciones de mapeo entre el contorno del edificio y los elementos indoor cercanos al "
        "perimetro; (d) si el sotano se extiende claramente fuera de la huella (p. ej. tuneles de "
        "acceso a anden), definir un recorte especifico por nivel en vez de un unico poligono 2D."
    )
    lines.append("")

    report = "\n".join(lines) + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nInforme guardado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()
