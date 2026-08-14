"""
Fase 0 — Investigación de datos indoor en OSM para AED Route Hamburg.

Script de usar-y-tirar. NO forma parte del deploy ni del repo de GitHub.
No modifica ningún módulo de src/aed_route ni app/. Reutiliza el cliente
Overpass existente (rotación de endpoints + backoff) vía
aed_route.io.call_overpass / resolve_hamburg_admin_relation_id.

Uso:
    .venv/bin/python scratch/investigate_indoor.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aed_route.io import call_overpass, resolve_hamburg_admin_relation_id  # noqa: E402
from aed_route.config import OVERPASS_QUERY_TIMEOUT_S  # noqa: E402

OUT_DIR = PROJECT_ROOT / "data" / "interim"
OUT_DIR.mkdir(parents=True, exist_ok=True)

POLITE_DELAY_S = 3.0  # extra pause between Overpass calls, on top of the client's own backoff

BBOXES = {
    "Hamburg Hauptbahnhof": (53.5515, 10.0035, 53.5545, 10.0095),
    "Hamburg Dammtor": (53.5600, 9.9880, 53.5617, 9.9910),
    "Hamburg-Harburg (estacion)": (53.4548, 9.9900, 53.4568, 9.9935),
    "Hamburg Airport (terminal)": (53.6285, 9.9960, 53.6320, 10.0060),
    "Europa-Passage (mall)": (53.5512, 9.9988, 53.5533, 10.0018),
    "AEZ Alstertal (mall)": (53.6476, 10.0965, 53.6497, 10.1008),
    "Elbe-EKZ Osdorf (mall)": (53.5734, 9.9088, 53.5755, 9.9128),
    "Universitat Hamburg": (53.5660, 9.9825, 53.5690, 9.9870),
}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug


# ── Parte 1 — DEA con datos indoor en Hamburgo ──────────────────────────


def fetch_all_hamburg_aeds(rel_id: int) -> list[dict]:
    query = f"""
    [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];
    relation({rel_id});
    map_to_area->.a;
    (
      node["emergency"="defibrillator"](area.a);
    );
    out tags center;
    """
    resp = call_overpass(query)
    return [el for el in (resp.get("elements") or []) if el.get("type") == "node"]


def summarize_aeds(elements: list[dict]) -> tuple[int, list[dict]]:
    total = len(elements)
    indoor_rows = []
    for el in elements:
        tags = el.get("tags") or {}
        indoor = tags.get("indoor")
        level = tags.get("level")
        if indoor is None and level is None:
            continue
        indoor_rows.append({
            "id": el.get("id"),
            "lat": el.get("lat"),
            "lon": el.get("lon"),
            "name": tags.get("name"),
            "indoor": indoor,
            "level": level,
            "access": tags.get("access"),
            "opening_hours": tags.get("opening_hours"),
        })
    return total, indoor_rows


# ── Parte 2 — Ranking de edificios candidatos ───────────────────────────


def fetch_building_probe(bbox: tuple[float, float, float, float]) -> dict:
    s, w, n, e = bbox
    bbox_str = f"{s},{w},{n},{e}"
    query = f"""
    [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];
    (
      nwr["indoor"~"^(room|area|corridor|level)$"]({bbox_str});
      way["highway"="corridor"]({bbox_str});
      way["highway"="footway"]["indoor"="yes"]({bbox_str});
      nwr["highway"="elevator"]({bbox_str});
      way["highway"="steps"]["level"]({bbox_str});
      nwr["stairs"="yes"]({bbox_str});
      node["door"]({bbox_str});
      node["entrance"]({bbox_str});
      node["emergency"="defibrillator"]({bbox_str});
    );
    out tags center;
    """
    return call_overpass(query)


def classify_building(resp: dict) -> dict:
    elements = resp.get("elements") or []

    vertical = 0
    horizontal = 0
    doors = 0
    entrances = 0
    rooms_areas = 0
    indoor_levels = 0
    aeds = 0
    aeds_indoor = 0

    for el in elements:
        tags = el.get("tags") or {}
        indoor = tags.get("indoor")
        highway = tags.get("highway")

        is_elevator = highway == "elevator"
        is_steps_with_level = highway == "steps" and "level" in tags
        is_stairs = tags.get("stairs") == "yes"
        is_vertical = is_elevator or is_steps_with_level or is_stairs

        is_indoor_corridor = indoor == "corridor" or highway == "corridor"
        is_footway_indoor = highway == "footway" and indoor == "yes"
        is_horizontal = is_indoor_corridor or is_footway_indoor

        is_room_area = indoor in ("room", "area")
        is_indoor_level = indoor == "level"
        is_door = "door" in tags
        is_entrance = "entrance" in tags
        is_aed = tags.get("emergency") == "defibrillator"

        if is_vertical:
            vertical += 1
        if is_horizontal:
            horizontal += 1
        if is_room_area:
            rooms_areas += 1
        if is_indoor_level:
            indoor_levels += 1
        if is_door:
            doors += 1
        if is_entrance:
            entrances += 1
        if is_aed:
            aeds += 1
            if indoor is not None or tags.get("level") is not None:
                aeds_indoor += 1

    score = (
        5 * vertical
        + 2 * horizontal
        + 1 * (doors + entrances)
        + 1 * (rooms_areas + indoor_levels)
        + (50 if aeds_indoor > 0 else 0)
    )

    viable = horizontal >= 1 and vertical >= 1 and entrances >= 1

    return {
        "n_elements": len(elements),
        "vertical": vertical,
        "horizontal": horizontal,
        "doors": doors,
        "entrances": entrances,
        "rooms_areas": rooms_areas,
        "indoor_levels": indoor_levels,
        "aeds": aeds,
        "aeds_indoor": aeds_indoor,
        "score": score,
        "viable": viable,
    }


# ── Main ─────────────────────────────────────────────────────────────


def main() -> None:
    report_lines: list[str] = []
    report_lines.append("# Investigacion datos indoor OSM — Hamburgo (Fase 0)\n")

    # Parte 1
    print("Resolviendo relation id de Hamburgo...")
    rel_id = resolve_hamburg_admin_relation_id()
    print(f"  relation id = {rel_id}")

    print("Descargando todos los DEA de Hamburgo...")
    aed_elements = fetch_all_hamburg_aeds(rel_id)
    total, indoor_rows = summarize_aeds(aed_elements)
    print(f"  total DEA = {total}, con indoor/level = {len(indoor_rows)}")

    report_lines.append("## Parte 1 — DEA en Hamburgo\n")
    report_lines.append(f"- Relation id resuelto: **{rel_id}**")
    report_lines.append(f"- Total DEA descargados de Overpass: **{total}** "
                         f"(cache local del proyecto: ~139-141)")
    report_lines.append(f"- DEA con tag `indoor` o `level`: **{len(indoor_rows)}**\n")

    if indoor_rows:
        report_lines.append(
            "| id | lat | lon | name | indoor | level | access | opening_hours |"
        )
        report_lines.append(
            "|---|---|---|---|---|---|---|---|"
        )
        for r in indoor_rows:
            report_lines.append(
                f"| {r['id']} | {r['lat']} | {r['lon']} | {r['name']} | "
                f"{r['indoor']} | {r['level']} | {r['access']} | {r['opening_hours']} |"
            )
    else:
        report_lines.append("Ningun DEA en Hamburgo tiene tag `indoor` ni `level`.")

    report_lines.append("")

    # Parte 2
    report_lines.append("## Parte 2 — Ranking de edificios candidatos\n")
    report_lines.append(
        "| Edificio | elementos | vertical | horizontal | doors | entrances | "
        "rooms/areas | indoor=level | DEA | DEA indoor | score | viable |"
    )
    report_lines.append(
        "|---|---|---|---|---|---|---|---|---|---|---|---|"
    )

    results = {}
    bbox_items = list(BBOXES.items())
    for i, (name, bbox) in enumerate(bbox_items):
        print(f"Consultando Overpass para: {name} ...")
        resp = fetch_building_probe(bbox)
        stats = classify_building(resp)
        stats["raw"] = resp
        results[name] = stats

        report_lines.append(
            f"| {name} | {stats['n_elements']} | {stats['vertical']} | "
            f"{stats['horizontal']} | {stats['doors']} | {stats['entrances']} | "
            f"{stats['rooms_areas']} | {stats['indoor_levels']} | {stats['aeds']} | "
            f"{stats['aeds_indoor']} | {stats['score']} | "
            f"{'si' if stats['viable'] else 'no'} |"
        )

        if i < len(bbox_items) - 1:
            time.sleep(POLITE_DELAY_S)

    # Ganador: mayor score entre los viables; si ninguno es viable, mayor score general
    viable_results = {k: v for k, v in results.items() if v["viable"]}
    pool = viable_results if viable_results else results
    winner_name = max(pool, key=lambda k: pool[k]["score"])
    winner = results[winner_name]

    slug = slugify(winner_name)
    probe_path = OUT_DIR / f"indoor_probe_{slug}.json"
    probe_path.write_text(
        json.dumps(winner["raw"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines.append("")
    report_lines.append("## Conclusion\n")
    report_lines.append(f"**Mejor candidato: {winner_name}** (score={winner['score']}, "
                         f"viable={'si' if winner['viable'] else 'no'})")
    report_lines.append(
        f"- Vias horizontales indoor: {winner['horizontal']}, "
        f"conexiones verticales: {winner['vertical']}, "
        f"entradas: {winner['entrances']}, puertas: {winner['doors']}"
    )
    if winner["aeds_indoor"] > 0:
        report_lines.append(
            f"- Tiene **{winner['aeds_indoor']}** DEA mapeado(s) con tag indoor/level "
            f"dentro del bbox consultado."
        )
    elif winner["aeds"] > 0:
        report_lines.append(
            f"- Hay {winner['aeds']} DEA dentro del bbox, pero ninguno tiene tag "
            f"indoor/level."
        )
    else:
        report_lines.append("- No hay ningun DEA mapeado dentro de este bbox.")
    report_lines.append(f"- Respuesta Overpass cruda guardada en: `{probe_path}`")

    report_md = "\n".join(report_lines) + "\n"
    report_path = PROJECT_ROOT / "scratch" / "indoor_investigation_report.md"
    report_path.write_text(report_md, encoding="utf-8")

    print("\n" + "=" * 60)
    print(report_md)
    print("=" * 60)
    print(f"\nInforme guardado en: {report_path}")
    print(f"Probe crudo del ganador guardado en: {probe_path}")


if __name__ == "__main__":
    main()
