# Deployment Guide — AED Route Hamburg

## Prerequisites
- Python 3.10 or higher
- pip

## Steps

Important: this project is not a static-only website. The `static/`
directory contains the browser UI, but routing, AED data, boundaries, and
isochrones are served by **FastAPI** (via `uvicorn`) through `/api/...`.
Uploading only `static/` will render the page without a working backend.

Note on `static/` (updated 2026-08-17, Ítem 8A(3)): it used to contain a
second, unlinked static prototype (`index.html` + `app.js` + `styles.css`,
Hamburg-Mitte-only, hardcoded demo data under `static/data/`). That
prototype has been retired — `static/` now contains only the live
frontend: `index_original.html` + `app_original.js` + `styles_original.css`,
served at `GET /` (see `app/app.py`) and connected to the API described in
this document.

### 1. Copy the project
Transfer the project folder to the server. The final structure should look like this:

aed_route_hamburg/
├── app/
│   ├── app.py
│   └── wsgi.py
├── data/
│   ├── interim/
│   │   └── hamburg_graph.pkl        ← 364 MB, must be present
│   └── processed/
│       ├── hamburg_aeds.geojson
│       ├── hamburg_boundary.geojson
│       └── hamburg_isochrones_walk.geojson
├── docs/
├── src/
│   └── aed_route/
├── static/
│   ├── app_original.js
│   ├── index_original.html
│   └── styles_original.css
└── requirements.txt

### 2. Create and activate a virtual environment
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

### 3. Install dependencies
pip install -r requirements.txt

### 4. Verify data files
Before starting the server, confirm that all four cache files are present:

data/processed/hamburg_aeds.geojson
data/processed/hamburg_boundary.geojson
data/processed/hamburg_isochrones_walk.geojson
data/interim/hamburg_graph.pkl

Their absence is handled differently per file (verified against the actual
code, not assumed) — do not rely on all of them failing the same way:

- **`hamburg_aeds.geojson` missing → the app crashes on launch** with an
  explicit `RuntimeError` (`app/app.py`, `_require_cache`).
- **`hamburg_graph.pkl` missing → the app does NOT crash.** It falls back to
  building the graph live from OSMnx (`load_or_build_graph_bundle` in
  `src/aed_route/graph_builder_osm.py`), which downloads the walk/bike/drive
  networks for all of Hamburg from Overpass — a slow, network-dependent
  operation, not a fast failure. Do not assume a missing graph file will be
  caught quickly at startup.
- **`hamburg_isochrones_walk.geojson` missing → the app does NOT crash.** It
  recomputes isochrones at startup (`compute_isochrones`, also not fast at
  full-Hamburg scale if run from scratch).
- **`hamburg_boundary.geojson` missing → no effect at startup.** The file is
  only read when a request actually hits `GET /api/boundary`
  (`app/app.py`); if missing at that point, the request fails with an
  unhandled `FileNotFoundError` (HTTP 500), not a startup crash.

They must be copied manually to the server alongside the code regardless —
only the AED cache is guaranteed to fail fast if you forget one.

### 5. Start the server
Run this command from the project root (this project runs on **uvicorn**,
not Gunicorn — there is no Gunicorn config anywhere in this repo):

uvicorn app.app:app --host 0.0.0.0 --port 5000

**`--reload` note (resolved 2026-08-17):** this command previously included
`--reload`, a uvicorn flag meant for development — it restarts the whole
process whenever it detects a file change under the project directory.
With the 364 MB graph bundle taking real time to reload from disk, a
spurious restart (e.g. from a log file or a docs edit touching the watched
tree) leaves the service down for that long, in production, for no
reason. It also contradicted this repo's own `Dockerfile`, whose `CMD`
never included it. Removed; the command above now matches `Dockerfile`'s
`CMD` exactly (same host/port, no `--reload`, no explicit `--workers` —
uvicorn defaults to 1 worker, which is also the hard requirement noted
below).

