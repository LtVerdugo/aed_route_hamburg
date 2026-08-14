from __future__ import annotations

from pathlib import Path
from typing import Final


# =========================================================
# App / map
# =========================================================
# CRS
CRS_MAP: Final[str] = "EPSG:4326"       # Web map
CRS_PROJECTED: Final[str] = "EPSG:25832"  # Metric calculations in Hamburg

# Routing defaults (used later)
WALK_SPEED_M_S: Final[float] = 1.7  # We need to back this up with research papers
BIKE_SPEED_M_S: Final[float] = 4.5  # We need to back this up with research papers

SHORTLIST_EUCLIDEAN_K: Final[int] = 3
MAX_SNAP_DISTANCE_M: Final[float] = 100.0

TRANSPORT_PROFILES: Final[tuple[str, ...]] = ("walk", "bike", "car")


# =========================================================
# Overpass / Hamburg disambiguation
# =========================================================
OSM_AREA_NAME: Final[str] = "Hamburg"
OSM_AREA_ADMIN_LEVEL: Final[str] = "4"   # Hamburg city-state
OSM_AREA_ISO3166_2: Final[str] = "DE-HH"
OSM_AREA_WIKIDATA: Final[str] = "Q1055"

# Optional manual override if ever needed
OSM_AREA_RELATION_ID: int | None = None

OVERPASS_ENDPOINTS: Final[tuple[str, ...]] = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
)

OVERPASS_HTTP_TIMEOUT_S: Final[int] = 180
OVERPASS_QUERY_TIMEOUT_S: Final[int] = 120
OVERPASS_MAX_ENDPOINT_ATTEMPTS: Final[int] = 2
OVERPASS_BACKOFF_BASE_S: Final[float] = 2.0


# =========================================================
# Local cache paths
# =========================================================
DATA_DIR_REL: Final[Path] = Path("data")
INTERIM_DIR_REL: Final[Path] = DATA_DIR_REL / "interim"
PROCESSED_DIR_REL: Final[Path] = DATA_DIR_REL / "processed"

AEDS_CACHE_REL_PATH: Final[Path] = PROCESSED_DIR_REL / "hamburg_aeds.geojson"
BOUNDARY_CACHE_REL_PATH: Final[Path] = PROCESSED_DIR_REL / "hamburg_boundary.geojson"

GRAPH_CACHE_REL_PATH: Final[Path] = INTERIM_DIR_REL / "hamburg_graph.pkl"

# Artefacto derivado (Fase 7, 2026-08-14) — NUNCA el pickle del grafo en sí.
# Lista de node_keys fuera del componente débilmente conexo mayor del
# grafo, calculada al arranque de la app y cacheada aquí para no repetir
# el cálculo (~0.7s sobre el grafo real) en cada reinicio del proceso.
GIANT_COMPONENT_CACHE_REL_PATH: Final[Path] = (
    PROCESSED_DIR_REL / "graph_giant_component_excluded_nodes.json"
)


# =========================================================
# Isochrones
# =========================================================
# Travel times in seconds for AED isochrone layers.
# 2 minutes: critical window for defibrillation effectiveness.
# 4 minutes: outer limit before survival rates drop significantly.
ISOCHRONE_TIMES_S: Final[tuple[int, ...]] = (120, 240)

# Cache path for precomputed isochrones
ISOCHRONE_CACHE_REL_PATH: Final[Path] = (
    PROCESSED_DIR_REL / "hamburg_isochrones_walk.geojson"
)


# =========================================================
# Indoor navigation — PROVISIONAL (calibrar con literatura)
# =========================================================
# Costes de conexion vertical. Valores de partida provisionales:
# deben recalibrarse con material cientifico (evacuacion / transito
# vertical en estaciones). Ver docs/indoor_navigation.md.
STAIR_SECONDS_PER_LEVEL: Final[float] = 15.0
ESCALATOR_SECONDS_PER_LEVEL: Final[float] = 12.0
ELEVATOR_SECONDS_PER_LEVEL: Final[float] = 10.0
ELEVATOR_WAIT_SECONDS: Final[float] = 20.0
# Ruido conocido a ignorar en el grafo indoor (a verificar):
INDOOR_IGNORE_LEVELS: Final[tuple[float, ...]] = (5.0,)