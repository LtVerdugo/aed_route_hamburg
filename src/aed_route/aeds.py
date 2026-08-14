from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import AEDS_CACHE_REL_PATH, OVERPASS_QUERY_TIMEOUT_S
from .io import (
    call_overpass,
    load_or_build_geojson,
    resolve_hamburg_admin_relation_id,
)


def fetch_aeds_overpass() -> dict[str, Any]:
    """
    Download Hamburg AEDs from OSM/Overpass.
    """
    rel_id = resolve_hamburg_admin_relation_id()

    query = f"""
    [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];
    relation({rel_id});
    map_to_area->.a;
    (
      node["emergency"="defibrillator"](area.a);
    );
    out body;
    """
    return call_overpass(query)


def overpass_aeds_to_geojson(overpass_json: dict[str, Any]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []

    for el in overpass_json.get("elements", []) or []:
        if el.get("type") != "node":
            continue

        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue

        tags = el.get("tags", {}) or {}

        props = {
            "id": el.get("id"),
            "name": tags.get("name"),
            "access": tags.get("access"),
            "opening_hours": tags.get("opening_hours"),
            "indoor": tags.get("indoor"),
            "level": tags.get("level"),
            "operator": tags.get("operator"),
            "source": "osm_overpass",
        }

        # We also keep all the original tags in case we need them later
        for k, v in tags.items():
            if k not in props:
                props[k] = v

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)],
                },
                "properties": props,
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }
