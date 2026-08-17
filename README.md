# AED Route Hamburg

Multimodal (walk / bike / car) routing to the nearest AED (automated
external defibrillator) across the city of Hamburg, on the real street
network — FastAPI backend, OSMnx-built routing graph, Leaflet.js
frontend. City-wide, not limited to a single district.

**Note (2026-08-17):** the app is served at the base of its public path,
**not** under `/static/`:
https://www.cml.hcu-hamburg.de/demos/aed-routing/

If you have `.../demos/aed-routing/static/` bookmarked or linked
somewhere, it stopped working when the old static prototype at that path
was retired — it now returns 404.

Car mode is currently disabled in the UI, pending a team decision on how
to fix its known routing gap (see `docs/decisions.md`).

For installation, configuration, and deployment instructions, see
**`README_deploy.md`** — this file does not duplicate them.
