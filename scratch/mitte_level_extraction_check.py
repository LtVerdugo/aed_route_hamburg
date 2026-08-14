"""
Fase 2b — Extraccion exploratoria por semantica (level) en Hamburg-Mitte.

Script de usar-y-tirar, SOLO LECTURA sobre el codigo del proyecto (no
modifica src/aed_route ni app/). Reutiliza el cliente Overpass existente.

Parte A: nwr["level"](area de Hamburg-Mitte) + recursion de nodos
         referenciados. Guarda crudo en data/interim/mitte_level_elements.json.
Parte B: inventario, catalogo de tags, niveles, comparacion con el
         taginfo de indoorequal, clasificacion routeable/shape/poi, y
         gap de elementos sin level (steps/elevator/door/entrance).

Uso:
    .venv/bin/python scratch/mitte_level_extraction_check.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
import urllib.error
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aed_route.io import call_overpass  # noqa: E402

OUT_PATH = PROJECT_ROOT / "data" / "interim" / "mitte_level_elements.json"
GAP_COUNTS_PATH = PROJECT_ROOT / "data" / "interim" / "mitte_level_gap_counts.json"
REPORT_PATH = PROJECT_ROOT / "scratch" / "mitte_level_extraction_report.md"

MITTE_RELATION_ID = 28971
TAGINFO_URL = "https://raw.githubusercontent.com/indoorequal/indoorequal/master/taginfo.json"

QUERY_A = f"""
[out:json][timeout:180];
rel({MITTE_RELATION_ID}); map_to_area->.a;
(
  nwr["level"](area.a);
);
(._; >;);
out body qt;
"""

# Universe counts (no level filter) for the gap analysis in section 5.
# One query per category (not a single unioned "out count;") so counts are
# not aggregated together and can be compared individually.
GAP_QUERIES = {
    "steps": f"""
        [out:json][timeout:60];
        rel({MITTE_RELATION_ID}); map_to_area->.a;
        way["highway"="steps"](area.a);
        out count;
    """,
    "elevator": f"""
        [out:json][timeout:60];
        rel({MITTE_RELATION_ID}); map_to_area->.a;
        nwr["highway"="elevator"](area.a);
        out count;
    """,
    "door": f"""
        [out:json][timeout:60];
        rel({MITTE_RELATION_ID}); map_to_area->.a;
        node["door"](area.a);
        out count;
    """,
    "entrance": f"""
        [out:json][timeout:60];
        rel({MITTE_RELATION_ID}); map_to_area->.a;
        node["entrance"](area.a);
        out count;
    """,
}

KEY_TAGS_TO_BREAKDOWN = [
    "indoor", "highway", "door", "entrance", "railway", "emergency",
    "shop", "amenity", "tourism",
]


# ── Parte A ──────────────────────────────────────────────────────────


def download_or_load_main() -> dict:
    if OUT_PATH.exists():
        print(f"Ya existe {OUT_PATH}, no se vuelve a descargar.")
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    print("Consultando Overpass — Parte A (nwr[level] en Hamburg-Mitte)...")
    resp = call_overpass(QUERY_A)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    print(f"Guardado en {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    return resp


def download_or_load_gap() -> dict:
    if GAP_COUNTS_PATH.exists():
        print(f"Ya existe {GAP_COUNTS_PATH}, no se vuelve a descargar.")
        return json.loads(GAP_COUNTS_PATH.read_text(encoding="utf-8"))

    import time
    results = {}
    categories = list(GAP_QUERIES.items())
    for i, (label, query) in enumerate(categories):
        print(f"Consultando Overpass — conteo universo '{label}' "
              f"(sin filtro de level, para la seccion 5 - gap)...")
        results[label] = call_overpass(query)
        if i < len(categories) - 1:
            time.sleep(2.0)

    GAP_COUNTS_PATH.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    return results


def build_indices(resp: dict):
    elements = resp.get("elements") or []
    nodes, ways, relations = {}, {}, {}
    for el in elements:
        t = el["type"]
        eid = el["id"]
        if t == "node":
            existing = nodes.get(eid)
            if existing is None or (not existing.get("tags") and el.get("tags")):
                nodes[eid] = el
        elif t == "way":
            ways[eid] = el
        elif t == "relation":
            relations[eid] = el
    return elements, nodes, ways, relations


def section_global(elements, nodes, ways, relations, lines):
    lines.append("## Parte A — Descarga\n")
    lines.append(f"- Archivo: `{OUT_PATH.relative_to(PROJECT_ROOT)}` — "
                 f"**{OUT_PATH.stat().st_size / 1024:.1f} KB**")
    lines.append(f"- Nodes: **{len(nodes)}**, Ways: **{len(ways)}**, Relations: **{len(relations)}**")
    lines.append(f"- Total elementos crudos (con posibles duplicados node id "
                 f"por `._; >;`): {len(elements)}\n")

    route_rels = [r for r in relations.values() if (r.get("tags") or {}).get("type") == "route"]
    if route_rels:
        lines.append(f"**ALERTA: se encontraron {len(route_rels)} relations `type=route` "
                     f"— NO se esperaban.** Ejemplos: " +
                     ", ".join(f"{r['id']} ({(r.get('tags') or {}).get('name')})" for r in route_rels[:5]))
    else:
        lines.append("Verificado: **0 relations `type=route`** — confirmado, no aparecen "
                     "(a diferencia del bbox crudo de Hbf en la Fase 2a.2, donde `>;` sin filtro "
                     "de `level` arrastraba rutas de bus/tren completas). Aqui el filtro "
                     "`nwr[\"level\"]` en el primer paso evita ese problema porque las relations "
                     "de ruta no llevan tag `level`.")
    lines.append("")

    rel_types = Counter((r.get("tags") or {}).get("type") for r in relations.values())
    lines.append(f"Tipos de relation presentes: {dict(rel_types)}\n")


# ── Parte B.1 — catalogo de tags ──────────────────────────────────────


def section_tag_catalog(nodes, ways, relations, lines):
    lines.append("## Parte B.1 — Catalogo de tags\n")
    all_els = list(nodes.values()) + list(ways.values()) + list(relations.values())

    key_counter = Counter()
    for el in all_els:
        for k in (el.get("tags") or {}):
            key_counter[k] += 1

    lines.append(f"Total claves de tag distintas: **{len(key_counter)}**\n")
    lines.append("Top 40 por frecuencia:\n")
    lines.append("| clave | # elementos |")
    lines.append("|---|---|")
    for k, c in key_counter.most_common(40):
        lines.append(f"| `{k}` | {c} |")
    lines.append("")

    lines.append("### Desglose de valores para tags clave\n")
    for key in KEY_TAGS_TO_BREAKDOWN:
        values = Counter()
        for el in all_els:
            v = (el.get("tags") or {}).get(key)
            if v is not None:
                values[v] += 1
        total = sum(values.values())
        lines.append(f"**`{key}`** — {total} elementos")
        if values:
            lines.append(", ".join(f"`{v}`={c}" for v, c in values.most_common(20)))
        lines.append("")

    return key_counter


# ── Parte B.2 — niveles ───────────────────────────────────────────────


def classify_level_value(raw: str) -> str:
    raw = raw.strip()
    if re.fullmatch(r"-?\d+", raw):
        return "entero"
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return "decimal"
    if re.fullmatch(r"-?\d+\s*-\s*-?\d+", raw):
        return "rango"
    if ";" in raw:
        return "lista"
    return "otro/no-numerico"


def section_levels(nodes, ways, relations, lines):
    lines.append("## Parte B.2 — Niveles\n")
    all_els = list(nodes.values()) + list(ways.values()) + list(relations.values())

    for key in ("level", "repeat_on"):
        values = Counter()
        shapes = Counter()
        decimals = []
        for el in all_els:
            tags = el.get("tags") or {}
            if key in tags:
                v = str(tags[key])
                values[v] += 1
                shape_cls = classify_level_value(v)
                shapes[shape_cls] += 1
                if shape_cls == "decimal":
                    decimals.append((el["type"], el["id"], v))

        lines.append(f"### `{key}` — presente en {sum(values.values())} elementos")
        if values:
            lines.append(f"Forma de los valores: {dict(shapes)}")
            lines.append("Top 20 valores: " + ", ".join(f"`{v}`={c}" for v, c in values.most_common(20)))
            if key == "level":
                if decimals:
                    lines.append(f"\n**Decimales confirmados ({len(decimals)}):** " +
                                 ", ".join(f"{t} {i} (level=`{v}`)" for t, i, v in decimals[:10]))
                else:
                    lines.append("\n**No se encontraron valores decimales de `level` en Hamburg-Mitte** "
                                 "(el `-0.5` visto en Hbf/indoorequal no aparece aqui, o esta fuera "
                                 "del limite administrativo de Mitte).")
        else:
            lines.append("No aparece.")
        lines.append("")


# ── Parte B.3 — comparacion con taginfo ───────────────────────────────


def fetch_taginfo() -> dict | None:
    try:
        req = urllib.request.Request(TAGINFO_URL, headers={"User-Agent": "aed_route_hamburg-scratch/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"No se pudo descargar taginfo.json: {exc}")
        return None


def extract_taginfo_tags(taginfo: dict) -> set[tuple[str, str | None]]:
    """
    taginfo.json (MediaWiki/taginfo project format) typically has a "tags" list
    of {"key": ..., "value": ...} dicts. Handle defensively since the exact
    schema is external and may vary.
    """
    tags = set()
    entries = taginfo.get("tags") if isinstance(taginfo, dict) else None
    if not entries:
        return tags
    for entry in entries:
        key = entry.get("key")
        value = entry.get("value")
        if key:
            tags.add((key, value))
    return tags


def section_taginfo_comparison(key_counter: Counter, nodes, ways, relations, lines):
    lines.append("## Parte B.3 — Comparacion con taginfo de indoorequal\n")

    taginfo = fetch_taginfo()
    if taginfo is None:
        lines.append("**No se pudo descargar o parsear el taginfo.json de indoorequal "
                     "(ver mensaje de error en consola). Seccion omitida — no se puede "
                     "cruzar sin el archivo de referencia.**\n")
        return

    taginfo_tags = extract_taginfo_tags(taginfo)
    taginfo_keys = {k for k, v in taginfo_tags}

    lines.append(f"taginfo.json: **{len(taginfo_tags)}** pares (key,value) / "
                 f"**{len(taginfo_keys)}** claves distintas declaradas por indoorequal.\n")

    our_keys = set(key_counter.keys())

    matched = sorted(taginfo_keys & our_keys, key=lambda k: -key_counter[k])
    only_taginfo = sorted(taginfo_keys - our_keys)
    only_ours_relevant = [
        k for k in our_keys - taginfo_keys
        if k in ("door", "entrance", "conveying", "stairs", "ramp", "level:ref",
                  "min_level", "max_level", "repeat_on", "wheelchair", "tactile_paving")
    ]

    lines.append(f"### Claves del taginfo presentes en nuestros datos ({len(matched)})\n")
    lines.append(", ".join(f"`{k}`={key_counter[k]}" for k in matched[:40]))
    lines.append("")

    lines.append(f"### Claves del taginfo que NO aparecen en Hamburg-Mitte ({len(only_taginfo)})\n")
    lines.append(", ".join(f"`{k}`" for k in only_taginfo[:40]) if only_taginfo else "(ninguna)")
    lines.append("")

    lines.append(f"### Tags nuestros relevantes que NO estan en el taginfo de indoorequal "
                 f"({len(only_ours_relevant)}) — posibles huecos de su lista\n")
    if only_ours_relevant:
        lines.append(", ".join(f"`{k}`={key_counter[k]}" for k in
                                sorted(only_ours_relevant, key=lambda k: -key_counter[k])))
    else:
        lines.append("(ninguno detectado)")
    lines.append("")


# ── Parte B.4 — clasificacion routeable / shape / poi ─────────────────


def section_classification(nodes, ways, relations, lines):
    lines.append("## Parte B.4 — Routeable vs Shape vs POI\n")

    all_els = list(nodes.values()) + list(ways.values()) + list(relations.values())

    routeable, shape, poi = [], [], []

    for el in all_els:
        tags = el.get("tags") or {}
        highway = tags.get("highway")
        indoor = tags.get("indoor")

        is_routeable = (
            (highway == "footway" and indoor == "yes")
            or highway in ("corridor", "steps", "elevator")
            or indoor == "corridor"
            or tags.get("conveying") in ("yes", "forward", "backward", "reversible")
        )
        is_shape = indoor in ("room", "area", "corridor", "wall", "column")
        is_poi = any(k in tags for k in ("shop", "amenity", "tourism"))

        if is_routeable:
            routeable.append(el)
        if is_shape:
            shape.append(el)
        if is_poi:
            poi.append(el)

    routeable_ids = {(e["type"], e["id"]) for e in routeable}
    shape_ids = {(e["type"], e["id"]) for e in shape}
    poi_ids = {(e["type"], e["id"]) for e in poi}

    lines.append(f"- (a) Routeable (footway+indoor, corridor, steps, elevator, conveying): "
                 f"**{len(routeable)}**")
    lines.append(f"- (b) Shape/estructura (indoor=room/area/corridor/wall/column): **{len(shape)}**")
    lines.append(f"- (c) POI/semantica (shop/amenity/tourism): **{len(poi)}**\n")

    overlap_route_shape = routeable_ids & shape_ids
    overlap_shape_poi = shape_ids & poi_ids
    overlap_route_poi = routeable_ids & poi_ids
    all_three = routeable_ids & shape_ids & poi_ids

    lines.append(f"**Solapes (un elemento puede caer en mas de un grupo — no son mutuamente "
                 f"excluyentes):**")
    lines.append(f"- routeable ∩ shape: **{len(overlap_route_shape)}** "
                 f"(esperado: `indoor=corridor` cuenta en ambos grupos segun la definicion dada)")
    lines.append(f"- shape ∩ poi: **{len(overlap_shape_poi)}** (p. ej. una sala `indoor=room` "
                 f"que ademas es `amenity=cafe`, como el caso DB Lounge visto en Hbf)")
    lines.append(f"- routeable ∩ poi: **{len(overlap_route_poi)}**")
    lines.append(f"- en los tres grupos a la vez: **{len(all_three)}**\n")

    none_of = [
        el for el in all_els
        if (el["type"], el["id"]) not in routeable_ids
        and (el["type"], el["id"]) not in shape_ids
        and (el["type"], el["id"]) not in poi_ids
    ]
    lines.append(f"- Elementos que NO caen en ninguno de los tres grupos: **{len(none_of)}** "
                 f"de {len(all_els)} totales (tienen `level` pero ninguna de las semanticas "
                 f"pedidas — p. ej. `door`/`entrance` puros, u otras combinaciones de tags).\n")


# ── Parte B.5 — gap de elementos sin level ────────────────────────────


def _extract_count(resp: dict) -> int:
    for el in (resp.get("elements") or []):
        if el.get("type") == "count":
            tags = el.get("tags", {})
            # Overpass "out count;" reports "total" (and "nodes"/"ways"/"relations")
            return int(tags.get("total", 0))
    return 0


def section_gap(nodes, ways, relations, gap_resp, lines):
    lines.append("## Parte B.5 — Gap de elementos SIN `level`\n")

    with_level_steps = sum(1 for w in ways.values()
                            if (w.get("tags") or {}).get("highway") == "steps"
                            and "level" in (w.get("tags") or {}))
    with_level_elevator = sum(
        1 for coll in (nodes, ways) for el in coll.values()
        if (el.get("tags") or {}).get("highway") == "elevator"
        and "level" in (el.get("tags") or {})
    )
    with_level_door = sum(1 for n in nodes.values()
                           if "door" in (n.get("tags") or {}) and "level" in (n.get("tags") or {}))
    with_level_entrance = sum(1 for n in nodes.values()
                               if "entrance" in (n.get("tags") or {}) and "level" in (n.get("tags") or {}))

    universe = {label: _extract_count(resp) for label, resp in gap_resp.items()}

    lines.append("Conteo UNIVERSO en Hamburg-Mitte (4 queries separadas, `out count;`, "
                 "SIN filtro de `level`) vs. cuantos de esos YA tienen `level` en "
                 "`mitte_level_elements.json`:\n")

    lines.append("| categoria | universo (todo Mitte) | con `level` | SIN `level` (gap) | % gap |")
    lines.append("|---|---|---|---|---|")

    rows = [
        ("highway=steps", universe.get("steps", 0), with_level_steps),
        ("highway=elevator", universe.get("elevator", 0), with_level_elevator),
        ("node door", universe.get("door", 0), with_level_door),
        ("node entrance", universe.get("entrance", 0), with_level_entrance),
    ]
    for label, total, with_lvl in rows:
        gap = total - with_lvl
        pct = (gap / total * 100) if total else 0.0
        lines.append(f"| {label} | {total} | {with_lvl} | {gap} | {pct:.1f}% |")
    lines.append("")

    lines.append(
        "Estos elementos SIN `level` (o sin ser miembros de ningun way con `level`) son "
        "**invisibles para la query `nwr[\"level\"]` de la Parte A** — solo se revelan con "
        "una query sin ese filtro, como las 4 usadas aqui. Este es el numero a tener en "
        "cuenta para decidir si la extraccion final debe complementarse con una pasada "
        "adicional no filtrada por `level` para estos 4 tags clave.\n"
    )


def main():
    lines: list[str] = []
    lines.append("# Extraccion exploratoria por level — Hamburg-Mitte (Fase 2b)\n")

    resp = download_or_load_main()
    elements, nodes, ways, relations = build_indices(resp)
    section_global(elements, nodes, ways, relations, lines)

    key_counter = section_tag_catalog(nodes, ways, relations, lines)
    section_levels(nodes, ways, relations, lines)
    section_taginfo_comparison(key_counter, nodes, ways, relations, lines)
    section_classification(nodes, ways, relations, lines)

    gap_resp = download_or_load_gap()
    section_gap(nodes, ways, relations, gap_resp, lines)

    report = "\n".join(lines) + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nInforme guardado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()
