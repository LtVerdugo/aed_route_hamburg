# AED Route Hamburg

An interactive web map for finding the shortest route from any point in Hamburg to the nearest AED (automated external defibrillator). Users click anywhere on the map to calculate the optimal route in three transport modes — walking, cycling, or driving — with animated route visualisation, 2-minute and 4-minute walk isochrones, and the option to compare up to two alternative AED locations.

## Project structure

```
aed_route_hamburg/
├── app/
│   └── flask_app.py          # Flask application and API routes
├── docs/
│   ├── routing_methodology.md
│   ├── network_and_graph_build.md
│   └── explanation.docx
├── src/
│   └── aed_route/
│       ├── __init__.py
│       ├── config.py         # All project constants
│       ├── io.py             # Overpass API client, cache I/O
│       ├── aeds.py           # AED data download and parsing
│       ├── boundary.py       # Hamburg boundary download and parsing
│       ├── graph_builder_osm.py  # Multimodal graph construction
│       ├── isochrones.py     # Walk isochrone computation
│       ├── nearest.py        # Spatial indices (cKDTree)
│       ├── routing.py        # A* routing on the unified graph
│       └── utils.py          # Logging, filesystem helpers
├── static/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── data/
│   ├── raw/
│   ├── interim/              # Graph bundle (.pkl)
│   └── processed/            # AED, boundary, isochrone GeoJSON
├── requirements.txt
├── wsgi.py
├── .gitignore
└── README_deploy.md
```

## How it works

AED and boundary data are downloaded from the OpenStreetMap Overpass API and cached as GeoJSON. The street network for Hamburg is built using OSMnx — walk, bike, and car networks are downloaded separately, merged into a single `MultiDiGraph`, and cached as a pickle bundle. At startup, Flask loads the bundle once into memory and builds spatial indices (cKDTree) over all nodes and AED locations.

On each map click, the origin is snapped to the nearest graph node, the three Euclidean-nearest AEDs are selected as candidates (K=3), and A* is run on a mode-filtered subgraph view for each candidate. Results are ranked by total travel cost and returned as JSON.

Walk isochrones (2 min and 4 min) are precomputed using `nx.ego_graph` with a 25 m street buffer and cached as GeoJSON.

## Features

- **Three transport modes** — walk, bike, car; each uses mode-specific road rules and travel times
- **Animated route drawing** — progressive draw via leaflet.motion, then ant-path flow effect
- **Walk isochrones** — 2-minute (green) and 4-minute (orange) walking coverage around each AED
- **Layer toggles** — AED locations, isochrones, Hamburg city boundary mask
- **Alternative routes** — compare up to 2 additional nearest AEDs with time difference
- **Help popup** — onboarding overlay on first load

## Tech stack

**Backend:** Python, Flask, OSMnx, NetworkX, Shapely, PyProj, SciPy, Gunicorn

**Frontend:** Leaflet.js 1.7.1, leaflet.motion 0.3.2, leaflet-ant-path 1.3.0

## Running locally

```bash
gunicorn --workers 1 --bind 0.0.0.0:5050 --timeout 120 wsgi:app
```

See [README_deploy.md](README_deploy.md) for full deployment instructions including data pipeline setup, environment configuration, and production deployment.

## Methodology

See [docs/routing_methodology.md](docs/routing_methodology.md) for the formal definition of the multimodal routing rules, including OSM highway classification, access restrictions, transport-specific traversal logic, and speed assumptions.
