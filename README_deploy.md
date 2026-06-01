# Deployment Guide — AED Route Hamburg

## Prerequisites
- Python 3.10 or higher
- pip

## Steps

Important: this project is not a static-only website. The `static/`
directory contains the browser UI, but routing, AED data, boundaries, and
isochrones are served by Flask through `/api/...`. Uploading only `static/`
will render the page without a working backend.

### 1. Copy the project
Transfer the project folder to the server. The final structure should look like this:

aed_route_hamburg/
├── app/
│   └── flask_app.py
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

These files are NOT downloaded automatically at startup. If any of them is missing the app will crash on launch. They must be copied manually to the server alongside the code.

### 5. Start the server
Run this command from the project root:

gunicorn --workers 1 --bind 0.0.0.0:5050 --timeout 120 wsgi:app

Important notes:
- --workers must be 1. The graph bundle (364 MB) is loaded into memory once at startup and is not safe to share across multiple worker processes.
- --timeout 120 is required because the graph takes 20-30 seconds to load on first startup. Without this, Gunicorn will kill the worker before it finishes loading.
- The app will be silent for 20-30 seconds on first start while the graph loads. This is normal.

### 6. Configure the public URL
The recommended public URL is:

  https://www.cml.hcu-hamburg.de/demos/aed-routing/

Do not publish the app as `/demos/aed-routing/static/`. The `static/`
folder is an implementation detail; users should land on the Flask index
route.

If nginx strips the public prefix before forwarding to Gunicorn, no extra
environment variable is needed:

```nginx
location /demos/aed-routing/ {
    proxy_pass http://127.0.0.1:5050/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

If the reverse proxy forwards the prefix through to Flask unchanged, start
Gunicorn with `PUBLIC_BASE_PATH`:

```bash
PUBLIC_BASE_PATH=/demos/aed-routing \
gunicorn --workers 1 --bind 0.0.0.0:5050 --timeout 120 wsgi:app
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
  Flask app ready.

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
