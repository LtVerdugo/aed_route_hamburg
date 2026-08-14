"""
Fase 3 (visor) — Genera un HTML autocontenido para inspeccionar visualmente
el grafo indoor de Hbf (nodos, aristas, conectores verticales, salas, DEA)
con selector de nivel, estilo OpenLevelUp/indoorequal.

Script de usar-y-tirar, SOLO LECTURA. NO modifica src/aed_route ni app/.
Lee data/interim/hbf_indoor_graph.pkl (grafo del paso 1 de Fase 3) para
nodos/aristas/conectores verticales (sin cambios), y
data/interim/hbf_indoor_clean_v2.json (re-extraccion limpia sin
relations type=route, con TODAS las puertas/entradas sin filtro de
level) para salas, puertas y entradas — con fallback a
hbf_indoor_isolated.json si el archivo limpio aun no existe. No usa red
durante la ejecucion del script — el HTML resultante si carga Leaflet y
el basemap desde CDN al abrirlo en un navegador, igual que el resto del
proyecto.

Uso:
    .venv/bin/python scratch/build_indoor_viewer.py
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import aed_route.indoor as indoor_mod  # noqa: E402
from aed_route.indoor import _load_isolated, locate_dea_anchor  # noqa: E402
from shapely.geometry import LineString, Point  # noqa: E402

GRAPH_PKL = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_graph.pkl"
ISOLATED_JSON = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_isolated.json"
CLEAN_V2_JSON = PROJECT_ROOT / "data" / "interim" / "hbf_indoor_clean_v2.json"
DB_LOUNGE_BUFFER_JSON = PROJECT_ROOT / "data" / "interim" / "db_lounge_buffer.json"
OUT_HTML = PROJECT_ROOT / "scratch" / "hbf_indoor_viewer.html"

# Rooms/doors/entrances now come from the richer, route-relation-free
# re-extraction (Fase 3, hbf_indoor_clean_v2.json) which explicitly queries
# door/entrance nodes independent of the `level` filter. NODES/EDGES/
# VERTICAL_CONNECTORS still come from the pkl graph (unchanged — rebuilding
# the routing graph is out of scope for this viewer-only phase).
ROOMS_DOORS_SOURCE = CLEAN_V2_JSON if CLEAN_V2_JSON.exists() else ISOLATED_JSON

WINNER_AED_ID = 13948102741

_VERTICAL_KIND_LABEL = {"steps": "stairs", "elevator": "elevator", "conveying": "escalator"}


class _RemapUnpickler(pickle.Unpickler):
    """
    The graph pkl was produced by running `python -m aed_route.indoor`
    directly, so IndoorRoom got pickled as `__main__.IndoorRoom` instead of
    `aed_route.indoor.IndoorRoom`. Remap on load instead of touching
    indoor.py or re-running the build.
    """
    def find_class(self, module, name):
        if module == "__main__":
            module = "aed_route.indoor"
        return super().find_class(module, name)


def load_graph_bundle():
    with GRAPH_PKL.open("rb") as f:
        return _RemapUnpickler(f).load()


# ── Extraccion ───────────────────────────────────────────────────────


def classify_node_type(G, node_key, data):
    if data.get("node_type") == "aed":
        return "aed"
    for _, _, ed in G.edges(node_key, data=True):
        if ed.get("kind") == "horizontal":
            return "footway"
    return "ancla_vertical"


def export_nodes(G):
    nodes = []
    for key, data in G.nodes(data=True):
        if data.get("lon") is None or data.get("lat") is None:
            continue
        nodes.append({
            "node_key": key,
            "level": data.get("level"),
            "lon": data["lon"],
            "lat": data["lat"],
            "tipo": classify_node_type(G, key, data),
        })
    return nodes


def export_horizontal_edges(G):
    edges = []
    for u, v, k, ed in G.edges(keys=True, data=True):
        if ed.get("kind") != "horizontal":
            continue
        geom = ed.get("geometry")
        if geom is None:
            continue
        edges.append({
            "level": ed.get("level"),
            "cost_s": ed.get("cost_s"),
            "coords": [[float(c[0]), float(c[1])] for c in geom.coords],
        })
    return edges


def export_vertical_connectors(G):
    groups = {}
    for u, v, ed in G.edges(data=True):
        kind = ed.get("kind")
        if kind not in _VERTICAL_KIND_LABEL:
            continue
        source_id = ed.get("source_id")
        group_key = (kind, source_id)
        if group_key not in groups:
            u_data = G.nodes[u]
            groups[group_key] = {
                "tipo": _VERTICAL_KIND_LABEL[kind],
                "levels": set(),
                "lon": u_data.get("lon"),
                "lat": u_data.get("lat"),
                "source_id": source_id,
            }
        groups[group_key]["levels"].add(ed.get("level_from"))
        groups[group_key]["levels"].add(ed.get("level_to"))

    connectors = []
    for info in groups.values():
        if info["lon"] is None:
            continue
        connectors.append({
            "tipo": info["tipo"],
            "levels": sorted(info["levels"]),
            "lon": info["lon"],
            "lat": info["lat"],
            "source_id": info["source_id"],
        })
    return connectors


def _polygon_rings(polygon):
    """Shapely (Multi)Polygon -> list of [ [ [lon,lat], ... ], ... ] (one entry per part)."""
    if polygon is None or polygon.is_empty:
        return []
    geoms = list(polygon.geoms) if polygon.geom_type == "MultiPolygon" else [polygon]
    parts = []
    for g in geoms:
        exterior = [[float(x), float(y)] for x, y in g.exterior.coords]
        interiors = [[[float(x), float(y)] for x, y in ring.coords] for ring in g.interiors]
        parts.append({"exterior": exterior, "interiors": interiors})
    return parts


def _build_node_to_room_map(nodes: dict, ways: dict) -> dict[int, dict]:
    """node id -> {room_id, room_name} for nodes sitting on a room/area/corridor perimeter."""
    node_to_room = {}
    for way in ways.values():
        tags = way.get("tags") or {}
        if tags.get("indoor") not in ("room", "area", "corridor"):
            continue
        for nid in (way.get("nodes") or []):
            # first match wins; a node is rarely shared by two rooms
            node_to_room.setdefault(nid, {"room_id": way["id"], "room_name": tags.get("name")})
    return node_to_room


def export_doors_and_entrances():
    """
    Doors (door=* or indoor=door) and entrances (entrance=*), read from the
    richer, route-relation-free re-extraction (hbf_indoor_clean_v2.json,
    Fase 3) — NOT from the pkl graph, since many of these nodes never made
    it into the routing graph in step 1 (they are not part of any
    footway's node list), and NOT from the older hbf_indoor_isolated.json,
    which missed most entrances because it was filtered by `level` first.
    A node without its own `level` tag is marked with levels=None
    ("heredado/desconocido") rather than guessed — the viewer shows those
    on every level, flagged as uncertain. Each door/entrance is also
    matched against room perimeters (indoor=room/area/corridor) so the
    tooltip can say which room/shop it belongs to, if any.
    """
    nodes, ways, _ = _load_isolated(ROOMS_DOORS_SOURCE)
    node_to_room = _build_node_to_room_map(nodes, ways)

    doors, entrances = [], []
    n_doors_no_level = 0
    n_entrances_no_level = 0

    for n in nodes.values():
        tags = n.get("tags") or {}
        if "lat" not in n or "lon" not in n:
            continue

        is_door = "door" in tags or tags.get("indoor") == "door"
        is_entrance = "entrance" in tags
        if not (is_door or is_entrance):
            continue

        has_own_level = "level" in tags
        levels = None
        if has_own_level:
            levels = [lv for lv in indoor_mod.parse_level(tags["level"])
                      if lv not in indoor_mod._IGNORE_LEVELS]
            if not levels:
                levels = None  # unparseable/ignored -> treat as unknown too

        room_info = node_to_room.get(n["id"])

        base = {
            "node_key": n["id"],
            "lon": n["lon"],
            "lat": n["lat"],
            "levels": levels,
            "level_known": levels is not None,
            "room_id": room_info["room_id"] if room_info else None,
            "room_name": room_info["room_name"] if room_info else None,
        }

        if is_door:
            door_value = tags.get("door") if "door" in tags else "indoor=door"
            doors.append({**base, "door_value": door_value})
            if levels is None:
                n_doors_no_level += 1

        if is_entrance:
            entrances.append({**base, "entrance_value": tags.get("entrance")})
            if levels is None:
                n_entrances_no_level += 1

    return doors, entrances, n_doors_no_level, n_entrances_no_level


def analyze_db_lounge_doors(doors, rooms_export, room_id=733736697, threshold_m=3.0):
    """
    Distance (in meters, via the same projected CRS used elsewhere in the
    project) from every door node to the DB Lounge polygon's boundary.
    Returns (closest_overall, list_within_threshold).
    """
    room = next((r for r in rooms_export if r["id"] == room_id), None)
    if room is None or not room.get("rings"):
        return None, [], None

    exterior_proj = [indoor_mod._TO_PROJ.transform(lon, lat)
                      for lon, lat in room["rings"][0]["exterior"]]
    boundary = LineString(exterior_proj)

    scored = []
    for d in doors:
        x, y = indoor_mod._TO_PROJ.transform(d["lon"], d["lat"])
        dist = boundary.distance(Point(x, y))
        scored.append((dist, d))

    scored.sort(key=lambda t: t[0])
    within = [(dist, d) for dist, d in scored if dist <= threshold_m]
    closest = scored[0] if scored else None
    return closest, within, room


def load_new_doors_from_buffer(doors_export, entrances_export):
    """
    Read data/interim/db_lounge_buffer.json (produced separately by
    scratch/query_db_lounge_buffer.py, an unfiltered 10m-buffer Overpass
    re-query around the DB Lounge). Returns (new_nodes, buffer_queried) —
    nodes tagged door/indoor=door/entrance that are NOT already present in
    the level-filtered dataset this viewer otherwise uses.
    """
    if not DB_LOUNGE_BUFFER_JSON.exists():
        return [], False

    data = json.loads(DB_LOUNGE_BUFFER_JSON.read_text(encoding="utf-8"))
    elements = data.get("elements") or []

    known_ids = {d["node_key"] for d in doors_export} | {e["node_key"] for e in entrances_export}

    new_nodes = []
    for el in elements:
        if el.get("type") != "node" or "lat" not in el:
            continue
        tags = el.get("tags") or {}
        if not ("door" in tags or tags.get("indoor") == "door" or "entrance" in tags):
            continue
        if el["id"] in known_ids:
            continue
        new_nodes.append({
            "node_key": el["id"],
            "lon": el["lon"],
            "lat": el["lat"],
            "tags": tags,
        })

    return new_nodes, True


def export_rooms():
    """
    Rebuilt from the clean re-extraction JSON (not the pkl) so we can
    attach the real `indoor` tag value (room/area/corridor), which
    IndoorRoom in indoor.py does not store. Reuses indoor.py's own
    polygon-reconstruction via _build_rooms for consistency, then looks up
    the source tag by id.
    """
    nodes, ways, relations = _load_isolated(ROOMS_DOORS_SOURCE)
    rooms = indoor_mod._build_rooms(ways, nodes, relations)

    exported = []
    for room in rooms:
        source = ways.get(room.id) if room.osm_type == "way" else relations.get(room.id)
        indoor_tag = (source.get("tags") or {}).get("indoor") if source else None
        rings = _polygon_rings(room.polygon)
        if not rings:
            continue
        exported.append({
            "id": room.id,
            "name": room.name,
            "indoor": indoor_tag,
            "levels": room.levels,
            "rings": rings,
        })
    return exported


def export_dea(G, rooms_export):
    dea_key = G.graph.get("dea_node_key")
    dea_data = G.nodes[dea_key]
    dea_lon, dea_lat = dea_data["lon"], dea_data["lat"]

    anchor_key, anchor_dist = locate_dea_anchor(G, level=0.0)
    anchor_data = G.nodes[anchor_key]
    anchor_lon, anchor_lat = anchor_data["lon"], anchor_data["lat"]

    dea_point = Point(dea_lon, dea_lat)
    hookup_line = LineString([(dea_lon, dea_lat), (anchor_lon, anchor_lat)])

    from shapely.geometry import shape as shapely_shape, Polygon, MultiPolygon

    def _rebuild_polygon(rings):
        polys = []
        for part in rings:
            try:
                polys.append(Polygon(part["exterior"], part["interiors"]))
            except Exception:
                continue
        if not polys:
            return None
        return polys[0] if len(polys) == 1 else MultiPolygon(polys)

    containing_room = None
    crossed_rooms = []
    for room in rooms_export:
        if 0.0 not in (room["levels"] or []):
            continue
        poly = _rebuild_polygon(room["rings"])
        if poly is None or not poly.is_valid:
            continue
        if poly.contains(dea_point):
            containing_room = room
        if hookup_line.crosses(poly.boundary) or hookup_line.intersects(poly.boundary):
            crossed_rooms.append(room)

    return {
        "node_key": dea_key,
        "lon": dea_lon,
        "lat": dea_lat,
        "level": dea_data.get("level"),
        "anchor_node_key": anchor_key,
        "anchor_lon": anchor_lon,
        "anchor_lat": anchor_lat,
        "anchor_dist_m": anchor_dist,
        "containing_room": {"id": containing_room["id"], "name": containing_room["name"]}
                           if containing_room else None,
        "crosses_wall_of": [{"id": r["id"], "name": r["name"]} for r in crossed_rooms
                            if not containing_room or r["id"] != containing_room["id"]],
    }


# ── HTML ─────────────────────────────────────────────────────────────


HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Visor grafo indoor — Hamburg Hbf</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; height:100%; font-family: -apple-system, sans-serif; }
  #map { position:absolute; top:0; left:0; right:280px; bottom:0; }
  #panel {
    position:absolute; top:0; right:0; width:280px; bottom:0;
    background:#fff; border-left:1px solid #ddd; overflow-y:auto;
    box-sizing:border-box; padding:12px; font-size:13px;
  }
  #panel h2 { font-size:15px; margin:0 0 8px 0; }
  #levels { display:flex; flex-direction:column; gap:4px; margin-bottom:14px; }
  .level-btn {
    padding:6px 10px; border:1px solid #ccc; border-radius:4px; background:#f7f7f7;
    cursor:pointer; text-align:center; font-weight:600;
  }
  .level-btn.active { background:#2563eb; color:#fff; border-color:#2563eb; }
  #counter { background:#f0f4ff; border-radius:4px; padding:8px; margin-bottom:14px; line-height:1.5; }
  .legend-item { display:flex; align-items:center; gap:6px; margin-bottom:5px; }
  .swatch { width:14px; height:14px; border-radius:50%; display:inline-block; flex:0 0 auto; }
  .swatch.line { border-radius:0; height:3px; }
  .swatch.room { border-radius:2px; border:1px solid #999; }
  #diagnostic { margin-top:14px; padding:8px; background:#fff7ed; border:1px solid #fdba74;
                border-radius:4px; line-height:1.5; }
  #diagnostic b { color:#9a3412; }
  #dblounge-diagnostic { margin-top:10px; padding:8px; background:#fef2f2; border:1px solid #fca5a5;
                border-radius:4px; line-height:1.5; }
  #dblounge-diagnostic b { color:#991b1b; }
  .leaflet-tooltip { font-size:11px; }
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <h2>Nivel</h2>
  <div id="levels"></div>
  <div id="counter"></div>
  <h2>Leyenda</h2>
  <div class="legend-item"><span class="swatch line" style="background:#888;"></span> arista horizontal (footway)</div>
  <div class="legend-item"><span class="swatch" style="background:#555;"></span> nodo footway</div>
  <div class="legend-item"><span class="swatch" style="background:#b45309;"></span> escalera (stairs)</div>
  <div class="legend-item"><span class="swatch" style="background:#0ea5e9;"></span> ascensor (elevator)</div>
  <div class="legend-item"><span class="swatch" style="background:#7c3aed;"></span> mecanica (escalator)</div>
  <div class="legend-item"><span class="swatch room" style="background:#93c5fd;"></span> sala / area / corridor</div>
  <div class="legend-item"><span class="swatch" style="background:#dc2626;"></span> DEA</div>
  <div class="legend-item"><span class="swatch" style="background:#16a34a;"></span> nodo footway mas cercano al DEA</div>
  <div class="legend-item"><span class="swatch" style="background:#f59e0b;"></span> puerta (door / indoor=door)</div>
  <div class="legend-item"><span class="swatch" style="background:#a855f7;"></span> entrada (entrance=*)</div>
  <div class="legend-item"><span class="swatch" style="background:#fff; border:2px dashed #999;"></span> nivel incierto (sin `level` propio)</div>
  <div id="diagnostic"></div>
  <div id="dblounge-diagnostic"></div>
</div>

<script>
const NODES = __NODES_JSON__;
const HORIZONTAL_EDGES = __HORIZONTAL_EDGES_JSON__;
const VERTICAL_CONNECTORS = __VERTICAL_CONNECTORS_JSON__;
const ROOMS = __ROOMS_JSON__;
const DEA = __DEA_JSON__;
const DOORS = __DOORS_JSON__;
const ENTRANCES = __ENTRANCES_JSON__;
const DB_LOUNGE = __DB_LOUNGE_JSON__;

const map = L.map("map", { zoomControl: true }).setView([DEA.lat, DEA.lon], 18);

L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  { attribution: "&copy; OpenStreetMap &copy; CARTO", subdomains: "abcd", maxZoom: 22 }
).addTo(map);

// One persistent LayerGroup per toggleable category. renderLevel() clears
// and repopulates each one for the active level WITHOUT touching whether
// it is currently on the map — so checkbox state survives level changes.
const roomsLayer = L.layerGroup();
const edgesLayer = L.layerGroup();
const nodesLayer = L.layerGroup();
const vertLayer = L.layerGroup();
const doorsLayer = L.layerGroup();
const entrancesLayer = L.layerGroup();
const deaLayer = L.layerGroup();
const dbLoungeLayer = L.layerGroup();

// Default subset shown on load: level 0 with rooms + footway edges + DEA on.
roomsLayer.addTo(map);
edgesLayer.addTo(map);
deaLayer.addTo(map);

L.control.layers(null, {
  "Salas (poligonos)": roomsLayer,
  "Aristas horizontales (footway)": edgesLayer,
  "Nodos footway": nodesLayer,
  "Conectores verticales": vertLayer,
  "Puertas": doorsLayer,
  "Entradas": entrancesLayer,
  "DEA": deaLayer,
  "DB Lounge resaltada + puertas nuevas": dbLoungeLayer,
}, { collapsed: false, position: "topleft" }).addTo(map);

function fmtLevel(lv) {
  return Number.isInteger(lv) ? String(lv) : String(lv);
}

// distinct levels present in nodes/edges/rooms (vertical connectors show on any level in their array)
const levelSet = new Set();
NODES.forEach(n => levelSet.add(n.level));
ROOMS.forEach(r => (r.levels || []).forEach(lv => levelSet.add(lv)));
const levels = Array.from(levelSet).sort((a, b) => b - a);

let activeLevel = levels.includes(0) ? 0 : levels[0];

const levelsDiv = document.getElementById("levels");
function renderLevelButtons() {
  levelsDiv.innerHTML = "";
  levels.forEach(lv => {
    const btn = document.createElement("div");
    btn.className = "level-btn" + (lv === activeLevel ? " active" : "");
    btn.textContent = fmtLevel(lv);
    btn.onclick = () => { activeLevel = lv; renderLevelButtons(); renderLevel(); };
    levelsDiv.appendChild(btn);
  });
}

const roomPane = "roomPane", edgePane = "edgePane", nodePane = "nodePane",
      vertPane = "vertPane", doorPane = "doorPane", entrancePane = "entrancePane",
      deaPane = "deaPane";
[roomPane, edgePane, nodePane, vertPane, doorPane, entrancePane, deaPane].forEach((name, i) => {
  map.createPane(name);
  map.getPane(name).style.zIndex = 400 + i * 10;
});

// DB Lounge highlight + any doors found by the buffer re-query — its own
// toggleable layer, not tied to level (drawn once, level-independent).
if (DB_LOUNGE) {
  DB_LOUNGE.rings.forEach(part => {
    const latlngs = [part.exterior.map(([lon, lat]) => [lat, lon])];
    part.interiors.forEach(ring => latlngs.push(ring.map(([lon, lat]) => [lat, lon])));
    L.polygon(latlngs, {
      pane: roomPane, color: "#dc2626", weight: 3, fillColor: "#fca5a5", fillOpacity: 0.25,
      dashArray: "4,4",
    })
      .bindTooltip(`DB Lounge (way ${DB_LOUNGE.id}) — sala del DEA`, { permanent: false, sticky: true })
      .addTo(dbLoungeLayer);
  });
  (DB_LOUNGE.doors_within_threshold || []).forEach(d => {
    L.circleMarker([d.lat, d.lon], {
      pane: doorPane, radius: 8, color: "#dc2626", weight: 3, fillColor: "#f59e0b", fillOpacity: 0.9,
    })
      .bindTooltip(`puerta ${d.node_key} a ${d.dist_m.toFixed(2)} m del perimetro`, { sticky: true })
      .addTo(dbLoungeLayer);
  });
  (DB_LOUNGE.new_doors_from_buffer || []).forEach(d => {
    L.circleMarker([d.lat, d.lon], {
      pane: doorPane, radius: 7, color: "#16a34a", weight: 3, fillColor: "#facc15", fillOpacity: 0.9,
    })
      .bindTooltip(
        `NUEVA (buffer 10m, no estaba en el dataset filtrado): node ${d.node_key} — ` +
        `${JSON.stringify(d.tags)}`,
        { sticky: true }
      )
      .addTo(dbLoungeLayer);
  });
}

function renderLevel() {
  roomsLayer.clearLayers();
  edgesLayer.clearLayers();
  nodesLayer.clearLayers();
  vertLayer.clearLayers();
  doorsLayer.clearLayers();
  entrancesLayer.clearLayers();
  deaLayer.clearLayers();

  let nRoomsShown = 0, nNodesShown = 0, nEdgesShown = 0, nVertShown = 0;

  ROOMS.forEach(room => {
    if (!(room.levels || []).includes(activeLevel)) return;
    nRoomsShown++;
    room.rings.forEach(part => {
      const latlngs = [part.exterior.map(([lon, lat]) => [lat, lon])];
      part.interiors.forEach(ring => latlngs.push(ring.map(([lon, lat]) => [lat, lon])));
      const poly = L.polygon(latlngs, {
        pane: roomPane, color: "#60a5fa", weight: 1, fillColor: "#93c5fd", fillOpacity: 0.35,
      }).addTo(roomsLayer);
      if (room.name) {
        poly.bindTooltip(room.name, { permanent: false, sticky: true });
      }
    });
  });

  HORIZONTAL_EDGES.forEach(edge => {
    if (edge.level !== activeLevel) return;
    nEdgesShown++;
    const latlngs = edge.coords.map(([lon, lat]) => [lat, lon]);
    L.polyline(latlngs, { pane: edgePane, color: "#888", weight: 2 })
      .bindTooltip(`cost_s=${edge.cost_s ? edge.cost_s.toFixed(1) : "?"}`, { sticky: true })
      .addTo(edgesLayer);
  });

  NODES.forEach(n => {
    if (n.level !== activeLevel || n.tipo !== "footway") return;
    nNodesShown++;
    L.circleMarker([n.lat, n.lon], {
      pane: nodePane, radius: 2.5, color: "#555", weight: 1, fillOpacity: 0.9,
    })
      .bindTooltip(n.node_key, { sticky: true })
      .addTo(nodesLayer);
  });

  const vertColor = { stairs: "#b45309", elevator: "#0ea5e9", escalator: "#7c3aed" };
  VERTICAL_CONNECTORS.forEach(c => {
    if (!c.levels.includes(activeLevel)) return;
    nVertShown++;
    L.circleMarker([c.lat, c.lon], {
      pane: vertPane, radius: 6, color: vertColor[c.tipo] || "#333",
      weight: 2, fillColor: vertColor[c.tipo] || "#333", fillOpacity: 0.7,
    })
      .bindTooltip(`${c.tipo} — conecta niveles [${c.levels.map(fmtLevel).join(", ")}]`, { sticky: true })
      .addTo(vertLayer);
  });

  let nDoorsShown = 0, nEntrancesShown = 0;

  DOORS.forEach(d => {
    if (d.levels && !d.levels.includes(activeLevel)) return;
    nDoorsShown++;
    const uncertain = !d.level_known;
    L.circleMarker([d.lat, d.lon], {
      pane: doorPane, radius: uncertain ? 5 : 4, color: uncertain ? "#999" : "#f59e0b",
      weight: uncertain ? 2 : 1, fillColor: "#f59e0b", fillOpacity: uncertain ? 0.4 : 0.9,
      dashArray: uncertain ? "3,2" : null,
    })
      .bindTooltip(
        `puerta: door=${d.door_value}` +
        (uncertain ? ` — nivel incierto (sin level propio)` : ` — level ${fmtLevel(d.levels[0])}`) +
        (d.room_name || d.room_id ? ` — sala: ${d.room_name || ("way " + d.room_id)}` : ` — sin sala asociada`),
        { sticky: true }
      )
      .addTo(doorsLayer);
  });

  ENTRANCES.forEach(e => {
    if (e.levels && !e.levels.includes(activeLevel)) return;
    nEntrancesShown++;
    const uncertain = !e.level_known;
    L.circleMarker([e.lat, e.lon], {
      pane: entrancePane, radius: uncertain ? 5 : 4, color: uncertain ? "#999" : "#a855f7",
      weight: uncertain ? 2 : 1, fillColor: "#a855f7", fillOpacity: uncertain ? 0.4 : 0.9,
      dashArray: uncertain ? "3,2" : null,
    })
      .bindTooltip(
        `entrada: entrance=${e.entrance_value}` +
        (uncertain ? ` — nivel incierto (sin level propio)` : ` — level ${fmtLevel(e.levels[0])}`) +
        (e.room_name || e.room_id ? ` — sala: ${e.room_name || ("way " + e.room_id)}` : ` — sin sala asociada`),
        { sticky: true }
      )
      .addTo(entrancesLayer);
  });

  // DEA always drawn (its layer's own on/off state controls visibility)
  L.circleMarker([DEA.lat, DEA.lon], {
    pane: deaPane, radius: 8, color: "#dc2626", weight: 2, fillColor: "#dc2626", fillOpacity: 0.9,
  })
    .bindTooltip(`DEA ${DEA.node_key} (level ${fmtLevel(DEA.level)})`, { permanent: true, direction: "top" })
    .addTo(deaLayer);

  if (activeLevel === 0) {
    L.circleMarker([DEA.anchor_lat, DEA.anchor_lon], {
      pane: deaPane, radius: 6, color: "#16a34a", weight: 2, fillColor: "#16a34a", fillOpacity: 0.9,
    })
      .bindTooltip(`nodo footway mas cercano (${DEA.anchor_dist_m.toFixed(2)} m)`, { sticky: true })
      .addTo(deaLayer);

    L.polyline([[DEA.lat, DEA.lon], [DEA.anchor_lat, DEA.anchor_lon]], {
      pane: deaPane, color: "#16a34a", weight: 2, dashArray: "6,6",
    }).addTo(deaLayer);
  }

  document.getElementById("counter").innerHTML =
    `<b>Nivel ${fmtLevel(activeLevel)}:</b><br/>` +
    `${nNodesShown} nodos footway, ${nEdgesShown} aristas, ` +
    `${nVertShown} conectores verticales, ${nRoomsShown} salas, ` +
    `${nDoorsShown} puertas, ${nEntrancesShown} entradas`;
}

const containing = DEA.containing_room
  ? `El DEA cae DENTRO de la sala <b>"${DEA.containing_room.name || DEA.containing_room.id}"</b>.`
  : `El DEA NO cae dentro de ninguna sala mapeada — esta en espacio abierto / pasillo.`;

const crossing = DEA.crosses_wall_of.length
  ? `La linea DEA -> nodo footway mas cercano SI cruza el limite de: ` +
    DEA.crosses_wall_of.map(r => `"${r.name || r.id}"`).join(", ") + "."
  : `La linea DEA -> nodo footway mas cercano NO cruza ningun limite de sala mapeado.`;

document.getElementById("diagnostic").innerHTML =
  `<b>Diagnostico de enganche (nivel 0)</b><br/>${containing}<br/>${crossing}<br/>` +
  `Distancia al nodo footway mas cercano: <b>${DEA.anchor_dist_m.toFixed(2)} m</b> ` +
  `(nodo <code>${DEA.anchor_node_key}</code>).`;

if (DB_LOUNGE) {
  let dbHtml = `<b>Puertas cerca de la DB Lounge (way ${DB_LOUNGE.id})</b><br/>` +
               `(activa la capa "DB Lounge resaltada + puertas nuevas" en la leyenda para verlas)<br/>`;
  if (DB_LOUNGE.doors_within_threshold && DB_LOUNGE.doors_within_threshold.length) {
    DB_LOUNGE.doors_within_threshold.forEach(d => {
      dbHtml += `node <code>${d.node_key}</code> — door=${d.door_value}, ` +
                `${d.dist_m.toFixed(2)} m del perimetro, level ${d.level_known ? fmtLevel(d.levels[0]) : "incierto"}<br/>`;
    });
  } else {
    dbHtml += `NINGUNA puerta local (dataset filtrado por level) a &le;3 m del perimetro. `;
    if (DB_LOUNGE.closest_door) {
      const cd = DB_LOUNGE.closest_door;
      dbHtml += `La mas cercana en ese dataset es <code>${cd.node_key}</code> a ` +
                `${cd.dist_m.toFixed(2)} m — demasiado lejos para ser su puerta real.<br/>`;
    } else {
      dbHtml += `No hay ninguna puerta en el dataset local en absoluto.<br/>`;
    }
  }
  if (DB_LOUNGE.new_doors_from_buffer && DB_LOUNGE.new_doors_from_buffer.length) {
    dbHtml += `<br/><b>Re-consulta con buffer de 10 m (sin filtro de tag/level) encontro ` +
              `${DB_LOUNGE.new_doors_from_buffer.length} nodo(s) NUEVO(S)</b> que el dataset ` +
              `filtrado no tenia (en amarillo/verde en el mapa):<br/>`;
    DB_LOUNGE.new_doors_from_buffer.forEach(d => {
      dbHtml += `node <code>${d.node_key}</code> — ${JSON.stringify(d.tags)}<br/>`;
    });
  } else if (DB_LOUNGE.buffer_queried) {
    dbHtml += `<br/>La re-consulta con buffer de 10 m tampoco trajo ninguna puerta/entrada ` +
              `nueva que el dataset filtrado no tuviera ya.`;
  }
  document.getElementById("dblounge-diagnostic").innerHTML = dbHtml;
}

renderLevelButtons();
renderLevel();
</script>
</body>
</html>
"""


def main():
    bundle = load_graph_bundle()
    G = bundle["graph"]

    nodes_export = export_nodes(G)
    edges_export = export_horizontal_edges(G)
    connectors_export = export_vertical_connectors(G)
    rooms_export = export_rooms()
    dea_export = export_dea(G, rooms_export)
    doors_export, entrances_export, n_doors_no_level, n_entrances_no_level = export_doors_and_entrances()

    closest_door, doors_within, db_lounge_room = analyze_db_lounge_doors(doors_export, rooms_export)
    new_doors_from_buffer, buffer_queried = load_new_doors_from_buffer(doors_export, entrances_export)

    db_lounge_export = None
    if db_lounge_room is not None:
        db_lounge_export = {
            "id": db_lounge_room["id"],
            "rings": db_lounge_room["rings"],
            "doors_within_threshold": [
                {**d, "dist_m": dist} for dist, d in doors_within
            ],
            "closest_door": (
                {**closest_door[1], "dist_m": closest_door[0]} if closest_door else None
            ),
            "new_doors_from_buffer": new_doors_from_buffer,
            "buffer_queried": buffer_queried,
        }

    html = (
        HTML_TEMPLATE
        .replace("__NODES_JSON__", json.dumps(nodes_export, ensure_ascii=False))
        .replace("__HORIZONTAL_EDGES_JSON__", json.dumps(edges_export, ensure_ascii=False))
        .replace("__VERTICAL_CONNECTORS_JSON__", json.dumps(connectors_export, ensure_ascii=False))
        .replace("__ROOMS_JSON__", json.dumps(rooms_export, ensure_ascii=False))
        .replace("__DEA_JSON__", json.dumps(dea_export, ensure_ascii=False))
        .replace("__DOORS_JSON__", json.dumps(doors_export, ensure_ascii=False))
        .replace("__ENTRANCES_JSON__", json.dumps(entrances_export, ensure_ascii=False))
        .replace("__DB_LOUNGE_JSON__", json.dumps(db_lounge_export, ensure_ascii=False))
    )

    OUT_HTML.write_text(html, encoding="utf-8")

    print(f"Nodos exportados: {len(nodes_export)}")
    print(f"Aristas horizontales exportadas: {len(edges_export)}")
    print(f"Conectores verticales exportados: {len(connectors_export)}")
    print(f"Salas exportadas: {len(rooms_export)}")
    print(f"Puertas exportadas: {len(doors_export)} ({n_doors_no_level} sin level propio)")
    print(f"Entradas exportadas: {len(entrances_export)} ({n_entrances_no_level} sin level propio)")
    print()
    print("Por nivel:")
    from collections import Counter
    n_by_level = Counter(n["level"] for n in nodes_export if n["tipo"] == "footway")
    e_by_level = Counter(e["level"] for e in edges_export)
    r_by_level = Counter(lv for r in rooms_export for lv in (r["levels"] or []))
    door_by_level = Counter()
    for d in doors_export:
        for lv in (d["levels"] or ["sin level"]):
            door_by_level[lv] += 1
    entrance_by_level = Counter()
    for e in entrances_export:
        for lv in (e["levels"] or ["sin level"]):
            entrance_by_level[lv] += 1
    all_levels = set(n_by_level) | set(e_by_level) | set(r_by_level) | set(door_by_level) | set(entrance_by_level)
    for lv in sorted(all_levels, key=lambda x: (x == "sin level", x if x != "sin level" else 0), reverse=True):
        print(f"  level {lv}: {n_by_level.get(lv,0)} nodos footway, "
              f"{e_by_level.get(lv,0)} aristas, {r_by_level.get(lv,0)} salas, "
              f"{door_by_level.get(lv,0)} puertas, {entrance_by_level.get(lv,0)} entradas")

    print()
    print("Diagnostico DEA:")
    print(json.dumps(dea_export, indent=2, ensure_ascii=False))

    print()
    print("Diagnostico DB Lounge (way 733736697) — puertas cercanas:")
    if db_lounge_export is None:
        print("  Sala no encontrada en rooms_export.")
    elif db_lounge_export["doors_within_threshold"]:
        for d in db_lounge_export["doors_within_threshold"]:
            print(f"  PUERTA node_key={d['node_key']} dist_m={d['dist_m']:.2f} "
                  f"door_value={d['door_value']} levels={d['levels']} "
                  f"level_known={d['level_known']}")
    else:
        print("  NINGUNA puerta local a <=3 m del perimetro de la DB Lounge.")
        if db_lounge_export["closest_door"]:
            cd = db_lounge_export["closest_door"]
            print(f"  (la mas cercana en todo el dataset: node_key={cd['node_key']} "
                  f"a {cd['dist_m']:.2f} m — demasiado lejos)")
        else:
            print("  No hay ninguna puerta en el dataset local.")

    if buffer_queried:
        if new_doors_from_buffer:
            print(f"\n  Re-consulta con buffer (db_lounge_buffer.json) trajo "
                  f"{len(new_doors_from_buffer)} nodo(s) NUEVO(S) door/entrance no presentes "
                  f"en el dataset filtrado:")
            for d in new_doors_from_buffer:
                print(f"    node {d['node_key']} — {d['tags']}")
        else:
            print("\n  Re-consulta con buffer (db_lounge_buffer.json) NO trajo ninguna "
                  "puerta/entrada nueva.")
    else:
        print("\n  data/interim/db_lounge_buffer.json no existe todavia — corre "
              "scratch/query_db_lounge_buffer.py primero para incluir esta comparacion.")

    print(f"\nHTML autocontenido guardado en: {OUT_HTML} ({OUT_HTML.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
