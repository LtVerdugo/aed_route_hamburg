"""
Fase 2a.2 — Descarga COMPLETA de Hamburg Hbf (con topologia real) e
inventario exhaustivo. Script de usar-y-tirar, SOLO LECTURA sobre el
codigo del proyecto (no modifica src/aed_route ni app/). Reutiliza el
cliente Overpass existente (rotacion de endpoints + backoff).

Parte A: descarga nwr(bbox) + recursion de nodos referenciados
         ("out body; >; out skel qt;") y guarda el crudo en
         data/interim/hbf_osm_full.json (no toca el probe de la Fase 0).
Parte B: inventario exhaustivo en Markdown.

Uso:
    .venv/bin/python scratch/hbf_full_download_and_inventory.py
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aed_route.io import call_overpass  # noqa: E402

OUT_PATH = PROJECT_ROOT / "data" / "interim" / "hbf_osm_full.json"
REPORT_PATH = PROJECT_ROOT / "scratch" / "hbf_full_inventory.md"
WINNER_ROOM_ID = 733736697
WINNER_AED_ID = 13948102741

BBOX = "53.5515,10.0035,53.5545,10.0095"

QUERY = f"""
[out:json][timeout:180];
(
  nwr({BBOX});
);
out body;
>;
out skel qt;
"""


# ── Parte A — descarga ──────────────────────────────────────────────


def download_or_load() -> dict:
    if OUT_PATH.exists():
        print(f"Ya existe {OUT_PATH}, no se vuelve a descargar.")
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))

    print("Descargando bbox completo de Hbf via Overpass (out body; >; out skel qt;)...")
    resp = call_overpass(QUERY)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    print(f"Guardado en {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    return resp


# ── Utilidades comunes ───────────────────────────────────────────────


def haversine_m(p1, p2) -> float:
    lat1, lon1 = p1
    lat2, lon2 = p2
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def classify_level_value(raw: str) -> str:
    raw = raw.strip()
    import re
    if re.fullmatch(r"-?\d+", raw):
        return "entero"
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return "decimal"
    if re.fullmatch(r"-?\d+\s*-\s*-?\d+", raw):
        return "rango"
    if ";" in raw:
        return "lista"
    return "otro/no-numerico"


def build_indices(resp: dict):
    elements = resp.get("elements") or []

    nodes: dict[int, dict] = {}
    ways: dict[int, dict] = {}
    relations: dict[int, dict] = {}

    for el in elements:
        t = el["type"]
        eid = el["id"]
        if t == "node":
            existing = nodes.get(eid)
            if existing is None:
                nodes[eid] = el
            else:
                # prefer the version with tags (from "out body" over "out skel")
                if not existing.get("tags") and el.get("tags"):
                    nodes[eid] = el
        elif t == "way":
            ways[eid] = el
        elif t == "relation":
            relations[eid] = el

    return elements, nodes, ways, relations


def is_horizontal_routable(tags: dict) -> bool:
    highway = tags.get("highway")
    indoor = tags.get("indoor")
    return (highway == "footway" and indoor == "yes") or indoor == "corridor" or highway == "corridor"


def is_closed(way: dict) -> bool:
    node_ids = way.get("nodes") or []
    return len(node_ids) >= 3 and node_ids[0] == node_ids[-1]


def way_centroid(way: dict, nodes: dict) -> tuple[float, float] | None:
    node_ids = way.get("nodes") or []
    pts = [(nodes[n]["lat"], nodes[n]["lon"]) for n in node_ids if n in nodes and "lat" in nodes[n]]
    if not pts:
        return way.get("center", {}).get("lat"), way.get("center", {}).get("lon")
    lat = sum(p[0] for p in pts) / len(pts)
    lon = sum(p[1] for p in pts) / len(pts)
    return lat, lon


# ── Union-Find para componentes conexas ─────────────────────────────


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


# ── Secciones del inventario ─────────────────────────────────────────


def section_global(elements, nodes, ways, relations, lines):
    lines.append("## 1. Global\n")
    lines.append(f"- Nodes: **{len(nodes)}**")
    lines.append(f"- Ways: **{len(ways)}**")
    lines.append(f"- Relations: **{len(relations)}**")
    lines.append(f"- Total elementos en respuesta cruda: **{len(elements)}** "
                 f"(puede incluir duplicados node id por `out body` + `out skel qt`)")
    lines.append(f"- Tamano del archivo `{OUT_PATH.relative_to(PROJECT_ROOT)}`: "
                 f"**{OUT_PATH.stat().st_size / 1024:.1f} KB**\n")


def section_tag_catalog(nodes, ways, relations, lines):
    lines.append("## 2. Catalogo de tags (todas las claves, por frecuencia)\n")
    key_counter = Counter()
    for coll in (nodes, ways, relations):
        for el in coll.values():
            for k in (el.get("tags") or {}):
                key_counter[k] += 1

    lines.append(f"Total claves de tag distintas: **{len(key_counter)}**\n")
    lines.append("| clave | # elementos que la usan |")
    lines.append("|---|---|")
    for k, c in key_counter.most_common():
        lines.append(f"| `{k}` | {c} |")
    lines.append("")


def section_levels(nodes, ways, relations, lines):
    lines.append("## 3. Niveles\n")
    all_els = list(nodes.values()) + list(ways.values()) + list(relations.values())

    for key in ("level", "repeat_on"):
        values = Counter()
        shapes = Counter()
        for el in all_els:
            tags = el.get("tags") or {}
            if key in tags:
                v = str(tags[key])
                values[v] += 1
                shapes[classify_level_value(v)] += 1
        lines.append(f"### `{key}` — presente en {sum(values.values())} elementos")
        if values:
            lines.append(f"Forma de los valores: {dict(shapes)}")
            lines.append("Top 15 valores: " + ", ".join(f"`{v}`={c}" for v, c in values.most_common(15)))
        else:
            lines.append("No aparece.")
        lines.append("")

    both = 0
    diff = []
    for el in all_els:
        tags = el.get("tags") or {}
        if "layer" in tags and "level" in tags:
            both += 1
            if str(tags["layer"]) != str(tags["level"]):
                diff.append((el["type"], el["id"], tags["layer"], tags["level"]))
    lines.append(f"### `layer` vs `level`")
    lines.append(f"- Elementos con ambos: **{both}**")
    lines.append(f"- De esos, con valores DISTINTOS: **{len(diff)}**")
    for t, i, lv, lvl in diff[:10]:
        lines.append(f"  - {t} {i}: layer=`{lv}` level=`{lvl}`")
    lines.append("")


def section_horizontal(ways, relations, nodes, lines):
    lines.append("## 4. Horizontal routeable\n")

    footway_indoor = []
    corridor_lines = []
    corridor_polys = []
    room_area_polys = []

    for w in ways.values():
        tags = w.get("tags") or {}
        highway = tags.get("highway")
        indoor = tags.get("indoor")
        closed = is_closed(w)

        if highway == "footway" and indoor == "yes":
            footway_indoor.append(w)
        if indoor == "corridor" or highway == "corridor":
            if closed:
                corridor_polys.append(w)
            else:
                corridor_lines.append(w)
        if indoor in ("room", "area"):
            room_area_polys.append(w)

    for r in relations.values():
        tags = r.get("tags") or {}
        if tags.get("indoor") in ("room", "area"):
            room_area_polys.append(r)
        if tags.get("indoor") == "corridor":
            corridor_polys.append(r)

    lines.append(f"- `highway=footway` + `indoor=yes` (lineas): **{len(footway_indoor)}**")
    lines.append(f"- `indoor=corridor` / `highway=corridor` como LINEA (way abierto): **{len(corridor_lines)}**")
    lines.append(f"- `indoor=corridor` como POLIGONO (way/relation cerrado): **{len(corridor_polys)}**")
    lines.append(f"- `indoor=room` / `indoor=area` (poligonos): **{len(room_area_polys)}**\n")

    if corridor_lines:
        lines.append("Ejemplo corridor-linea:")
        lines.append(f"```json\n{json.dumps(corridor_lines[0], indent=2, ensure_ascii=False)[:800]}\n```")
    if corridor_polys:
        lines.append("Ejemplo corridor-poligono:")
        lines.append(f"```json\n{json.dumps(corridor_polys[0], indent=2, ensure_ascii=False)[:800]}\n```")
    lines.append("")

    return footway_indoor, corridor_lines


def section_vertical(ways, nodes, lines):
    lines.append("## 5. Vertical\n")

    cats = {
        "highway=steps": [],
        "highway=elevator (way)": [],
        "conveying=yes": [],
        "stairs=yes": [],
        "ramp/incline": [],
    }

    elevator_nodes = []

    for w in ways.values():
        tags = w.get("tags") or {}
        if tags.get("highway") == "steps":
            cats["highway=steps"].append(w)
        if tags.get("highway") == "elevator":
            cats["highway=elevator (way)"].append(w)
        if tags.get("conveying") in ("yes", "forward", "backward", "reversible"):
            cats["conveying=yes"].append(w)
        if tags.get("stairs") == "yes":
            cats["stairs=yes"].append(w)
        if "ramp" in tags or "incline" in tags:
            cats["ramp/incline"].append(w)

    for n in nodes.values():
        tags = n.get("tags") or {}
        if tags.get("highway") == "elevator":
            elevator_nodes.append(n)

    for label, els in cats.items():
        levels_seen = Counter()
        for e in els:
            lv = (e.get("tags") or {}).get("level")
            levels_seen[lv if lv is not None else "sin level"] += 1
        lines.append(f"- {label}: **{len(els)}** ways. Niveles: {dict(levels_seen)}")

    lev_elev_nodes = Counter()
    for n in elevator_nodes:
        lv = (n.get("tags") or {}).get("level")
        lev_elev_nodes[lv if lv is not None else "sin level"] += 1
    lines.append(f"- `highway=elevator` (node): **{len(elevator_nodes)}**. Niveles: {dict(lev_elev_nodes)}")
    lines.append("")


def section_multilevel_structures(relations, lines):
    lines.append("## 6. Estructuras multinivel (relations)\n")

    building_rels = [r for r in relations.values() if (r.get("tags") or {}).get("type") == "building" or "building" in (r.get("tags") or {})]
    indoor_level_rels = [r for r in relations.values() if (r.get("tags") or {}).get("indoor") == "level"]
    multipolygon_rels = [r for r in relations.values() if (r.get("tags") or {}).get("type") == "multipolygon"]

    lines.append(f"- Relations `type=building` (o con tag `building`): **{len(building_rels)}**")
    lines.append(f"- Relations `indoor=level`: **{len(indoor_level_rels)}**")
    lines.append(f"- Relations `type=multipolygon`: **{len(multipolygon_rels)}**\n")

    def describe(rel_list, label):
        if not rel_list:
            return
        lines.append(f"### {label}")
        for r in rel_list[:10]:
            tags = r.get("tags") or {}
            members = r.get("members") or []
            lines.append(
                f"- relation {r['id']} — level=`{tags.get('level')}` name=`{tags.get('name')}` "
                f"— {len(members)} miembros (roles: {dict(Counter(m.get('role') for m in members))})"
            )
        lines.append("")

    describe(building_rels, "Relations `building`")
    describe(indoor_level_rels, "Relations `indoor=level`")
    describe(multipolygon_rels, "Relations `multipolygon`")


def section_doors(nodes, ways, relations, lines):
    lines.append("## 7. Puertas (door) vs entradas (entrance)\n")

    routable_ways = {
        w["id"]: w for w in ways.values()
        if is_horizontal_routable(w.get("tags") or {})
        or (w.get("tags") or {}).get("highway") in ("steps", "elevator")
    }

    node_to_ways = defaultdict(list)
    for w in routable_ways.values():
        for nid in (w.get("nodes") or []):
            node_to_ways[nid].append(w["id"])

    door_nodes = [n for n in nodes.values() if "door" in (n.get("tags") or {})]
    entrance_nodes = [n for n in nodes.values() if "entrance" in (n.get("tags") or {})]

    def analyze(node_list, label):
        lines.append(f"### {label} — total {len(node_list)}")
        member_counts = Counter()
        isolated = 0
        by_level = Counter()
        for n in node_list:
            ways_containing = node_to_ways.get(n["id"], [])
            member_counts[len(ways_containing)] += 1
            if not ways_containing:
                isolated += 1
            lv = (n.get("tags") or {}).get("level")
            by_level[lv if lv is not None else "sin level"] += 1
        lines.append(f"- Distribucion de 'es miembro de N ways routeables': {dict(sorted(member_counts.items()))}")
        lines.append(f"- Aislados (miembro de 0 ways routeables): **{isolated}**")
        lines.append(f"- Por nivel: {dict(by_level)}")
        lines.append("")
        return member_counts, isolated

    analyze(door_nodes, "`door`")
    analyze(entrance_nodes, "`entrance`")

    return routable_ways, node_to_ways, door_nodes, entrance_nodes


def section_connectivity(ways, nodes, footway_indoor, corridor_lines, lines):
    lines.append("## 8. Conectividad (componentes conexas por nivel)\n")

    line_ways = footway_indoor + corridor_lines
    lines.append(f"Red horizontal analizada: {len(line_ways)} ways "
                 f"(`footway+indoor=yes` + `indoor=corridor`/`highway=corridor` abiertos).\n")

    by_level_ways = defaultdict(list)
    for w in line_ways:
        lv = (w.get("tags") or {}).get("level")
        by_level_ways[lv if lv is not None else "sin level"].append(w)

    lines.append("| level | # ways | # componentes conexas | tamano del componente mayor (nodos) |")
    lines.append("|---|---|---|---|")

    total_components_info = {}
    for lv, wlist in sorted(by_level_ways.items(), key=lambda x: str(x[0])):
        dsu = DSU()
        node_set = set()
        for w in wlist:
            node_ids = w.get("nodes") or []
            node_set.update(node_ids)
            for a, b in zip(node_ids[:-1], node_ids[1:]):
                dsu.union(a, b)
        comp_sizes = Counter()
        for n in node_set:
            comp_sizes[dsu.find(n)] += 1
        n_components = len(comp_sizes)
        largest = max(comp_sizes.values()) if comp_sizes else 0
        total_components_info[lv] = (n_components, largest, len(node_set))
        lines.append(f"| {lv} | {len(wlist)} | {n_components} | {largest} |")
    lines.append("")

    return by_level_ways


def section_dea_room(ways, nodes, door_nodes_ids_set, footway_indoor, corridor_lines, lines):
    lines.append("## 9. La sala del DEA — way 733736697 (indoor=room, level 0)\n")

    room = ways.get(WINNER_ROOM_ID)
    if room is None:
        lines.append(f"Way {WINNER_ROOM_ID} no encontrado en el dataset descargado (fuera del bbox o "
                     f"no era un way). No se puede completar esta seccion con el dataset actual.\n")
        return

    node_ids = room.get("nodes") or []
    lines.append(f"Way {WINNER_ROOM_ID}: tags={json.dumps(room.get('tags'), ensure_ascii=False)}")
    lines.append(f"Numero de nodos en el poligono: {len(node_ids)}\n")

    door_members = [nid for nid in node_ids if nid in door_nodes_ids_set]

    if door_members:
        lines.append(f"**a) Nodos `door` en el perimetro de la sala: {len(door_members)}**\n")
        for nid in door_members:
            n = nodes.get(nid, {})
            lines.append(f"- node {nid} — lat={n.get('lat')}, lon={n.get('lon')}, "
                         f"tags={json.dumps(n.get('tags'), ensure_ascii=False)}")
        lines.append("")

        lines.append("**b) ¿Ese door es tambien miembro de un footway+indoor o corridor?**\n")
        line_ways = footway_indoor + corridor_lines
        for nid in door_members:
            containing = [w["id"] for w in line_ways if nid in (w.get("nodes") or [])]
            if containing:
                lines.append(f"- node {nid}: SI, tambien es miembro de way(s) {containing} "
                             f"(footway/corridor) — confirma enganche sala->puerta->pasillo.")
            else:
                lines.append(f"- node {nid}: NO es miembro de ningun footway/corridor en este dataset.")
        lines.append("")
    else:
        lines.append("**a) La sala NO tiene ningun nodo `door` en su perimetro segun este dataset.**\n")

        lines.append("**c) Fallback — nodo routeable mas cercano al DEA por coordenada:**\n")
        aed = nodes.get(WINNER_AED_ID)
        if aed is None:
            lines.append(f"Nodo DEA {WINNER_AED_ID} no encontrado en el dataset descargado.\n")
        else:
            aed_pt = (aed["lat"], aed["lon"])
            candidates = []
            line_ways = footway_indoor + corridor_lines
            seen_ids = set()
            for w in line_ways:
                for nid in (w.get("nodes") or []):
                    if nid in seen_ids or nid not in nodes:
                        continue
                    seen_ids.add(nid)
                    n = nodes[nid]
                    if "lat" not in n:
                        continue
                    d = haversine_m(aed_pt, (n["lat"], n["lon"]))
                    candidates.append((d, nid, n))
            candidates.sort(key=lambda x: x[0])
            lines.append("| distancia (m) | node id | lat | lon |")
            lines.append("|---|---|---|---|")
            for d, nid, n in candidates[:5]:
                lines.append(f"| {d:.2f} | {nid} | {n['lat']} | {n['lon']} |")
            lines.append("")


def section_outdoor_hookup(nodes, footway_indoor, corridor_lines, entrance_nodes, lines):
    lines.append("## 10. Enganche outdoor — entrance miembro de way indoor routeable\n")

    line_ways = footway_indoor + corridor_lines
    node_to_ways = defaultdict(list)
    for w in line_ways:
        for nid in (w.get("nodes") or []):
            node_to_ways[nid].append(w["id"])

    hits = []
    for n in entrance_nodes:
        ways_containing = node_to_ways.get(n["id"], [])
        if ways_containing:
            hits.append((n, ways_containing))

    lines.append(f"Nodos `entrance` que son miembro de al menos un footway/corridor indoor: **{len(hits)}** "
                 f"de {len(entrance_nodes)}\n")

    if hits:
        lines.append("| node id | lat | lon | level | ways que lo contienen |")
        lines.append("|---|---|---|---|---|")
        for n, w_ids in hits[:20]:
            tags = n.get("tags") or {}
            lines.append(f"| {n['id']} | {n.get('lat')} | {n.get('lon')} | "
                         f"{tags.get('level')} | {w_ids} |")
        lines.append("")


def main() -> None:
    resp = download_or_load()
    elements, nodes, ways, relations = build_indices(resp)

    lines: list[str] = []
    lines.append("# Inventario exhaustivo — Hamburg Hbf (Fase 2a.2)\n")

    section_global(elements, nodes, ways, relations, lines)
    section_tag_catalog(nodes, ways, relations, lines)
    section_levels(nodes, ways, relations, lines)
    footway_indoor, corridor_lines = section_horizontal(ways, relations, nodes, lines)
    section_vertical(ways, nodes, lines)
    section_multilevel_structures(relations, lines)
    routable_ways, node_to_ways, door_nodes, entrance_nodes = section_doors(nodes, ways, relations, lines)
    section_connectivity(ways, nodes, footway_indoor, corridor_lines, lines)

    door_ids_set = {n["id"] for n in door_nodes}
    section_dea_room(ways, nodes, door_ids_set, footway_indoor, corridor_lines, lines)
    section_outdoor_hookup(nodes, footway_indoor, corridor_lines, entrance_nodes, lines)

    lines.append("## Datos disponibles no considerados hasta ahora\n")
    tag_keys = Counter()
    for coll in (nodes, ways, relations):
        for el in coll.values():
            for k in (el.get("tags") or {}):
                tag_keys[k] += 1
    interesting_unused = [
        k for k in tag_keys
        if k not in {
            "highway", "indoor", "level", "layer", "door", "entrance", "stairs",
            "conveying", "access", "name",
        }
    ]
    lines.append(
        "Claves de tag presentes que no se habian mencionado en fases anteriores "
        "(muestra, ver catalogo completo en seccion 2): " +
        ", ".join(f"`{k}`" for k in sorted(interesting_unused, key=lambda k: -tag_keys[k])[:25])
    )
    lines.append("")

    report = "\n".join(lines) + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nInforme guardado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()
