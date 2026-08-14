from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import logging
import math
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aed_route.utils import setup_logging, sha256_of_file
from aed_route.nearest import (
    build_aed_index,
    build_node_index,
    filter_node_index_to_keys,
    load_or_compute_giant_component,
)
from aed_route.routing import find_nearest_aeds
from aed_route.graph_builder_osm import load_or_build_graph_bundle
from aed_route.io import load_or_build_geojson
from aed_route.isochrones import compute_isochrones
from aed_route.config import (
    AEDS_CACHE_REL_PATH,
    BOUNDARY_CACHE_REL_PATH,
    GIANT_COMPONENT_CACHE_REL_PATH,
    GRAPH_CACHE_REL_PATH,
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

logger.info("Computing giant weakly connected component...")
# Fase 7, 2026-08-14 (C3). Read-only over the loaded graph, never touches
# the pickle. Cached as a NEW derived artifact — not the graph itself —
# so the ~0.7s computation isn't repeated on every process restart.
#
# The cache is tied to the graph pickle's own SHA-256 checksum (~0.7s to
# compute over the 364 MB file — measured, comparable to the giant
# component computation itself, so caching no longer saves much wall time
# in practice; it is kept anyway for the audit trail it leaves in
# data/processed/, and because it still avoids double work within the
# hot path when the check is cheap relative to graph rebuilds). The graph
# is immutable today (Restricción Global 1, enforced additionally by
# chmod 444 on the pickle — see docs/decisions.md, Fase 0), so this
# checksum can never actually change during this remediation effort. It
# exists as a safeguard for later: if the graph is ever rebuilt (e.g. for
# a future car-mode fix), a stale giant-component cache would otherwise
# silently reference nodes/edges from a graph that no longer exists,
# giving wrong-but-plausible-looking snapping decisions with no visible
# error — this check turns that into a logged, automatic recomputation
# instead.
nodes_df = bundle["nodes_df"]
all_node_keys = set(nodes_df["node_key"].tolist())
giant_cache_path = PROJECT_ROOT / GIANT_COMPONENT_CACHE_REL_PATH
graph_pkl_sha256 = sha256_of_file(PROJECT_ROOT / GRAPH_CACHE_REL_PATH)

# load_or_compute_giant_component (src/aed_route/nearest.py) hardened,
# after the Fase 7 code review, against a corrupt/malformed cache file
# (previously an uncaught JSONDecodeError/KeyError could crash startup —
# now treated the same as a checksum mismatch: logged and recomputed).
giant_node_keys, excluded_node_keys, _was_cached = load_or_compute_giant_component(
    cache_path=giant_cache_path,
    G=bundle["graph"],
    all_node_keys=all_node_keys,
    graph_pkl_sha256=graph_pkl_sha256,
)
logger.info(
    "Giant component %s: %d nodes, %d excluded (%s)",
    "loaded from cache" if _was_cached else "computed and cached",
    len(giant_node_keys), len(excluded_node_keys), giant_cache_path,
)

logger.info("Building spatial indices...")
node_index_unfiltered = build_node_index(nodes_df)
# Origin snapping restricted to the giant component (Fase 7, closes the
# origin-side half of C3): a click near a small disconnected fragment now
# snaps to a real, reachable node instead of an isolated one that could
# never yield a route to any AED. See docs/decisions.md for the AED side,
# which is NOT re-snapped here (accepted technical debt — see below).
node_index = filter_node_index_to_keys(node_index_unfiltered, giant_node_keys)
del node_index_unfiltered  # a second full-size cKDTree is dead weight past this point
aed_index = build_aed_index(aeds_fc, nodes_df)

aed_nodes_outside_giant = [
    nk for nk in aed_index["aed_nodes"] if nk not in giant_node_keys
]
if aed_nodes_outside_giant:
    logger.warning(
        "%d AED node(s) are OUTSIDE the giant weakly connected component "
        "and are NOT reachable from most origins in ANY transport mode — "
        "find_nearest_aeds will silently skip them as A* candidates "
        "(NetworkXNoPath). This is accepted technical debt (Fase 7, "
        "2026-08-14, see docs/decisions.md): fixing it would require "
        "re-snapping AED access edges, which means rebuilding the graph "
        "bundle — out of scope while the graph is treated as immutable. "
        "Affected AED node_keys: %s",
        len(aed_nodes_outside_giant), aed_nodes_outside_giant,
    )
else:
    logger.info("All AED nodes are within the giant weakly connected component.")

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

    # find_nearest_aeds is synchronous/CPU-bound (runs A* on a ~658k-node
    # graph up to SHORTLIST_EUCLIDEAN_K times). Running it directly inside
    # this async handler would block uvicorn's single event loop for the
    # full duration of the search, stalling every other concurrent request
    # (including /healthz) — see docs/decisions.md, 2026-08-14 (closes C10).
    results = await asyncio.to_thread(
        find_nearest_aeds,
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
    # Canonical port, unified 2026-08-14 (was 5050) to match every other
    # deployment artifact in this repo (Dockerfile, docker-compose.yml,
    # docs/apache.conf, app/wsgi.py) — see docs/decisions.md.
    uvicorn.run(app, host="0.0.0.0", port=5000)
