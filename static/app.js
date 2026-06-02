// ── State ──────────────────────────────────────────────────────
const state = {
  aedMarkers: [],
  isochroneLayers: null,
  isochronesVisible: false,
};

// ── Map init ───────────────────────────────────────────────────
const map = L.map("map", { zoomControl: false }).setView(
  [53.5488, 9.9872], 13
);

L.tileLayer(
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  {
    attribution: "© OpenStreetMap © CARTO",
    subdomains: "abcd",
    maxZoom: 19,
  }
).addTo(map);

L.control.zoom({ position: "topright" }).addTo(map);

// ── Custom panes for z-order control ──────────────────────────
map.createPane("isochronePane");
map.getPane("isochronePane").style.zIndex = 350;
map.createPane("aedPane");
map.getPane("aedPane").style.zIndex = 450;

// ── Load and draw AEDs ─────────────────────────────────────────
async function loadAEDs() {
  const res = await fetch("./data/hamburg_mitte_aeds.geojson");
  const fc = await res.json();
  fc.features.forEach((f) => {
    if (f.geometry.type !== "Point") return;
    const [lon, lat] = f.geometry.coordinates;
    const marker = L.circleMarker([lat, lon], {
      radius: 5,
      color: "#dc2626",
      fillColor: "#dc2626",
      fillOpacity: 0.85,
      weight: 1,
      pane: "aedPane",
    }).addTo(map);
    const p = f.properties;
    marker.bindTooltip(
      `AED ${p.osm_id}<br>${p.name || "—"}<br>${p.access || "—"}`
    );
    state.aedMarkers.push(marker);
  });
}

// ── Load and draw Hamburg-Mitte boundary ──────────────────────
async function loadBoundary() {
  const res = await fetch("./data/hamburg_mitte_boundary.geojson");
  const fc = await res.json();

  L.geoJSON(fc, {
    style: { color: "#2563eb", weight: 2, fillOpacity: 0 }
  }).addTo(map);
}

// ── Load isochrones ────────────────────────────────────────────
async function loadIsochrones() {
  const res = await fetch("./data/hamburg_mitte_isochrones_walk.geojson");
  const fc = await res.json();

  // Separate features by time threshold
  const features_2min = fc.features.filter(
    f => f.properties.time_s === 120
  );
  const features_4min = fc.features.filter(
    f => f.properties.time_s === 240
  );

  // Draw 4min layer first (below), then 2min on top
  const layer_4min = L.geoJSON(
    { type: "FeatureCollection", features: features_4min },
    {
      style: {
        fillColor: "#f97316",
        fillOpacity: 0.12,
        stroke: false,
        interactive: false,
      },
      pane: "isochronePane",
    }
  );

  const layer_2min = L.geoJSON(
    { type: "FeatureCollection", features: features_2min },
    {
      style: {
        fillColor: "#16a34a",
        fillOpacity: 0.25,
        stroke: false,
        interactive: false,
      },
      pane: "isochronePane",
    }
  );

  // Store layers in state for toggle
  state.isochroneLayers = { layer_2min, layer_4min };
  state.isochronesVisible = false;
}

function toggleIsochrones() {
  if (!state.isochroneLayers) return;
  const { layer_2min, layer_4min } = state.isochroneLayers;

  if (state.isochronesVisible) {
    map.removeLayer(layer_4min);
    map.removeLayer(layer_2min);
    state.isochronesVisible = false;
  } else {
    layer_4min.addTo(map);
    layer_2min.addTo(map);
    state.isochronesVisible = true;
  }
}

// ── Layer toggles ──────────────────────────────────────────────
document.getElementById("toggle-aeds").addEventListener("change", (e) => {
  const checked = e.target.checked;
  state.aedMarkers.forEach(m => checked ? m.addTo(map) : map.removeLayer(m));
});

document.getElementById("toggle-isochrones").addEventListener("change", toggleIsochrones);

// ── Init ───────────────────────────────────────────────────────
loadAEDs().catch(err => console.error("Failed to load AEDs:", err));
loadBoundary().catch(err => console.error("Failed to load boundary:", err));
loadIsochrones().catch(err => console.error("Failed to load isochrones:", err));
