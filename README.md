# AED Route Hamburg

Multimodal (walk / bike / car) routing to the nearest AED (automated
external defibrillator) across the city of Hamburg, on the real street
network — FastAPI backend, OSMnx-built routing graph, Leaflet.js
frontend. City-wide, not limited to a single district.

**Status note (corrected 2026-08-17):** the backend-based app described in
this repository has **not been deployed anywhere yet**. The URL currently
live at
https://www.cml.hcu-hamburg.de/demos/aed-routing/static/
is a **separate, manually-uploaded static folder** — an older,
Hamburg-Mitte-only prototype with precomputed GeoJSON and no backend. It
is unrelated to this repository's code, was not affected by this repo's
own internal cleanup of an unlinked prototype pair, and keeps working
today exactly as before — nothing about it is broken.

Once (if) this backend app is deployed, the recommended public URL is the
base path, without `/static/`:
https://www.cml.hcu-hamburg.de/demos/aed-routing/
— see `README_deploy.md`, including its note on why that deployment is
not currently possible on the existing HCU infrastructure.

Car mode is currently disabled in the UI, pending a team decision on how
to fix its known routing gap (see `docs/decisions.md`).

For installation, configuration, and deployment instructions, see
**`README_deploy.md`** — this file does not duplicate them.
