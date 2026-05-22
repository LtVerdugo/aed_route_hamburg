// ── State ──────────────────────────────────────────────────────
const state = {
  mode: "walk",
  results: [],
  showAlternatives: false,
  routeLayers: [],
  altLayers: [],
  originMarker: null,
  aedMarkers: [],
  isochroneLayers: null,
  isochronesVisible: false,
};

// ── Map init ───────────────────────────────────────────────────
const map = L.map("map", { zoomControl: false }).setView(
  [53.5511, 9.9937], 12
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
map.createPane("originPane");
map.getPane("originPane").style.zIndex = 460;

// ── Constants ──────────────────────────────────────────────────
const ROUTE_ANIM_MS = 3000; // Route draw animation duration in ms
const isValidCoord = (c) => c && c[0] != null && c[1] != null;
// Large overscan in Leaflet layer-point units — must exceed the visible
// viewport at any zoom level to ensure the mask covers the full canvas.
const MASK_OVERSCAN = 50000;

// ── Load and draw AEDs ─────────────────────────────────────────
async function loadAEDs() {
  const res = await fetch("/api/aeds");
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
      `AED ${p.id}<br>${p.name || "—"}<br>${p.access || "—"}`
    );
    state.aedMarkers.push(marker);
  });
}

// ── Mode selector ──────────────────────────────────────────────
document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mode-btn").forEach(
      (b) => b.classList.remove("active")
    );
    btn.classList.add("active");
    state.mode = btn.dataset.mode;
  });
});

// ── Compare toggle ─────────────────────────────────────────────
document.getElementById("btn-compare").addEventListener("click", () => {
  state.showAlternatives = !state.showAlternatives;
  const btn = document.getElementById("btn-compare");
  btn.classList.toggle("active", state.showAlternatives);
  const altDiv = document.getElementById("result-alternatives");
  altDiv.style.display = state.showAlternatives ? "block" : "none";
  drawAlternatives();
});

// ── Map click ──────────────────────────────────────────────────
map.on("click", async (e) => {
  const { lat, lng } = e.latlng;
  showLoading();

  // Origin marker
  if (state.originMarker) state.originMarker.remove();
  state.originMarker = L.circleMarker([lat, lng], {
    radius: 8,
    color: "#ffffff",
    fillColor: "#2563eb",
    fillOpacity: 1,
    weight: 3,
    pane: "originPane",
  }).addTo(map);

  try {
    const res = await fetch("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lon: lng, mode: state.mode }),
    });
    const data = await res.json();
    state.results = data.results || [];
    renderPanel();
    drawRoutes();
  } catch (err) {
    console.error("Routing error details:", err);
    showHint();
  }
});

// ── Render panel ───────────────────────────────────────────────
function renderPanel() {
  if (!state.results.length) { showHint(); return; }

  document.getElementById("hint").style.display = "none";
  document.getElementById("loading").style.display = "none";
  document.getElementById("results").style.display = "block";

  const best = state.results[0];
  document.getElementById("result-best").innerHTML =
    buildCard(best, true);

  const altHtml = state.results.slice(1).map(
    (r) => buildCard(r, false, best.total_time_s)
  ).join("");
  document.getElementById("result-alternatives").innerHTML = altHtml;
  document.getElementById("result-alternatives").style.display =
    state.showAlternatives ? "block" : "none";

  const btn = document.getElementById("btn-compare");
  btn.classList.toggle("active", state.showAlternatives);
}

