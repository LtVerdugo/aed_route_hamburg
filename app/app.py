from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
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

logger.info("FastAPI app ready.")

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=str(PROJECT_ROOT / "static")),
    name="static",
)


# ── Routes ─────────────────────────────────────────────────────
@app.get("/")
async def index():
    return FileResponse(str(PROJECT_ROOT / "static" / "index_original.html"))


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/api/aeds")
async def get_aeds():
    return aeds_fc


@app.get("/api/isochrones")
async def get_isochrones():
    cache_path = PROJECT_ROOT / ISOCHRONE_CACHE_REL_PATH
    return Response(cache_path.read_bytes(), media_type="application/json")


@app.get("/api/boundary")
async def get_boundary():
    cache_path = PROJECT_ROOT / BOUNDARY_CACHE_REL_PATH
    return Response(cache_path.read_bytes(), media_type="application/json")


class RouteRequest(BaseModel):
    lat: float
    lon: float
    mode: str = "walk"


@app.post("/api/route")
async def route(body: RouteRequest):
    if body.mode not in ("walk", "bike", "car"):
        raise HTTPException(status_code=400, detail="Invalid mode")

    results = find_nearest_aeds(
        origin_lon=body.lon,
        origin_lat=body.lat,
        mode=body.mode,
        graph_bundle=bundle,
        aed_index=aed_index,
        node_index=node_index,
        k=SHORTLIST_EUCLIDEAN_K,
    )

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

    return {"results": serializable}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)