**Port note (resolved 2026-08-14):** the canonical port across this repo is
now **5000** — unified in `app/app.py`, `app/wsgi.py`, `Dockerfile`,
`docker-compose.yml` and `docs/apache.conf` (this document previously
described an inconsistency between 5000 and 5050; that inconsistency is
now fixed in the code and docs). **This choice was made for internal
consistency between this repo's own files — it has NOT been verified
against the actual reverse proxy configuration running on the HCU server.**
`docs/apache.conf` is a snippet kept in this repo, not proof of what is
actually configured in production. If the real deployed proxy points to
5050, this change will make the service unreachable until that proxy
config is updated to match. Verify the live proxy configuration before the
next deployment — see `docs/decisions.md`.

Important notes:
- --workers must be 1. The graph bundle (364 MB) is loaded into memory once at startup and is not safe to share across multiple worker processes.
- The graph bundle load itself (when the cache file is present, which is the
  normal case) takes roughly 5 seconds in practice, not "20-30 seconds" —
  most of that time is `pickle.load` on the 364 MB file. If
  `hamburg_graph.pkl` is missing and the app falls back to a live OSMnx
  rebuild (see step 4), the wait is much longer and depends on network
  conditions, not a fixed 20-30 s window.
- Since this project runs on uvicorn (not Gunicorn), there is no
  `--timeout`/worker-kill concern to configure — uvicorn does not impose a
  startup timeout on its own worker process the way Gunicorn's default
  configuration can.
- Startup also computes the graph's giant weakly connected component
  (Fase 7, 2026-08-14 — used to restrict origin snapping, see
  `docs/decisions.md`), adding roughly **0.85 seconds** on top of the
  above: ~0.7s to checksum the 364 MB graph pickle (to detect a stale
  cache — see `docs/decisions.md`) plus ~0.15s to rebuild the filtered
  spatial index, whether the giant-component result itself is loaded from
  cache or computed fresh. Negligible next to the ~5s graph load, included
  here for completeness since every added startup cost was asked to be
  tracked explicitly during this remediation.

### 6. Configure the public URL
The recommended public URL is:

  https://www.cml.hcu-hamburg.de/demos/aed-routing/

Do not publish the app as `/demos/aed-routing/static/`. The `static/`
folder is an implementation detail; users should land on the FastAPI index
route (`GET /`, `app/app.py`).

This deployment requires the reverse proxy to strip the public prefix
before forwarding to uvicorn — `app/app.py` instantiates `FastAPI()` with
no `root_path` and no `X-Forwarded-*` middleware (verified by reading
`app/app.py`; every route is registered at its bare path: `/`, `/api/aeds`,
`/healthz`, etc., never at `/demos/aed-routing/...`). No extra environment
variable is needed for this mode:

```nginx
location /demos/aed-routing/ {
    proxy_pass http://127.0.0.1:5000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

**Forwarding the prefix through unchanged is NOT supported today.**
A previous revision of this document described a `PUBLIC_BASE_PATH`
environment variable for that scenario; confirmed by grep against `app/`
and `src/` that no such variable is read anywhere in this repo's code —
it never did anything. Diagnosed 2026-08-14 (see `docs/decisions.md`): if
the real proxy does not strip `/demos/aed-routing/` before forwarding,
every route — including the root page — returns 404 from the backend
**before any HTML is ever served**; there is no working nginx
configuration for this mode with the code as it stands today. Supporting
it would require adding `root_path` and/or `X-Forwarded-*` middleware to
the `FastAPI()` instance in `app/app.py` — a code change, out of scope
for this remediation. Confirm with whoever manages the real HCU reverse
proxy that it strips the prefix (the config above) before deploying —
this has **not** been verified against the actual production proxy
configuration.

### 7. Access and verify the app
Once the server is ready you will see this log line:
  FastAPI app ready.

The app is then accessible at:
  http://<server-ip>:5000

or, behind the CML reverse proxy:
  https://www.cml.hcu-hamburg.de/demos/aed-routing/

Check these URLs after deployment:

```bash
curl https://www.cml.hcu-hamburg.de/demos/aed-routing/healthz
curl https://www.cml.hcu-hamburg.de/demos/aed-routing/api/aeds
curl https://www.cml.hcu-hamburg.de/demos/aed-routing/api/boundary
```

The first should return `{"ok":true}`. The API checks should return GeoJSON
or JSON, not a 404 HTML page.
