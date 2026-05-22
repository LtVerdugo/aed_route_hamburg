# Deployment Guide — AED Route Hamburg

## Prerequisites
- Python 3.10 or higher
- pip

## Steps

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

### 6. Access the app
Once the server is ready you will see this log line:
  Flask app ready.

The app is then accessible at:
  http://<server-ip>:5050

If the server is behind a reverse proxy (nginx, Apache), point the proxy to port 5050.
