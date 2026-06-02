# AED Coverage — Hamburg-Mitte

Interactive map showing walk isochrone coverage
(2 min and 4 min) from each AED in Hamburg-Mitte.

**Live:**
https://www.cml.hcu-hamburg.de/demos/aed-routing/static/

## Repository contents

    static/
    ├── index.html
    ├── app.js
    ├── styles.css
    └── data/
        ├── hamburg_mitte_aeds.geojson
        ├── hamburg_mitte_boundary.geojson
        └── hamburg_mitte_isochrones_walk.geojson

## How to update the data

Data is precomputed locally and committed to the repo.
To regenerate after OSM changes:

1. Run build_hamburg_mitte.py on your local machine
   (requires Python environment — not included in repo)
2. The script copies updated GeoJSON to static/data/
3. Commit and push static/data/*.geojson

## Deployment

The server serves static/ at:
https://www.cml.hcu-hamburg.de/demos/aed-routing/static/

No backend required. All data is pre-generated.

## Uploading to the server

The colleague only needs to upload the static/ folder.
No Python, no dependencies, no configuration needed.
