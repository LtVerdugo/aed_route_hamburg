"""
Fase 2c — Aislar Hamburg Hbf desde mitte_level_elements.json y verificar
el recorte. Script de usar-y-tirar, SOLO LECTURA, SIN RED. No modifica
src/aed_route ni app/. Lee unicamente data/interim/mitte_level_elements.json
(ya en disco) y escribe data/interim/hbf_indoor_isolated.json.

Uso:
    .venv/bin/python scratch/isolate_hbf_from_mitte.py
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "data" / "interim" / "mitte_level_elements.json"
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_isolated.json"
REPORT_PATH = PROJECT_ROOT / "scratch" / "hbf_isolated_report.md"

WINNER_AED_ID = 13948102741

BBOX_SOUTH = 53.5505
BBOX_WEST = 10.0025
BBOX_NORTH = 53.5560
BBOX_EAST = 10.0110


# ── Carga e indices ──────────────────────────────────────────────────


def load_source():
    data = json.loads(SRC_PATH.read_text(encoding="utf-8"))
    elements = data.get("elements") or []
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
    return nodes, ways, relations


def way_centroid(way: dict, nodes: dict):
    pts = [(nodes[n]["lat"], nodes[n]["lon"]) for n in (way.get("nodes") or [])
           if n in nodes and "lat" in nodes[n]]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def relation_centroid(rel: dict, nodes: dict, ways: dict):
    lats, lons = [], []
    for m in rel.get("members") or []:
        if m.get("type") == "node" and m.get("ref") in nodes:
            n = nodes[m["ref"]]
            if "lat" in n:
                lats.append(n["lat"])
                lons.append(n["lon"])
        elif m.get("type") == "way" and m.get("ref") in ways:
            c = way_centroid(ways[m["ref"]], nodes)
            if c:
                lats.append(c[0])
                lons.append(c[1])
    if not lats:
        return None
    return sum(lats) / len(lats), sum(lons) / len(lons)


def in_bbox(lat, lon) -> bool:
    return BBOX_SOUTH <= lat <= BBOX_NORTH and BBOX_WEST <= lon <= BBOX_EAST


# ── Parte A — recorte espacial ────────────────────────────────────────


def section_part_a(nodes, ways, relations, lines):
    lines.append("## Parte A — Recorte espacial\n")
    lines.append(
        f"Bbox: sur={BBOX_SOUTH}, oeste={BBOX_WEST}, norte={BBOX_NORTH}, este={BBOX_EAST}\n"
    )

    in_nodes, in_ways, in_rels = {}, {}, {}

    for nid, n in nodes.items():
        if "lat" in n and in_bbox(n["lat"], n["lon"]):
            in_nodes[nid] = n

    for wid, w in ways.items():
        c = way_centroid(w, nodes)
        if c and in_bbox(*c):
            in_ways[wid] = w

    for rid, r in relations.items():
        c = relation_centroid(r, nodes, ways)
        if c and in_bbox(*c):
            in_rels[rid] = r

    lines.append(f"- Nodes dentro del bbox: **{len(in_nodes)}** de {len(nodes)}")
    lines.append(f"- Ways dentro del bbox (por centroide): **{len(in_ways)}** de {len(ways)}")
    lines.append(f"- Relations dentro del bbox (por centroide de miembros): **{len(in_rels)}** "
                 f"de {len(relations)}\n")

    return in_nodes, in_ways, in_rels


# ── Parte B.1 — que edificios hay dentro ──────────────────────────────


def section_buildings(in_nodes, in_ways, in_rels, lines):
    lines.append("## Parte B.1 — Edificios dentro del bbox\n")

    all_named = list(in_nodes.values()) + list(in_ways.values()) + list(in_rels.values())

    name_counter = Counter()
    operator_counter = Counter()
    for el in all_named:
        tags = el.get("tags") or {}
        if tags.get("name"):
            name_counter[tags["name"]] += 1
        if tags.get("operator"):
            operator_counter[tags["operator"]] += 1

    lines.append(f"### Top nombres (`name`) dentro del bbox ({len(name_counter)} distintos)\n")
    lines.append(", ".join(f"`{n}`={c}" for n, c in name_counter.most_common(30)))
    lines.append("")

    lines.append(f"### Top operadores (`operator`) dentro del bbox ({len(operator_counter)} distintos)\n")
    lines.append(", ".join(f"`{o}`={c}" for o, c in operator_counter.most_common(20)))
    lines.append("")

    suspicious_keywords = ["kunsthalle", "zob", "mediamarkt", "schauspielhaus", "europäischer hof",
                            "spitaler", "bieberhaus", "museum"]
    suspicious_hits = []
    for el in all_named:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").lower()
        for kw in suspicious_keywords:
            if kw in name:
                lat = el.get("lat")
                lon = el.get("lon")
                suspicious_hits.append((tags.get("name"), el["type"], el["id"], lat, lon, kw))

    lines.append("### Chequeo de vecinos ajenos conocidos (Kunsthalle, ZOB, MediaMarkt, etc.)\n")
    if suspicious_hits:
        lines.append("**Se colaron elementos de edificios vecinos:**\n")
        lines.append("| name | tipo | id | lat | lon | keyword |")
        lines.append("|---|---|---|---|---|---|")
        for name, t, i, lat, lon, kw in suspicious_hits[:20]:
            lines.append(f"| {name} | {t} | {i} | {lat} | {lon} | {kw} |")
    else:
        lines.append("No se detectaron coincidencias con nombres de edificios vecinos conocidos "
                     "(Kunsthalle, ZOB, MediaMarkt, Schauspielhaus, Europäischer Hof, Spitaler Hof, "
                     "Bieberhaus, museos) dentro del bbox.")
    lines.append("")

    dominant_names = [n for n, c in name_counter.most_common(15) if "hauptbahnhof" in n.lower()
                       or "hbf" in n.lower() or "gleis" in n.lower() or "bahnsteig" in n.lower()]
    lines.append(f"Nombres relacionados directamente con Hbf/anden/via en el top 15: {dominant_names}\n")


# ── Parte B.2 — dispersion por nivel ──────────────────────────────────


def section_level_dispersion(in_nodes, in_ways, in_rels, lines):
    lines.append("## Parte B.2 — Dispersion por nivel\n")

    all_els = list(in_nodes.values()) + list(in_ways.values()) + list(in_rels.values())
    level_counter = Counter()
    for el in all_els:
        lv = (el.get("tags") or {}).get("level")
        if lv is not None:
            level_counter[lv] += 1

    lines.append(f"Elementos con `level` dentro del bbox: **{sum(level_counter.values())}**\n")
    lines.append("| level | # elementos |")
    lines.append("|---|---|")

    def sort_key(lv):
        try:
            return (0, float(lv.split(";")[0]))
        except ValueError:
            return (1, lv)

    for lv, c in sorted(level_counter.items(), key=lambda x: sort_key(x[0])):
        lines.append(f"| {lv} | {c} |")
    lines.append("")

    basements_present = [lv for lv in level_counter if lv.startswith("-1") or lv.startswith("-2")
                          or lv.startswith("-3") or "-1" in lv or "-2" in lv or "-3" in lv]
    decimals_present = [lv for lv in level_counter if re.search(r"\d\.\d", lv)]

    lines.append(f"Niveles de sotano detectados (-1/-2/-3, incluye listas que los mencionen): "
                 f"**{'si' if basements_present else 'NO — bbox insuficiente'}** "
                 f"— ejemplos: {basements_present[:10]}")
    lines.append(f"Decimales detectados (p.ej. -0.5): **{'si' if decimals_present else 'no'}** "
                 f"— valores: {decimals_present}\n")

    return level_counter


# ── Parte B.3 — inventario de conectores ──────────────────────────────


def section_connectors(in_nodes, in_ways, in_rels, lines):
    lines.append("## Parte B.3 — Inventario de conectores\n")

    def level_of(tags):
        return tags.get("level", "sin level")

    footway_indoor = [w for w in in_ways.values()
                       if (w.get("tags") or {}).get("highway") == "footway"
                       and (w.get("tags") or {}).get("indoor") == "yes"]
    corridor_hwy = [w for w in in_ways.values() if (w.get("tags") or {}).get("highway") == "corridor"]

    steps = [w for w in in_ways.values() if (w.get("tags") or {}).get("highway") == "steps"]
    elevator = [el for coll in (in_nodes, in_ways) for el in coll.values()
                if (el.get("tags") or {}).get("highway") == "elevator"]
    conveying = [w for w in in_ways.values()
                 if (w.get("tags") or {}).get("conveying") in ("yes", "forward", "backward", "reversible")]

    door_tag = [n for n in in_nodes.values() if "door" in (n.get("tags") or {})]
    indoor_door_tag = [n for n in in_nodes.values() if (n.get("tags") or {}).get("indoor") == "door"]

    rooms = [w for w in in_ways.values() if (w.get("tags") or {}).get("indoor") == "room"]
    areas = [w for w in in_ways.values() if (w.get("tags") or {}).get("indoor") == "area"]
    corridors_indoor = [w for w in in_ways.values() if (w.get("tags") or {}).get("indoor") == "corridor"]

    def by_level_counts(elements):
        c = Counter()
        for e in elements:
            c[level_of(e.get("tags") or {})] += 1
        return dict(c)

    lines.append(f"### Vias routeable")
    lines.append(f"- `highway=footway`+`indoor=yes`: **{len(footway_indoor)}** — por nivel: "
                 f"{by_level_counts(footway_indoor)}")
    lines.append(f"- `highway=corridor`: **{len(corridor_hwy)}** — por nivel: "
                 f"{by_level_counts(corridor_hwy)}\n")

    lines.append(f"### Verticales")
    lines.append(f"- `highway=steps`: **{len(steps)}** — por nivel: {by_level_counts(steps)}")
    lines.append(f"- `highway=elevator`: **{len(elevator)}** — por nivel: {by_level_counts(elevator)}")
    lines.append(f"- `conveying=yes/forward/backward/reversible`: **{len(conveying)}** — por nivel: "
                 f"{by_level_counts(conveying)}\n")

    lines.append(f"### Puertas (dos convenciones distintas)")
    lines.append(f"- tag `door=*` (node): **{len(door_tag)}** — por nivel: {by_level_counts(door_tag)}")
    lines.append(f"- tag `indoor=door` (node): **{len(indoor_door_tag)}** — por nivel: "
                 f"{by_level_counts(indoor_door_tag)}")
    both = {n["id"] for n in door_tag} & {n["id"] for n in indoor_door_tag}
    lines.append(f"- nodos con AMBAS convenciones a la vez: **{len(both)}**\n")

    lines.append(f"### Shape (poligonos)")
    named_rooms = sum(1 for w in rooms if (w.get("tags") or {}).get("name"))
    named_areas = sum(1 for w in areas if (w.get("tags") or {}).get("name"))
    named_corridors = sum(1 for w in corridors_indoor if (w.get("tags") or {}).get("name"))
    lines.append(f"- `indoor=room`: **{len(rooms)}** ({named_rooms} con `name`)")
    lines.append(f"- `indoor=area`: **{len(areas)}** ({named_areas} con `name`)")
    lines.append(f"- `indoor=corridor`: **{len(corridors_indoor)}** ({named_corridors} con `name`)\n")

    lines.append(f"### El DEA ganador\n")
    aed = in_nodes.get(WINNER_AED_ID)
    if aed:
        tags = aed.get("tags") or {}
        lines.append(f"Nodo {WINNER_AED_ID} **SI esta dentro del bbox**. level=`{tags.get('level')}`, "
                     f"indoor=`{tags.get('indoor')}`, lat={aed.get('lat')}, lon={aed.get('lon')}.\n")
    else:
        lines.append(f"**Nodo {WINNER_AED_ID} NO aparece dentro del bbox** — revisar coordenadas "
                     f"o si el nodo esta presente en mitte_level_elements.json en absoluto.\n")

    return footway_indoor, corridor_hwy


# ── Parte B.4 — conectividad rapida ───────────────────────────────────


class DSU:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def section_connectivity(footway_indoor, corridor_hwy, lines):
    lines.append("## Parte B.4 — Conectividad rapida (componentes por nivel)\n")

    line_ways = footway_indoor + corridor_hwy
    by_level_ways = defaultdict(list)
    for w in line_ways:
        lv = (w.get("tags") or {}).get("level", "sin level")
        by_level_ways[lv].append(w)

    lines.append(f"Red routeable analizada: {len(line_ways)} ways "
                 f"(`footway+indoor=yes` + `highway=corridor`).\n")
    lines.append("| level | # ways | # componentes | mayor componente (nodos) |")
    lines.append("|---|---|---|---|")

    def sort_key(lv):
        try:
            return (0, float(lv.split(";")[0]))
        except ValueError:
            return (1, lv)

    for lv, wlist in sorted(by_level_ways.items(), key=lambda x: sort_key(x[0])):
        dsu = DSU()
        node_set = set()
        for w in wlist:
            nids = w.get("nodes") or []
            node_set.update(nids)
            for a, b in zip(nids[:-1], nids[1:]):
                dsu.union(a, b)
        comp_sizes = Counter(dsu.find(n) for n in node_set)
        n_comp = len(comp_sizes)
        largest = max(comp_sizes.values()) if comp_sizes else 0
        lines.append(f"| {lv} | {len(wlist)} | {n_comp} | {largest} |")
    lines.append("")


# ── Parte C — parseo de niveles ───────────────────────────────────────


def parse_level(raw: str):
    raw = raw.strip()
    if ";" in raw:
        result = []
        for part in raw.split(";"):
            sub = parse_level(part)
            if sub is None:
                return None
            result.extend(sub)
        return result
    if re.fullmatch(r"-?\d+", raw):
        return [float(raw)]
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return [float(raw)]
    m = re.fullmatch(r"(-?\d+)-(-?\d+)", raw)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return [float(x) for x in range(lo, hi + 1)]
    return None


def section_parse_levels(in_nodes, in_ways, in_rels, lines):
    lines.append("## Parte C — Parseo de niveles (verificacion)\n")

    all_els = list(in_nodes.values()) + list(in_ways.values()) + list(in_rels.values())
    raw_values = Counter()
    for el in all_els:
        lv = (el.get("tags") or {}).get("level")
        if lv is not None:
            raw_values[str(lv)] += 1

    shape_counts = Counter()
    unparseable = []
    normalized_levels = Counter()  # normalized numeric level -> # of source (element,level) occurrences

    for raw, count in raw_values.items():
        if ";" in raw:
            shape_counts["lista"] += count
        elif re.fullmatch(r"-?\d+", raw):
            shape_counts["entero"] += count
        elif re.fullmatch(r"-?\d+\.\d+", raw):
            shape_counts["decimal"] += count
        elif re.fullmatch(r"-?\d+-(-?\d+)", raw):
            shape_counts["rango"] += count
        else:
            shape_counts["otro/no-numerico"] += count

        parsed = parse_level(raw)
        if parsed is None:
            unparseable.append((raw, count))
        else:
            for p in parsed:
                normalized_levels[p] += count

    lines.append(f"Valores `level` distintos (raw): **{len(raw_values)}**, "
                 f"ocurrencias totales: **{sum(raw_values.values())}**\n")
    lines.append(f"Clasificacion: {dict(shape_counts)}\n")

    lines.append("### Conjunto de plantas reales (normalizado)\n")
    lines.append("Plantas detectadas tras expandir listas y rangos (nota: los conteos suman "
                 "mas que el total de elementos porque una lista como `-1;0` cuenta para ambas "
                 "plantas):\n")
    lines.append(", ".join(f"`{p:g}`={c}" for p, c in sorted(normalized_levels.items())))
    lines.append("")

    lines.append(f"### Valores de `level` que la funcion NO supo parsear: **{len(unparseable)}**\n")
    if unparseable:
        lines.append("| valor raw | ocurrencias |")
        lines.append("|---|---|")
        for raw, count in sorted(unparseable, key=lambda x: -x[1]):
            lines.append(f"| `{raw}` | {count} |")
    else:
        lines.append("(ninguno — todos los valores se parsearon)")
    lines.append("")


# ── Main ───────────────────────────────────────────────────────────────


def main():
    nodes, ways, relations = load_source()

    lines: list[str] = []
    lines.append("# Aislamiento de Hbf desde Mitte + verificacion del recorte (Fase 2c)\n")
    lines.append(f"Fuente: `{SRC_PATH.relative_to(PROJECT_ROOT)}` — "
                 f"{len(nodes)} nodes, {len(ways)} ways, {len(relations)} relations totales en Mitte.\n")

    in_nodes, in_ways, in_rels = section_part_a(nodes, ways, relations, lines)

    section_buildings(in_nodes, in_ways, in_rels, lines)
    section_level_dispersion(in_nodes, in_ways, in_rels, lines)
    footway_indoor, corridor_hwy = section_connectors(in_nodes, in_ways, in_rels, lines)
    section_connectivity(footway_indoor, corridor_hwy, lines)
    section_parse_levels(in_nodes, in_ways, in_rels, lines)

    isolated = {
        "type": "FeatureCollectionRaw",
        "bbox": {"south": BBOX_SOUTH, "west": BBOX_WEST, "north": BBOX_NORTH, "east": BBOX_EAST},
        "elements": (
            [{"type": "node", **v} for v in in_nodes.values()]
            + [{"type": "way", **v} for v in in_ways.values()]
            + [{"type": "relation", **v} for v in in_rels.values()]
        ),
    }
    # de-duplicate the "type" key collision from ** spread (original el already has "type")
    for el in isolated["elements"]:
        pass  # el["type"] already correct since original dicts include their own "type" key

    OUT_PATH.write_text(json.dumps(isolated, ensure_ascii=False), encoding="utf-8")

    report = "\n".join(lines) + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSubconjunto guardado en: {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    print(f"Informe guardado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()
