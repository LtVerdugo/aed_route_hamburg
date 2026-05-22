from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests

from .config import (
    OSM_AREA_ADMIN_LEVEL,
    OSM_AREA_ISO3166_2,
    OSM_AREA_NAME,
    OSM_AREA_RELATION_ID,
    OSM_AREA_WIKIDATA,
    OVERPASS_BACKOFF_BASE_S,
    OVERPASS_ENDPOINTS,
    OVERPASS_HTTP_TIMEOUT_S,
    OVERPASS_MAX_ENDPOINT_ATTEMPTS,
    OVERPASS_QUERY_TIMEOUT_S,
)
from .utils import ensure_parent_dir

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 502, 503, 504}


@dataclass(frozen=True)
class OverpassError(RuntimeError):
    message: str
    last_endpoint: str | None = None
    last_status: int | None = None
    last_snippet: str | None = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.last_endpoint:
            parts.append(f"endpoint={self.last_endpoint}")
        if self.last_status is not None:
            parts.append(f"status={self.last_status}")
        if self.last_snippet:
            parts.append(f"snippet={self.last_snippet}")
        return " | ".join(parts)


@dataclass(frozen=True)
class CacheReport:
    used_cache: bool
    out_path: str
    n_features: int


def call_overpass(query: str) -> dict[str, Any]:
    """
    Call Overpass by rotating endpoints and retrying in the event of temporary failures.
    """
    endpoints = list(OVERPASS_ENDPOINTS)
    random.shuffle(endpoints)

    session = requests.Session()
    last_exc: Exception | None = None
    last_status: int | None = None
    last_snippet: str | None = None
    last_endpoint: str | None = None

    for endpoint in endpoints:
        last_endpoint = endpoint

        for attempt in range(1, OVERPASS_MAX_ENDPOINT_ATTEMPTS + 1):
            try:
                resp = session.post(
                    endpoint,
                    data={"data": query},
                    timeout=OVERPASS_HTTP_TIMEOUT_S,
                    headers={"User-Agent": "aed_route_hamburg/0.1"},
                )

                last_status = resp.status_code

                if resp.status_code in _RETRYABLE_STATUS:
                    last_snippet = (resp.text or "")[:300].replace("\n", " ")
                    logger.debug(
                        "Retryable Overpass response | endpoint=%s | attempt=%s/%s | status=%s",
                        endpoint,
                        attempt,
                        OVERPASS_MAX_ENDPOINT_ATTEMPTS,
                        resp.status_code,
                    )
                    time.sleep(OVERPASS_BACKOFF_BASE_S * attempt)
                    continue

                resp.raise_for_status()

                text = (resp.text or "").strip()
                if not text:
                    raise ValueError("Empty response body from Overpass.")

                try:
                    return resp.json()
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Non-JSON response. First chars: {text[:120]}") from exc

            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                logger.debug(
                    "Overpass endpoint failed | endpoint=%s | attempt=%s/%s | status=%s | error=%s",
                    endpoint,
                    attempt,
                    OVERPASS_MAX_ENDPOINT_ATTEMPTS,
                    last_status,
                    exc,
                )
                time.sleep(OVERPASS_BACKOFF_BASE_S * attempt)

    logger.warning(
        "Overpass failed on all endpoints | last_endpoint=%s | last_status=%s | error=%s",
        last_endpoint,
        last_status,
        last_exc,
    )
    raise OverpassError(
        message="Overpass failed on all endpoints",
        last_endpoint=last_endpoint,
        last_status=last_status,
        last_snippet=last_snippet,
    )


def _extract_relations(response: dict) -> list:
    return [
        el for el in (response.get("elements") or [])
        if el.get("type") == "relation"
    ]


def resolve_hamburg_admin_relation_id() -> int:
    """
    Determine the correct relation ID for Hamburg (DE) to avoid any ambiguity.
    """
    if OSM_AREA_RELATION_ID is not None:
        return int(OSM_AREA_RELATION_ID)

    q1 = f"""
    [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];
    relation
      ["boundary"="administrative"]
      ["name"="{OSM_AREA_NAME}"]
      ["admin_level"="{OSM_AREA_ADMIN_LEVEL}"]
      ["ISO3166-2"="{OSM_AREA_ISO3166_2}"];
    out tags;
    """
    r1 = call_overpass(q1)
    candidates = _extract_relations(r1)

    if not candidates:
        q2 = f"""
        [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];
        relation
          ["boundary"="administrative"]
          ["wikidata"="{OSM_AREA_WIKIDATA}"];
        out tags;
        """
        r2 = call_overpass(q2)
        candidates = _extract_relations(r2)

    if not candidates:
        q3 = f"""
        [out:json][timeout:{OVERPASS_QUERY_TIMEOUT_S}];
        relation
          ["boundary"="administrative"]
          ["name"="{OSM_AREA_NAME}"]
          ["admin_level"="{OSM_AREA_ADMIN_LEVEL}"];
        out tags;
        """
        r3 = call_overpass(q3)
        candidates = _extract_relations(r3)

    if not candidates:
        raise ValueError("Could not resolve Hamburg (DE) administrative relation id.")

    def _score(el: dict[str, Any]) -> int:
        tags = el.get("tags") or {}
        s = 0
        if tags.get("admin_level") == str(OSM_AREA_ADMIN_LEVEL):
            s += 10
        if tags.get("ISO3166-2") == OSM_AREA_ISO3166_2:
            s += 100
        if tags.get("wikidata") == OSM_AREA_WIKIDATA:
            s += 90
        return s

    best = max(candidates, key=_score)
    return int(best["id"])


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent_dir(path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def load_or_build_geojson(
    *,
    out_path: Path,
    build_fn: Callable[[], dict[str, Any]],
    force_rebuild: bool = False,
) -> tuple[dict[str, Any], CacheReport]:
    """
    Loads a GeoJSON from the cache or generates and saves it.
    """
    if out_path.exists() and not force_rebuild:
        gj = read_json(out_path)
        n = len(gj.get("features", []) or [])
        return gj, CacheReport(
            used_cache=True,
            out_path=str(out_path),
            n_features=n,
        )

    gj = build_fn()
    write_json(out_path, gj)
    n = len(gj.get("features", []) or [])
    return gj, CacheReport(
        used_cache=False,
        out_path=str(out_path),
        n_features=n,
    )