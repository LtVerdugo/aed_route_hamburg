from __future__ import annotations

from pathlib import Path
from typing import Any

from shapely.geometry import LineString, MultiLineString, mapping
from shapely.ops import polygonize, unary_union

from .config import BOUNDARY_CACHE_REL_PATH, OVERPASS_QUERY_TIMEOUT_S
from .io import (
    CacheReport,
    call_overpass,
    load_or_build_geojson,
    resolve_hamburg_admin_relation_id,
)


def fetch_hamburg_boundary_overpass() -> dict[str, Any]:
    """
    Download the list of Hamburg’s administrative bodies and their members.
    """
    rel_id = resolve_hamburg_admin_relation_id()

    query = f"""
    [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];
    relation({rel_id});
    (._;>;);
    out geom;
    """
    return call_overpass(query)


def overpass_boundary_to_geojson(overpass_json: dict[str, Any]) -> dict[str, Any]:
    """
    Converts the administrative boundary of Hamburg into a GeoJSON polygon.
    Handles outer and inner boundaries where they exist.
    """
    elements = overpass_json.get("elements", []) or []

    ways_by_id: dict[int, list[tuple[float, float]]] = {}
    relation_el: dict[str, Any] | None = None

    for el in elements:
        if el.get("type") == "relation" and relation_el is None:
            relation_el = el

        if el.get("type") != "way":
            continue

        wid = el.get("id")
        geom = el.get("geometry")
        if wid is None or not geom:
            continue

        coords = [(float(p["lon"]), float(p["lat"])) for p in geom if "lon" in p and "lat" in p]
        if len(coords) >= 2:
            ways_by_id[int(wid)] = coords

    if relation_el is None:
        return {"type": "FeatureCollection", "features": []}

    outer_lines = []
    inner_lines = []

    for mem in relation_el.get("members", []) or []:
        if mem.get("type") != "way":
            continue

        ref = mem.get("ref")
        if ref is None:
            continue

        coords = ways_by_id.get(int(ref))
        if not coords or len(coords) < 2:
            continue

        role = (mem.get("role") or "").strip().lower()
        ls = LineString(coords)

        if role == "inner":
            inner_lines.append(ls)
        else:
            outer_lines.append(ls)

    if not outer_lines:
        return {"type": "FeatureCollection", "features": []}

    outer_ml = MultiLineString(outer_lines)
    outer_polys = list(polygonize(outer_ml))
    if not outer_polys:
        return {"type": "FeatureCollection", "features": []}

    outer_geom = unary_union(outer_polys)

    if inner_lines:
        inner_ml = MultiLineString(inner_lines)
        inner_polys = list(polygonize(inner_ml))
        if inner_polys:
            inner_geom = unary_union(inner_polys)
            geom_final = outer_geom.difference(inner_geom)
        else:
            geom_final = outer_geom
    else:
        geom_final = outer_geom

    try:
        geom_final = geom_final.buffer(0)
    except Exception:
        pass

    if geom_final.is_empty:
        return {"type": "FeatureCollection", "features": []}

    tags = relation_el.get("tags", {}) or {}

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": tags.get("name", "Hamburg"),
                    "relation_id": relation_el.get("id"),
                    "admin_level": tags.get("admin_level"),
                    "source": "osm_overpass",
                },
                "geometry": mapping(geom_final),
            }
        ],
    }


def load_or_build_boundary_geojson(
    *,
    project_root: Path,
    out_rel_path: Path = BOUNDARY_CACHE_REL_PATH,
    force_rebuild: bool = False,
) -> tuple[dict[str, Any], CacheReport]:
    gj, rep = load_or_build_geojson(
        out_path=project_root / out_rel_path,
        build_fn=lambda: overpass_boundary_to_geojson(fetch_hamburg_boundary_overpass()),
        force_rebuild=force_rebuild,
    )
    return gj, rep