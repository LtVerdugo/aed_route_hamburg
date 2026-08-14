# AED Coverage — Hamburg-Mitte

> **Notice added 2026-08-14:** this document describes an older, static
> prototype (`static/index.html` + `static/app.js`, Hamburg-Mitte only, no
> backend). It is **not** the application currently deployed — the live
> app is a FastAPI-backed, city-wide service described in
> `README_deploy.md`, served from `static/index_original.html` +
> `static/app_original.js`. The URL below, and the "no backend required"
> claim in this file, do not describe today's deployment; verified against
> the current code (`app/app.py`), not assumed. Whether to keep, merge, or
> retire this document (and the static prototype it describes) is a
> pending decision, not made yet — see `docs/decisions.md`.

Interactive map showing walk isochrone coverage
(2 min and 4 min) from each AED in Hamburg-Mitte.

**Live (as originally written — not verified against the current
deployment, see notice above):**
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

## Deployment (of the static prototype described in this file — see notice at top)

The server serves static/ at:
https://www.cml.hcu-hamburg.de/demos/aed-routing/static/

No backend required for *this* prototype. All data is pre-generated.
This does not describe the currently deployed application — see
`README_deploy.md`.

