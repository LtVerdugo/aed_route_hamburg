"""
Fase 3 — Re-extraccion limpia de Hbf (sin relations type=route) + inspeccion
del nodo 6872081573 (la "puerta" que aparece en indoorequal cerca de la DB
Lounge). Script de usar-y-tirar. NO modifica src/aed_route ni app/.
Reutiliza el cliente Overpass del proyecto.

Uso:
    .venv/bin/python scratch/reextract_hbf_clean.py
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

OLD_ISOLATED_JSON = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_isolated.json"
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_clean_v2.json"

BBOX = "53.5505,10.0025,53.5560,10.0110"
TARGET_NODE_ID = 6872081573

QUERY = f"""
[out:json][timeout:180];
(
  nwr["level"]({BBOX});
  node["door"]({BBOX});
  node["entrance"]({BBOX});
)->.sel;
(.sel; .sel >;);
out body qt;
"""


# ── Parte 1 — re-extraccion ──────────────────────────────────────────


def download_or_load():
    if OUT_PATH.exists():
        print(f"Ya existe {OUT_PATH}, no se vuelve a descargar.")
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))

    print("Consultando Overpass — re-extraccion limpia de Hbf (sin type=route)...")
    resp = call_overpass(QUERY)
    OUT_PATH.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    return resp


def build_indices(resp):
    elements = resp.get("elements") or []
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
    return elements, nodes, ways, relations


# ── Parte 2 — inspeccion del nodo 6872081573 ──────────────────────────


def fetch_single_node(node_id: int) -> dict | None:
    query = f"""
    [out:json][timeout:30];
    node({node_id});
    out tags;
    """
    resp = call_overpass(query)
    elements = resp.get("elements") or []
    return elements[0] if elements else None


def node_in_old_isolated(node_id: int) -> tuple[bool, bool]:
    """Returns (present_as_own_node, present_as_way_member)."""
    data = json.loads(OLD_ISOLATED_JSON.read_text(encoding="utf-8"))
    elements = data.get("elements") or []
    present_as_node = any(e.get("type") == "node" and e.get("id") == node_id for e in elements)
    present_as_member = any(
        e.get("type") == "way" and node_id in (e.get("nodes") or [])
        for e in elements
    )
    return present_as_node, present_as_member


def find_ways_containing(node_id: int, ways: dict) -> list[dict]:
    return [w for w in ways.values() if node_id in (w.get("nodes") or [])]


def main():
    resp = download_or_load()
    elements, nodes, ways, relations = build_indices(resp)

    route_rels = [r for r in relations.values() if (r.get("tags") or {}).get("type") == "route"]

    print("=" * 60)
    print("PARTE 1 — Re-extraccion limpia")
    print("=" * 60)
    print(f"Archivo: {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    print(f"Nodes: {len(nodes)}, Ways: {len(ways)}, Relations: {len(relations)}")
    print(f"Total elementos crudos: {len(elements)}")
    if route_rels:
        print(f"ALERTA: {len(route_rels)} relations type=route SIGUEN apareciendo: " +
              ", ".join(str(r['id']) for r in route_rels))
    else:
        print("CONFIRMADO: 0 relations type=route.")

    door_nodes = [n for n in nodes.values()
                  if "door" in (n.get("tags") or {}) or (n.get("tags") or {}).get("indoor") == "door"]
    entrance_nodes = [n for n in nodes.values() if "entrance" in (n.get("tags") or {})]
    print(f"\nPuertas (door=* o indoor=door): {len(door_nodes)}")
    print(f"Entradas (entrance=*): {len(entrance_nodes)}")

    print()
    print("=" * 60)
    print(f"PARTE 2 — Nodo {TARGET_NODE_ID}")
    print("=" * 60)

    target = nodes.get(TARGET_NODE_ID)
    fetched_directly = False
    if target is None:
        print(f"No estaba en la re-extraccion; consultando directamente node({TARGET_NODE_ID})...")
        target = fetch_single_node(TARGET_NODE_ID)
        fetched_directly = True

    if target is None:
        print(f"El nodo {TARGET_NODE_ID} no existe en OSM (o Overpass no lo devolvio).")
    else:
        tags = target.get("tags") or {}
        print(f"Encontrado {'via query directa' if fetched_directly else 'en la re-extraccion'}.")
        print(f"lat={target.get('lat')}, lon={target.get('lon')}")
        print(f"Tags completos: {json.dumps(tags, indent=2, ensure_ascii=False)}")

        print()
        is_door = "door" in tags or tags.get("indoor") == "door"
        is_entrance = "entrance" in tags
        print(f"¿door=* o entrance=*? door={'si, valor=' + tags.get('door', tags.get('indoor','?')) if is_door else 'no'}, "
              f"entrance={'si, valor=' + tags['entrance'] if is_entrance else 'no'}")

        own_level = tags.get("level")
        print(f"¿Tiene level propio? {'si, level=' + own_level if own_level else 'NO'}")

        containing_ways = find_ways_containing(TARGET_NODE_ID, ways) if not fetched_directly else []
        if not fetched_directly:
            if not own_level and containing_ways:
                print("Es vertice de estos ways (con su level):")
                for w in containing_ways:
                    print(f"  way {w['id']} tags={w.get('tags')}")
            elif not own_level:
                print("No es vertice de ningun way en la re-extraccion (nivel realmente desconocido).")

            room_ways = [w for w in containing_ways
                         if (w.get("tags") or {}).get("indoor") in ("room", "area", "corridor")]
            if room_ways:
                print("Pertenece al perimetro de estas salas/tiendas:")
                for w in room_ways:
                    t = w.get("tags") or {}
                    print(f"  way {w['id']} name={t.get('name')} indoor={t.get('indoor')} level={t.get('level')}")
            else:
                print("No es vertice de ninguna sala/tienda (indoor=room/area/corridor) en la re-extraccion.")
        else:
            print("(no se puede determinar membership de ways sin la re-extraccion completa "
                  "— este nodo no aparecio en ella)")

        was_present, was_member = node_in_old_isolated(TARGET_NODE_ID)
        print(f"\n¿Estaba en hbf_indoor_isolated.json (Fase 2c)? "
              f"como nodo propio={was_present}, como miembro de algun way={was_member}")

    print(f"\nDatos guardados en: {OUT_PATH}")


if __name__ == "__main__":
    main()
