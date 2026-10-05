# AED Route Hamburg

Multimodal (walk / bike / car) routing to the nearest AED (automated
external defibrillator) across the city of Hamburg, on the real street
network — FastAPI backend, OSMnx-built routing graph, Leaflet.js
frontend. City-wide, not limited to a single district.

**Status note (corrected 2026-10-05):** the backend-based app described in
this repository has **not been deployed anywhere yet**. The URL currently
live at
https://www.cml.hcu-hamburg.de/demos/aed-routing/static/
is a **manually-uploaded static folder** — an older, Hamburg-Mitte-only
prototype with precomputed GeoJSON and no backend. It does come from this
repository: its `index.html` and `app.js` are byte-identical (SHA-1
`8fe27e138029…` and `be45eb71492b…`) to the `static/index.html` and
`static/app.js` retired in commit 1b63142. Being a hand-uploaded copy,
it does not receive changes made here unless someone re-uploads it.

It is **broken today**: its basemap is CARTO `light_all`, which since late
August 2026 requires an API key. Without one, every tile request returns
HTTP 200 with the same 2049-byte PNG showing "API KEY REQUIRED" instead
of map content, at any zoom level and with or without a Referer
(measured 2026-10-05, see `docs/decisions.md`). The basemap fix in this
repository (OpenFreeMap) does not reach that folder.

Once (if) this backend app is deployed, the recommended public URL is the
base path, without `/static/`:
https://www.cml.hcu-hamburg.de/demos/aed-routing/
— see `README_deploy.md`, including its note on why that deployment is
not currently possible on the existing HCU infrastructure.

Car mode is currently disabled in the UI, pending a team decision on how
to fix its known routing gap (see `docs/decisions.md`).

For installation, configuration, and deployment instructions, see
**`README_deploy.md`** — this file does not duplicate them.
