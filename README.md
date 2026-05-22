# AED Route Hamburg

A new clean project to calculate the shortest route from a selected map point to the nearest AED in Hamburg using a graph-based routing approach.

## Current phase
Phase 2:
- Hamburg administrative boundary
- AED download from OSM/Overpass
- local cache-first loading
- first Streamlit map

## Project structure

aed_route_hamburg/
├── docs/
│   └── routing_methodology.md
├── app/
│   └── streamlit_app.py
├── src/
│   └── aed_route/
│       ├── __init__.py
│       ├── config.py
│       ├── io.py
│       ├── aeds.py
│       ├── boundary.py
│       ├── network.py
│       ├── graph_builder.py
│       ├── nearest.py
│       ├── routing.py
│       ├── map_viz.py
│       ├── app_logic.py
│       └── utils.py
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── notebooks/
├── tests/
├── requirements.txt
├── README.md
├── .gitignore
└── styles.css

## Run

```bash
streamlit run app/streamlit_app.py


## Methodology

See `docs/routing_methodology.md` for the formal definition of the multimodal routing rules, including the OSM highway classification, access restrictions, and transport-specific traversal logic.