"""
Fase 2a — Caracterizacion de datos indoor de Hamburg Hauptbahnhof.

Script de usar-y-tirar, SOLO LECTURA. No usa red, no toca src/aed_route
ni app/. Lee unicamente data/interim/indoor_probe_hamburg_hauptbahnhof.json
(generado en la Fase 0) y produce un informe Markdown.

Uso:
    .venv/bin/python scratch/characterize_hbf_indoor.py
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = PROJECT_ROOT / "data" / "interim" / "indoor_probe_hamburg_hauptbahnhof.json"
WINNER_AED_ID = 13948102741

LEVEL_KEYS = ["level", "repeat_on", "level:ref", "min_level", "max_level"]


def load_elements() -> list[dict]:
    data = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    return data.get("elements") or []


def lat_lon(el: dict) -> tuple[float, float] | None:
    if el["type"] == "node":
        return el.get("lat"), el.get("lon")
    center = el.get("center")
    if center:
        return center.get("lat"), center.get("lon")
    return None


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
    if re.fullmatch(r"-?\d+", raw):
        return "entero"
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return "decimal"
    if re.fullmatch(r"-?\d+\s*-\s*-?\d+", raw):
        return "rango"
    if ";" in raw:
        return "lista"
    return "otro/no-numerico"


def section_levels(els: list[dict], lines: list[str]) -> None:
    lines.append("## 1. Niveles (`level` y tags relacionados)\n")

    per_key_values: dict[str, Counter] = {k: Counter() for k in LEVEL_KEYS}
    per_key_class: dict[str, Counter] = {k: Counter() for k in LEVEL_KEYS}
    layer_and_level = 0
    layer_no_level = 0
    level_no_layer = 0
    layer_diff_from_level_examples = []

    for el in els:
        tags = el.get("tags") or {}
        for k in LEVEL_KEYS:
            if k in tags:
                v = str(tags[k])
                per_key_values[k][v] += 1
                per_key_class[k][classify_level_value(v)] += 1

        has_layer = "layer" in tags
        has_level = "level" in tags
        if has_layer and has_level:
            layer_and_level += 1
            if str(tags["layer"]) != str(tags["level"]):
                if len(layer_diff_from_level_examples) < 5:
                    layer_diff_from_level_examples.append(
                        (el["type"], el.get("id"), tags.get("layer"), tags.get("level"),
                         tags.get("highway") or tags.get("indoor"))
                    )
        elif has_layer and not has_level:
            layer_no_level += 1
        elif has_level and not has_layer:
            level_no_layer += 1

    for k in LEVEL_KEYS:
        n = sum(per_key_values[k].values())
        lines.append(f"### `{k}` — presente en {n} elementos")
        if n == 0:
            lines.append("No aparece en el dataset.\n")
            continue
        lines.append(f"Clasificacion de valores: {dict(per_key_class[k])}")
        top = per_key_values[k].most_common(15)
        lines.append("Valores distintos (top 15, con conteo): " +
                      ", ".join(f"`{v}`={c}" for v, c in top))
        lines.append("")

    lines.append("### `layer` vs `level`")
    lines.append(f"- Elementos con AMBOS `layer` y `level`: **{layer_and_level}**")
    lines.append(f"- Elementos con `layer` pero SIN `level`: **{layer_no_level}**")
    lines.append(f"- Elementos con `level` pero SIN `layer`: **{level_no_layer}**")
    if layer_diff_from_level_examples:
        lines.append(
            "- Casos donde `layer` != `level` en el mismo elemento (posible fuente de "
            "confusion — `layer` es orden de dibujo/apilado, no piso fisico):"
        )
        for typ, eid, layer_v, level_v, ctx in layer_diff_from_level_examples:
            lines.append(f"  - {typ} {eid}: layer=`{layer_v}`, level=`{level_v}` (tag principal: `{ctx}`)")
    else:
        lines.append(
            "- No se encontraron casos donde `layer` y `level` coincidan como claves pero "
            "difieran en valor dentro de los primeros ejemplos revisados; aun asi ambos "
            "tags coexisten con frecuencia y representan conceptos distintos en OSM "
            "(`layer` = orden de renderizado/apilamiento en cruces, no numero de planta)."
        )
    lines.append("")


def section_horizontal(els: list[dict], lines: list[str]) -> None:
    lines.append("## 2. Vias horizontales: lineas vs areas\n")

    corridor_ways = []
    footway_indoor_ways = []
    indoor_area_polys = []  # indoor=area/room, way or relation
    indoor_corridor_tag = []  # indoor=corridor (could be way tagged both ways)

    by_type_tag = Counter()

    for el in els:
        tags = el.get("tags") or {}
        indoor = tags.get("indoor")
        highway = tags.get("highway")

        if highway == "corridor":
            corridor_ways.append(el)
            by_type_tag[(el["type"], "highway=corridor")] += 1
        if highway == "footway" and indoor == "yes":
            footway_indoor_ways.append(el)
            by_type_tag[(el["type"], "highway=footway+indoor=yes")] += 1
        if indoor == "corridor":
            indoor_corridor_tag.append(el)
            by_type_tag[(el["type"], "indoor=corridor")] += 1
        if indoor in ("area", "room"):
            indoor_area_polys.append(el)
            by_type_tag[(el["type"], f"indoor={indoor}")] += 1

    lines.append(f"- `highway=corridor` (ways = lineas navegables): **{len(corridor_ways)}**")
    lines.append(f"- `highway=footway` + `indoor=yes` (ways = lineas navegables): **{len(footway_indoor_ways)}**")
    lines.append(f"- `indoor=corridor` como tag principal (sin `highway=corridor`, "
                  f"suele ser poligono de pasillo): **{len(indoor_corridor_tag)}**")
    lines.append(f"- `indoor=area` / `indoor=room` (poligonos de sala/area, NO lineas navegables): "
                  f"**{len(indoor_area_polys)}**\n")

    lines.append("Desglose por tipo de elemento OSM y tag:")
    lines.append("")
    lines.append("| tipo | tag | conteo |")
    lines.append("|---|---|---|")
    for (typ, tag), c in sorted(by_type_tag.items(), key=lambda x: -x[1]):
        lines.append(f"| {typ} | {tag} | {c} |")
    lines.append("")

    total_line_like = len(corridor_ways) + len(footway_indoor_ways)
    total_area_like = len(indoor_area_polys) + len(indoor_corridor_tag)
    lines.append(
        f"**Conclusion de la seccion:** hay **{total_line_like}** elementos tipo *linea navegable* "
        f"(`highway=corridor` o `footway`+`indoor=yes`) y **{total_area_like}** elementos tipo "
        f"*poligono* (`indoor=area/room/corridor`). Ambos coexisten en este dataset — el routing "
        f"indoor de Hbf no puede basarse solo en lineas: una parte relevante del espacio (salas, "
        f"vestibulos, la 'Galerie') solo esta mapeada como poligono sin una linea de centro "
        f"explicita.\n"
    )

    if corridor_ways:
        lines.append("Ejemplo `highway=corridor`:")
        lines.append(f"```json\n{json.dumps(corridor_ways[0], indent=2, ensure_ascii=False)}\n```\n")
    if indoor_area_polys:
        lines.append("Ejemplo `indoor=area`/`indoor=room`:")
        lines.append(f"```json\n{json.dumps(indoor_area_polys[0], indent=2, ensure_ascii=False)}\n```\n")


def section_vertical(els: list[dict], lines: list[str]) -> None:
    lines.append("## 3. Conexiones verticales\n")

    cats = {
        "highway=steps": [],
        "highway=elevator": [],
        "conveying=yes (escaleras mecanicas / cinta)": [],
        "stairs=yes": [],
    }

    for el in els:
        tags = el.get("tags") or {}
        highway = tags.get("highway")
        if highway == "steps":
            cats["highway=steps"].append(el)
        if highway == "elevator":
            cats["highway=elevator"].append(el)
        if tags.get("conveying") == "yes":
            cats["conveying=yes (escaleras mecanicas / cinta)"].append(el)
        if tags.get("stairs") == "yes":
            cats["stairs=yes"].append(el)

    for label, elements in cats.items():
        by_type = Counter(e["type"] for e in elements)
        lines.append(f"### {label} — total {len(elements)}, por tipo: {dict(by_type)}")
        if not elements:
            lines.append("No aparece en el dataset.\n")
            continue

        level_shapes = Counter()
        for e in elements:
            lv = (e.get("tags") or {}).get("level")
            if lv is None:
                level_shapes["sin level"] += 1
            else:
                level_shapes[classify_level_value(str(lv))] += 1
        lines.append(f"Forma del tag `level` en estos elementos: {dict(level_shapes)}")

        lines.append("Ejemplos:")
        for e in elements[:3]:
            lines.append(f"```json\n{json.dumps(e, indent=2, ensure_ascii=False)}\n```")
        lines.append("")


def section_connectivity(els: list[dict], lines: list[str]) -> None:
    lines.append("## 4. Conectividad\n")

    ways_no_geom = sum(1 for e in els if e["type"] == "way" and "nodes" not in e and "geometry" not in e)
    lines.append(
        f"**Limitacion importante del dataset actual:** la query de la Fase 0 uso "
        f"`out tags center;`, que devuelve solo tags + un punto centroide para ways y "
        f"relations — **no incluye la lista de nodos que componen cada way** "
        f"({ways_no_geom} de {sum(1 for e in els if e['type']=='way')} ways sin `nodes`/`geometry`). "
        f"Por tanto, **no es posible verificar desde este JSON si dos corridors/footways "
        f"comparten un nodo real** (topologia navegable en el sentido de grafo). Para "
        f"confirmarlo se necesitaria re-descargar con `out geom;` o `out body; >; out skel qt;` "
        f"y comparar IDs de nodo compartidos entre ways. Esto es un requisito a resolver "
        f"antes de diseñar el parser — no se puede asumir conectividad de grafo solo con "
        f"centroides.\n"
    )

    node_tags = [e for e in els if e["type"] == "node"]
    door_nodes = [e for e in node_tags if "door" in (e.get("tags") or {})]
    entrance_nodes = [e for e in node_tags if "entrance" in (e.get("tags") or {})]

    lines.append(f"- Nodos con tag `door`: **{len(door_nodes)}**")
    lines.append(f"- Nodos con tag `entrance`: **{len(entrance_nodes)}**")

    # Proximity check: for each door/entrance node, find nearest way/relation centroid
    routable_els = [
        e for e in els
        if e["type"] in ("way", "relation")
        and (
            (e.get("tags") or {}).get("highway") in ("corridor", "footway", "steps", "elevator")
            or (e.get("tags") or {}).get("indoor") in ("corridor", "area", "room")
        )
    ]

    def nearest_dist(node_el):
        p = lat_lon(node_el)
        if p is None or p[0] is None:
            return None
        best = None
        for r in routable_els:
            rp = lat_lon(r)
            if rp is None or rp[0] is None:
                continue
            d = haversine_m(p, rp)
            if best is None or d < best:
                best = d
        return best

    close_doors = sum(1 for n in door_nodes if (d := nearest_dist(n)) is not None and d <= 15)
    close_entr = sum(1 for n in entrance_nodes if (d := nearest_dist(n)) is not None and d <= 15)

    lines.append(
        f"- De los {len(door_nodes)} nodos `door`, **{close_doors}** estan a <=15 m del "
        f"centroide de alguna via/area indoor routeable (proxy grosero de 'sobre la via', "
        f"ya que no tenemos geometria exacta de las ways)."
    )
    lines.append(
        f"- De los {len(entrance_nodes)} nodos `entrance`, **{close_entr}** estan a <=15 m "
        f"del centroide de alguna via/area indoor routeable.\n"
    )

    lines.append(
        "Nota: estos nodos `door`/`entrance` **no tienen coordenadas del way al que "
        "pertenecen** — son nodos independientes con lat/lon propio; en el modelo OSM real "
        "suelen estar insertados como vertices de un way de edificio o de un corridor, pero "
        "eso solo se confirma con la lista completa de nodos del way (ver limitacion arriba).\n"
    )

    lines.append("### Entradas por nivel")
    entr_by_level = Counter()
    for e in entrance_nodes:
        lv = (e.get("tags") or {}).get("level")
        entr_by_level[lv if lv is not None else "sin level"] += 1
    lines.append("| level | # entradas |")
    lines.append("|---|---|")
    for lv, c in sorted(entr_by_level.items(), key=lambda x: (str(x[0]))):
        lines.append(f"| {lv} | {c} |")
    lines.append("")
    lines.append(
        f"La mayoria de nodos `entrance` **no llevan tag `level` propio** — el nivel al que "
        f"da una entrada normalmente se infiere del way de edificio en el que esta insertada, "
        f"no del nodo mismo. Con los datos actuales (sin membership de ways) no podemos "
        f"asignar con certeza cuantas entradas dan a level 0 vs otros niveles.\n"
    )


def section_access(els: list[dict], lines: list[str]) -> None:
    lines.append("## 5. Valores de `access`\n")

    indoor_routable = [
        e for e in els
        if (e.get("tags") or {}).get("highway") in ("corridor", "footway", "steps", "elevator")
        or (e.get("tags") or {}).get("indoor") in ("corridor", "area", "room", "yes")
    ]

    access_counts = Counter((e.get("tags") or {}).get("access") for e in indoor_routable)
    lines.append(f"Sobre {len(indoor_routable)} elementos indoor/routeables relevantes:\n")
    lines.append("| access | conteo |")
    lines.append("|---|---|")
    for v, c in access_counts.most_common():
        lines.append(f"| {v if v is not None else '(sin tag)'} | {c} |")
    lines.append("")

    no_private = sum(1 for v in access_counts if v in ("no", "private"))
    n_excluded = sum(c for v, c in access_counts.items() if v in ("no", "private"))
    lines.append(
        f"- Elementos con `access=no` o `access=private`: **{n_excluded}** de {len(indoor_routable)}. "
        f"Con el filtro actual del proyecto (`access!~no|private` aplicado a las 3 redes de "
        f"calle), estos quedarian excluidos tambien dentro del edificio si se reutiliza la "
        f"misma regla para indoor."
    )
    lines.append("")


def section_winner_aed(els: list[dict], lines: list[str]) -> None:
    lines.append("## 6. El DEA ganador (nodo 13948102741)\n")

    aed = next((e for e in els if e["type"] == "node" and e.get("id") == WINNER_AED_ID), None)
    if aed is None:
        lines.append(f"No se encontro el nodo {WINNER_AED_ID} en el JSON.\n")
        return

    lines.append("Tags completos:")
    lines.append(f"```json\n{json.dumps(aed, indent=2, ensure_ascii=False)}\n```\n")

    tags = aed.get("tags") or {}
    lines.append(f"- `level` = `{tags.get('level')}`")
    lines.append(f"- `indoor` = `{tags.get('indoor')}`")
    lines.append(f"- `defibrillator:location` (texto libre) = \"{tags.get('defibrillator:location')}\"")

    aed_pt = lat_lon(aed)

    candidates = []
    for e in els:
        if e is aed:
            continue
        etags = e.get("tags") or {}
        is_routable = (
            etags.get("highway") in ("corridor", "footway", "steps", "elevator")
            or etags.get("indoor") in ("corridor", "area", "room")
            or "door" in etags
            or "entrance" in etags
        )
        if not is_routable:
            continue
        p = lat_lon(e)
        if p is None or p[0] is None:
            continue
        d = haversine_m(aed_pt, p)
        candidates.append((d, e))

    candidates.sort(key=lambda x: x[0])

    lines.append("\nElementos routeables/indoor mas cercanos (por distancia al centroide, "
                  "linea recta, no por red):\n")
    lines.append("| distancia (m) | tipo | id | tag principal | level |")
    lines.append("|---|---|---|---|---|")
    for d, e in candidates[:8]:
        etags = e.get("tags") or {}
        main_tag = etags.get("highway") or etags.get("indoor") or (
            "door" if "door" in etags else "entrance" if "entrance" in etags else "?"
        )
        lines.append(f"| {d:.1f} | {e['type']} | {e.get('id')} | {main_tag} | {etags.get('level')} |")
    lines.append("")

    if candidates:
        d0, e0 = candidates[0]
        lines.append(
            f"El elemento routeable/indoor mas cercano es {e0['type']} `{e0.get('id')}` "
            f"a **{d0:.1f} m** (distancia recta centroide-a-punto, no de red) con "
            f"level=`{(e0.get('tags') or {}).get('level')}`. El DEA esta en level=`{tags.get('level')}`; "
            f"{'coincide' if str((e0.get('tags') or {}).get('level')) == str(tags.get('level')) else 'NO coincide'} "
            f"con el nivel del elemento mas cercano — a verificar manualmente antes de asumir "
            f"que es el punto de enganche correcto, dado que la distancia es centroide-a-centroide "
            f"(los ways no tienen geometria completa en este dataset, ver seccion 4)."
        )
    lines.append("")


def main() -> None:
    els = load_elements()
    lines: list[str] = []
    lines.append("# Caracterizacion de datos indoor — Hamburg Hauptbahnhof (Fase 2a)\n")
    lines.append(f"Fuente: `{PROBE_PATH.relative_to(PROJECT_ROOT)}` — {len(els)} elementos "
                  f"({sum(1 for e in els if e['type']=='node')} nodes, "
                  f"{sum(1 for e in els if e['type']=='way')} ways, "
                  f"{sum(1 for e in els if e['type']=='relation')} relations).\n")

    section_levels(els, lines)
    section_horizontal(els, lines)
    section_vertical(els, lines)
    section_connectivity(els, lines)
    section_access(els, lines)
    section_winner_aed(els, lines)

    report = "\n".join(lines) + "\n"
    out_path = PROJECT_ROOT / "scratch" / "hbf_indoor_characterization.md"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nInforme guardado en: {out_path}")


if __name__ == "__main__":
    main()
