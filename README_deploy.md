# Deployment Guide — AED Route Hamburg

## Prerequisites
- Python 3.10 or higher
- pip

## Steps

Important: this project is not a static-only website. The `static/`
directory contains the browser UI, but routing, AED data, boundaries, and
isochrones are served by **FastAPI** (via `uvicorn`) through `/api/...`.
Uploading only `static/` will render the page without a working backend.

Note on `static/`: it contains two frontend variants. `index_original.html`
+ `app_original.js` is the live one, served at `GET /` (see `app/app.py`) and
connected to the API described in this document. `index.html` + `app.js` is
an older, unlinked static prototype (no backend calls, hardcoded demo data,
Hamburg-Mitte-only GeoJSON under `static/data/`) — it is not served at any
route and is only reachable by navigating directly to `/static/index.html`.
Its disposition (keep as-is, archive, or remove) is a pending decision, not
yet made.

### 1. Copy the project
Transfer the project folder to the server. The final structure should look like this:

aed_route_hamburg/
├── app/
│   └── app.py
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
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── requirements.txt
└── wsgi.py

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

uvicorn app.app:app --host 0.0.0.0 --port 5000 --reload

**Port note:** the port used across this repo's files is currently
inconsistent — `app/app.py`'s own `__main__` block defaults to 5050, while
`app/wsgi.py`, `Dockerfile`, `docker-compose.yml` and `docs/apache.conf` use
5000. This is a known, tracked inconsistency (see `docs/decisions.md`),
pending unification in a later remediation phase. Use whatever port you
pass explicitly to `uvicorn --port`, and make sure it matches your reverse
proxy configuration — do not assume 5000 or 5050 without checking both ends.

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

### 6. Configure the public URL
The recommended public URL is:

  https://www.cml.hcu-hamburg.de/demos/aed-routing/

Do not publish the app as `/demos/aed-routing/static/`. The `static/`
folder is an implementation detail; users should land on the FastAPI index
route (`GET /`, `app/app.py`).

If nginx strips the public prefix before forwarding to uvicorn, no extra
environment variable is needed:

```nginx
location /demos/aed-routing/ {
    proxy_pass http://127.0.0.1:5050/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

If the reverse proxy forwards the prefix through unchanged, start uvicorn
with `PUBLIC_BASE_PATH` (note, added 2026-08-14: `PUBLIC_BASE_PATH` is not
actually read anywhere in this repo's code — verified by grep against
`app/` and `src/`. This whole paragraph describes a configuration mode that
does not exist today; not fixed further in this pass, flagged for later
triage):

```bash
uvicorn app.app:app --host 0.0.0.0 --port 5000 --reload
```

Example nginx config for that mode:

```nginx
location /demos/aed-routing/ {
    proxy_pass http://127.0.0.1:5050;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### 7. Access and verify the app
Once the server is ready you will see this log line:
  FastAPI app ready.

The app is then accessible at:
  http://<server-ip>:5050

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
