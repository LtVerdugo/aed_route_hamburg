from flask import Flask, jsonify, request, send_from_directory, Response
import logging
import math
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aed_route.utils import setup_logging
from aed_route.nearest import build_aed_index, build_node_index
from aed_route.routing import find_nearest_aeds
from aed_route.graph_builder_osm import load_or_build_graph_bundle
from aed_route.io import load_or_build_geojson
from aed_route.isochrones import compute_isochrones
from aed_route.config import (
    AEDS_CACHE_REL_PATH,
    BOUNDARY_CACHE_REL_PATH,
    ISOCHRONE_CACHE_REL_PATH,
    SHORTLIST_EUCLIDEAN_K,
)

setup_logging()
logger = logging.getLogger(__name__)

PUBLIC_BASE_PATH = os.environ.get("PUBLIC_BASE_PATH", "").strip()
if PUBLIC_BASE_PATH and not PUBLIC_BASE_PATH.startswith("/"):
    PUBLIC_BASE_PATH = f"/{PUBLIC_BASE_PATH}"
PUBLIC_BASE_PATH = PUBLIC_BASE_PATH.rstrip("/")
if PUBLIC_BASE_PATH == "/":
    PUBLIC_BASE_PATH = ""

app = Flask(
    __name__,
    static_folder=str(PROJECT_ROOT / "static"),
    static_url_path=(
        f"{PUBLIC_BASE_PATH}/static" if PUBLIC_BASE_PATH else "/static"
    ),
)
app.config["APPLICATION_ROOT"] = PUBLIC_BASE_PATH or "/"


def app_route(rule: str, **options):
    """Register a route with an optional public URL prefix alias."""
    def decorator(func):
        app.route(rule, **options)(func)
        if PUBLIC_BASE_PATH:
            app.route(f"{PUBLIC_BASE_PATH}{rule}", **options)(func)
            if rule == "/":
                app.route(PUBLIC_BASE_PATH, **options)(func)
        return func

    return decorator


def _require_cache(name: str):
    raise RuntimeError(f"{name} cache not found — run the data pipeline first")


def _clean(value):
    """Convert NaN/None to None for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


# ── Load all data once at startup ──────────────────────────────
logger.info("Loading AEDs...")
aeds_fc, _ = load_or_build_geojson(
    out_path=PROJECT_ROOT / AEDS_CACHE_REL_PATH,
    build_fn=lambda: _require_cache("AED"),
    force_rebuild=False,
)

logger.info("Loading graph bundle...")
bundle, _ = load_or_build_graph_bundle(
    project_root=PROJECT_ROOT,
    force_rebuild=False,
    aeds_fc=aeds_fc,
)

logger.info("Building spatial indices...")
nodes_df = bundle["nodes_df"]
node_index = build_node_index(nodes_df)
aed_index = build_aed_index(aeds_fc, nodes_df)

logger.info("Loading isochrones...")
isochrones_fc = compute_isochrones(
    G=bundle["graph"],
    aeds_fc=aeds_fc,
    project_root=PROJECT_ROOT,
    force_rebuild=False,
)
logger.info(
    "Isochrones loaded: %d features",
    len(isochrones_fc.get("features", [])),
)

logger.info("Flask app ready.")


# ── Routes ─────────────────────────────────────────────────────
@app_route("/")
def index():
    return send_from_directory(str(PROJECT_ROOT / "static"), "index.html")


@app_route("/healthz")
def healthz():
    return jsonify({"ok": True})


@app_route("/api/aeds")
def get_aeds():
    return jsonify(aeds_fc)


@app_route("/api/isochrones")
def get_isochrones():
    cache_path = PROJECT_ROOT / ISOCHRONE_CACHE_REL_PATH
    with cache_path.open("r", encoding="utf-8") as f:
        content = f.read()
    return Response(content, mimetype="application/json")


@app_route("/api/boundary")
def get_boundary():
    cache_path = PROJECT_ROOT / BOUNDARY_CACHE_REL_PATH
    with cache_path.open("r", encoding="utf-8") as f:
        content = f.read()
    return Response(content, mimetype="application/json")


@app_route("/api/route", methods=["POST"])
def route():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    lat = float(data["lat"])
    lon = float(data["lon"])
    mode = str(data.get("mode", "walk"))

    if mode not in ("walk", "bike", "car"):
        return jsonify({"error": "Invalid mode"}), 400

    results = find_nearest_aeds(
        origin_lon=lon,
        origin_lat=lat,
        mode=mode,
        graph_bundle=bundle,
        aed_index=aed_index,
        node_index=node_index,
        k=SHORTLIST_EUCLIDEAN_K,
    )

    # Serialize results — convert shapely geometries to GeoJSON coords
    serializable = []
    for r in results:
        edges = []
        for e in r.get("path_edges", []):
            geom = e.get("geometry")
            if geom is not None:
                try:
                    coords = [[float(c[0]), float(c[1])] for c in geom.coords]
                except Exception:
                    coords = []
            else:
                coords = []
            edges.append({
                "coords": coords,
                "highway": _clean(e.get("highway")),
                "name": _clean(e.get("name")),
                "length_m": _clean(e.get("length_m")),
                "cost_s": _clean(e.get("cost_s")),
                "time_s": _clean(e.get("time_s")),
            })
        serializable.append({
            "rank": r["rank"],
            "total_cost_s": _clean(r["total_cost_s"]),
            "total_time_s": _clean(r["total_time_s"]),
            "total_length_m": _clean(r["total_length_m"]),
            "euclidean_distance_m": _clean(r["euclidean_distance_m"]),
            "aed_id": _clean(r["aed_properties"].get("id")),
            "aed_lat": _clean(r["aed_properties"].get("lat")),
            "aed_lon": _clean(r["aed_properties"].get("lon")),
            "aed_name": _clean(r["aed_properties"].get("name")),
            "aed_access": _clean(r["aed_properties"].get("access")),
            "aed_opening_hours": _clean(
                r["aed_properties"].get("opening_hours")
            ),
            "edges": edges,
        })

    return jsonify({"results": serializable})


if __name__ == "__main__":
    app.run(debug=False, port=5050)