// ── Time formatting helper ─────────────────────────────────────
function formatTime(s, skipZeroMins = false) {
  const mins = Math.floor(s / 60);
  const secs = Math.round(s % 60);
  if (skipZeroMins && mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function buildCard(r, isBest, bestTime = 0) {
  const timeStr = formatTime(r.total_time_s);
  const distStr = `${Math.round(r.total_length_m)} m`;

  let extraHtml = "";
  if (!isBest) {
    const extra = r.total_time_s - bestTime;
    extraHtml = `<div class="extra-time">+${formatTime(extra, true)} longer</div>`;
  }

  const rankLabel = isBest ? "⭐ Nearest AED" : `#${r.rank}`;
  const cardClass = isBest ? "best" : "alternative";

  return `
    <div class="result-card ${cardClass}">
      <div class="rank-label">${rankLabel}</div>
      ${extraHtml}
      <div class="time">${timeStr}</div>
      <div class="distance">${distStr}</div>
      <div class="aed-meta">
        ID: ${r.aed_id || "—"}<br>
        ${r.aed_name ? "Name: " + r.aed_name + "<br>" : ""}
        ${r.aed_access ? "Access: " + r.aed_access : ""}
        ${r.aed_opening_hours
          ? "<br>Hours: " + r.aed_opening_hours : ""}
      </div>
    </div>`;
}

// ── Draw routes on map ─────────────────────────────────────────
function drawRoutes() {
  // Clear previous routes
  state.routeLayers.forEach((l) => l.remove());
  state.routeLayers = [];
  state.altLayers.forEach((l) => l.remove());
  state.altLayers = [];

  if (!state.results.length) return;

  const best = state.results[0];

  // Step 1: fitBounds immediately — frame origin + AED
  if (state.originMarker && best.aed_lat && best.aed_lon) {
    const bounds = L.latLngBounds(
      state.originMarker.getLatLng(),
      [best.aed_lat, best.aed_lon]
    );
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 17 });
  }

  // Step 2: build full coordinate array for the best route
  const allCoords = [];
  best.edges.forEach((edge) => {
    if (!edge.coords || edge.coords.length < 2) return;
    const validCoords = edge.coords.filter(isValidCoord);
    validCoords.forEach(([lon, lat]) => allCoords.push([lat, lon]));
  });

  if (allCoords.length < 2) return;

  // Step 3: draw route progressively with leaflet.motion + easeInOutQuart
  const motionLine = L.motion.polyline(allCoords, {
    color: "#16a34a",
    weight: 5,
    opacity: 0.9,
  }, {
    auto: true,
    duration: ROUTE_ANIM_MS,
    easing: L.Motion.Ease.easeInOutQuart,
  }, {
    removeOnEnd: false,
    showMarker: false,
  }).addTo(map);
  state.routeLayers.push(motionLine);

  setTimeout(() => {
    // Remove motion line and replace with antPath for the flow effect
    motionLine.remove();
    const antLine = L.polyline.antPath(allCoords, {
      delay: 800,
      dashArray: [10, 20],
      weight: 5,
      color: "#16a34a",
      pulseColor: "#ffffff",
      opacity: 0.9,
      paused: false,
      reverse: false,
      hardwareAccelerated: true,
    }).addTo(map);
    state.routeLayers.push(antLine);
    showAedPin(best);
  }, ROUTE_ANIM_MS);
  drawAlternatives();
}

// ── Draw or clear alternative routes ──────────────────────────
function drawAlternatives() {
  // Remove existing alternative layers (stored separately in state)
  state.altLayers.forEach((l) => l.remove());
  state.altLayers = [];

  if (!state.showAlternatives || state.results.length < 2) return;

  state.results.slice(1).forEach((r) => {
    r.edges.forEach((edge) => {
      if (!edge.coords || edge.coords.length < 2) return;
      const validCoords = edge.coords.filter(isValidCoord);
      if (validCoords.length < 2) return;
      const latlngs = validCoords.map(([lon, lat]) => [lat, lon]);
      const line = L.polyline(latlngs, {
        color: "#6b7280",
        weight: 3,
        opacity: 0.6,
        dashArray: "8 6",
      }).addTo(map);
      state.altLayers.push(line);
    });
  });
}

// ── Show AED pin after animation completes ────────────────────
function showAedPin(r) {
  if (!r.aed_lat || !r.aed_lon) return;

  const aedPin = L.marker([r.aed_lat, r.aed_lon], {
    icon: L.divIcon({
      className: "",
      html: `
        <div style="position:relative; width:32px; height:32px;">
          <div style="
            position:absolute; top:0; left:0;
            width:32px; height:32px;
            background:#16a34a;
            border:3px solid #fff;
            border-radius:50% 50% 50% 0;
            transform:rotate(-45deg);
            box-shadow:0 2px 6px rgba(0,0,0,0.3);
          "></div>
          <div style="
            position:absolute; top:50%; left:50%;
            width:32px; height:32px;
            transform:translate(-50%, -50%);
            border-radius:50%;
            background:rgba(22,163,74,0.4);
            animation:aed-pulse 1.5s ease-out infinite;
          "></div>
        </div>
      `,
      iconSize: [32, 32],
      iconAnchor: [16, 32],
    }),
  }).addTo(map);

  aedPin.bindTooltip(
    `AED ${r.aed_id} · ${formatTime(r.total_time_s)}`
  );
  state.routeLayers.push(aedPin);
}

// ── UI helpers ─────────────────────────────────────────────────
function showLoading() {
  document.getElementById("hint").style.display = "none";
  document.getElementById("results").style.display = "none";
  document.getElementById("loading").style.display = "block";
}

function showHint() {
  document.getElementById("hint").style.display = "block";
  document.getElementById("results").style.display = "none";
  document.getElementById("loading").style.display = "none";
}

// ── Load and draw Hamburg boundary ────────────────────────────
async function loadBoundary() {
  const res = await fetch("/api/boundary");
  const fc = await res.json();

  L.geoJSON(fc, {
    style: { color: "#2563eb", weight: 2, fillOpacity: 0 }
  }).addTo(map);

  map.on("moveend zoomend viewreset", () => updateMask(fc));
  updateMask(fc);
}

function updateMask(fc) {
  const existing = document.getElementById("hamburg-mask");
  if (existing) existing.remove();

  const svg = document.querySelector(".leaflet-overlay-pane svg");
  if (!svg) return;

  const geom = fc.features[0]?.geometry;
  if (!geom) return;

  let rings = [];
  if (geom.type === "Polygon") {
    rings = [geom.coordinates[0]];
  } else if (geom.type === "MultiPolygon") {
    rings = geom.coordinates.map(p => p[0]);
  }

  const toPixel = (coord) => {
    const pt = map.latLngToLayerPoint([coord[1], coord[0]]);
    return `${pt.x},${pt.y}`;
  };

  let d = `M${-MASK_OVERSCAN},${-MASK_OVERSCAN} L${MASK_OVERSCAN},${-MASK_OVERSCAN} L${MASK_OVERSCAN},${MASK_OVERSCAN} L${-MASK_OVERSCAN},${MASK_OVERSCAN} Z `;
  rings.forEach(ring => {
    d += "M" + ring.map(toPixel).join(" L") + " Z ";
  });

  const path = document.createElementNS(
    "http://www.w3.org/2000/svg", "path"
  );
  path.setAttribute("id", "hamburg-mask");
  path.setAttribute("d", d);
  path.setAttribute("fill", "white");
  path.setAttribute("fill-opacity", "0.45");
  path.setAttribute("fill-rule", "evenodd");
  path.setAttribute("pointer-events", "none");
  svg.appendChild(path);
}

// ── Load isochrones ────────────────────────────────────────────
async function loadIsochrones() {
  const res = await fetch("/api/isochrones?v=" + Date.now());
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

document.getElementById("toggle-mask").addEventListener("change", (e) => {
  const mask = document.getElementById("hamburg-mask");
  if (mask) mask.style.display = e.target.checked ? "" : "none";
});

// ── Init ───────────────────────────────────────────────────────
loadAEDs().catch(err => console.error("Failed to load AEDs:", err));
loadBoundary().catch(err => console.error("Failed to load boundary:", err));
loadIsochrones().catch(err => console.error("Failed to load isochrones:", err));

// ── Help popup ─────────────────────────────────────────────────
document.getElementById("btn-got-it").addEventListener("click", () => {
  document.getElementById("help-overlay").style.display = "none";
});

document.getElementById("btn-how-to-use").addEventListener("click", () => {
  document.getElementById("help-overlay").style.display = "flex";
});
