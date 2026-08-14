// ── State ──────────────────────────────────────────────────────
const state = {
  showAlternatives: false,
  routeLayers: [],
  altLayers: [],
  originMarker: null,
  aedMarkers: [],
  isochroneLayers: null,
  isochronesVisible: false,
};

const DEMO_DATA = {
  "origin": { "lat": 53.5503, "lon": 9.9927 },
  "results": [
    {
      "rank": 1,
      "aed_id": 12927362709,
      "aed_lat": 53.5487088,
      "aed_lon": 9.9905612,
      "aed_name": null,
      "aed_access": null,
      "total_time_s": 165.8,
      "total_length_m": 281.9,
      "edges": [
        {"coords": [[9.9931372,53.5503105],[9.9932126,53.5503529]]},
        {"coords": [[9.9932126,53.5503529],[9.9933458,53.5502661]]},
        {"coords": [[9.9933458,53.5502661],[9.993402,53.5502291]]},
        {"coords": [[9.993402,53.5502291],[9.9932817,53.5501228]]},
        {"coords": [[9.9932817,53.5501228],[9.9932275,53.5500617]]},
        {"coords": [[9.9932275,53.5500617],[9.9930475,53.5499621]]},
        {"coords": [[9.9930475,53.5499621],[9.9926706,53.5497367]]},
        {"coords": [[9.9926706,53.5497367],[9.9924784,53.5496275]]},
        {"coords": [[9.9924784,53.5496275],[9.9921718,53.5494496]]},
        {"coords": [[9.9921718,53.5494496],[9.9919903,53.5493392]]},
        {"coords": [[9.9919903,53.5493392],[9.9918847,53.5492748]]},
        {"coords": [[9.9918847,53.5492748],[9.9918444,53.549249]]},
        {"coords": [[9.9918444,53.549249],[9.9917799,53.5492108]]},
        {"coords": [[9.9917799,53.5492108],[9.9917153,53.5491758]]},
        {"coords": [[9.9917153,53.5491758],[9.9916496,53.5491433]]},
        {"coords": [[9.9916496,53.5491433],[9.9915839,53.5491135]]},
        {"coords": [[9.9915839,53.5491135],[9.9915366,53.5490924]]},
        {"coords": [[9.9915366,53.5490924],[9.9912665,53.5489738]]},
        {"coords": [[9.9912665,53.5489738],[9.9911437,53.5489097]]},
        {"coords": [[9.9911437,53.5489097],[9.9910566,53.5488642]]},
        {"coords": [[9.9910566,53.5488642],[9.9909665,53.5488233]]},
        {"coords": [[9.9909665,53.5488233],[9.990686,53.5487041]]},
        {"coords": [[9.990686,53.5487041],[9.9905612,53.5487088]]}
      ]
    },
    {
      "rank": 2,
      "aed_id": 3966894112,
      "aed_lat": 53.5513925,
      "aed_lon": 9.9962545,
      "aed_name": null,
      "aed_access": "yes",
      "total_time_s": 201.3,
      "total_length_m": 342.1,
      "edges": [
        {"coords": [[9.9931372,53.5503105],[9.9932126,53.5503529]]},
        {"coords": [[9.9932126,53.5503529],[9.9933458,53.5502661]]},
        {"coords": [[9.9933458,53.5502661],[9.993402,53.5502291]]},
        {"coords": [[9.993402,53.5502291],[9.9936048,53.5503386]]},
        {"coords": [[9.9936048,53.5503386],[9.9938579,53.5504663]]},
        {"coords": [[9.9938579,53.5504663],[9.994102,53.550616]]},
        {"coords": [[9.994102,53.550616],[9.9941729,53.5506595]]},
        {"coords": [[9.9941729,53.5506595],[9.9942354,53.5506939]]},
        {"coords": [[9.9942354,53.5506939],[9.9939831,53.5508447]]},
        {"coords": [[9.9939831,53.5508447],[9.9939492,53.5508649]]},
        {"coords": [[9.9939492,53.5508649],[9.9939316,53.5508768]]},
        {"coords": [[9.9939316,53.5508768],[9.994072,53.5509575]]},
        {"coords": [[9.994072,53.5509575],[9.9941379,53.5509955]]},
        {"coords": [[9.9941379,53.5509955],[9.9941609,53.5510077]]},
        {"coords": [[9.9941609,53.5510077],[9.9942354,53.5510137]]},
        {"coords": [[9.9942354,53.5510137],[9.9942901,53.5510378]]},
        {"coords": [[9.9942901,53.5510378],[9.9943667,53.5510823]]},
        {"coords": [[9.9943667,53.5510823],[9.9945271,53.5511676]]},
        {"coords": [[9.9945271,53.5511676],[9.9945293,53.5511925]]},
        {"coords": [[9.9945293,53.5511925],[9.9945364,53.5511959]]},
        {"coords": [[9.9945364,53.5511959],[9.9946496,53.5512579]]},
        {"coords": [[9.9946496,53.5512579],[9.9947186,53.551291]]},
        {"coords": [[9.9947186,53.551291],[9.9948662,53.5513618]]},
        {"coords": [[9.9948662,53.5513618],[9.9951072,53.5511752]]},
        {"coords": [[9.9951072,53.5511752],[9.9956618,53.5514786]]},
        {"coords": [[9.9956618,53.5514786],[9.9958097,53.5515636]]},
        {"coords": [[9.9958097,53.5515636],[9.9959743,53.5515327]]},
        {"coords": [[9.9959743,53.5515327],[9.9961048,53.551477]]},
        {"coords": [[9.9961048,53.551477],[9.9962499,53.5513729]]},
        {"coords": [[9.9962499,53.5513729],[9.9962545,53.5513925]]}
      ]
    },
    {
      "rank": 3,
      "aed_id": 13195378701,
      "aed_lat": 53.5523955,
      "aed_lon": 9.9904297,
      "aed_name": null,
      "aed_access": "customers",
      "total_time_s": 204.8,
      "total_length_m": 348.2,
      "edges": [
        {"coords": [[9.9931372,53.5503105],[9.9932126,53.5503529]]},
        {"coords": [[9.9932126,53.5503529],[9.9927907,53.5506287]]},
        {"coords": [[9.9927907,53.5506287],[9.9929953,53.5507359]]},
        {"coords": [[9.9929953,53.5507359],[9.9923941,53.5511461]]},
        {"coords": [[9.9923941,53.5511461],[9.9920802,53.5513983]]},
        {"coords": [[9.9920802,53.5513983],[9.9920603,53.5514161]]},
        {"coords": [[9.9920603,53.5514161],[9.9920531,53.5514216]]},
        {"coords": [[9.9920531,53.5514216],[9.9919541,53.5515052]]},
        {"coords": [[9.9919541,53.5515052],[9.9918609,53.551584]]},
        {"coords": [[9.9918609,53.551584],[9.9917942,53.5516404]]},
        {"coords": [[9.9917942,53.5516404],[9.9917702,53.5516589]]},
        {"coords": [[9.9917702,53.5516589],[9.9914258,53.5519388]]},
        {"coords": [[9.9914258,53.5519388],[9.9914128,53.5519494]]},
        {"coords": [[9.9914128,53.5519494],[9.9913589,53.551993]]},
        {"coords": [[9.9913589,53.551993],[9.9909588,53.5523296]]},
        {"coords": [[9.9909588,53.5523296],[9.9907519,53.5524999]]},
        {"coords": [[9.9907519,53.5524999],[9.9907398,53.5525088]]},
        {"coords": [[9.9907398,53.5525088],[9.9903694,53.5523642]]},
        {"coords": [[9.9903694,53.5523642],[9.9904297,53.5523955]]}
      ]
    }
  ]
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
map.createPane("originPane");
map.getPane("originPane").style.zIndex = 460;

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

// ── Demo ───────────────────────────────────────────────────────
function runDemo() {
  resetDemo();

  const origin = DEMO_DATA.origin;
  const results = DEMO_DATA.results;
  const best = results[0];

  const firstCoord = best.edges[0].coords[0];
  const snapLat = firstCoord[1];
  const snapLon = firstCoord[0];

  state.originMarker = L.circleMarker(
    [snapLat, snapLon], {
    radius: 8,
    color: "#ffffff",
    fillColor: "#2563eb",
    fillOpacity: 1,
    weight: 3,
    pane: "originPane",
  }).addTo(map);

  const bounds = L.latLngBounds(
    [snapLat, snapLon],
    [best.aed_lat, best.aed_lon]
  );
  map.fitBounds(bounds, { padding: [80, 80], maxZoom: 17 });

  const allCoords = [];
  best.edges.forEach(edge => {
    (edge.coords || []).forEach(([lon, lat]) => {
      allCoords.push([lat, lon]);
    });
  });

  if (allCoords.length >= 2) {
    animateLine(allCoords, () => { showAedPin(best); });
  }

  renderDemoPanel(results);

  document.getElementById("btn-demo").style.display = "none";
  document.getElementById("btn-reset").style.display = "block";
}

function resetDemo() {
  if (state.originMarker) {
    state.originMarker.remove();
    state.originMarker = null;
  }
  state.routeLayers.forEach(l => l.remove());
  state.routeLayers = [];
  state.altLayers.forEach(l => l.remove());
  state.altLayers = [];
  state.showAlternatives = false;

  document.getElementById("results").style.display = "none";
  document.getElementById("result-alternatives")
    .style.display = "none";
  const btnCompare = document.getElementById("btn-compare");
  btnCompare.classList.remove("active");
  btnCompare.textContent = "Compare routes";

  document.getElementById("btn-demo").style.display = "block";
  document.getElementById("btn-reset").style.display = "none";

  map.setView([53.5488, 9.9872], 13);
}

function animateLine(coords, onComplete) {
  const ROUTE_ANIM_MS = 3000;

  const motionLine = L.motion.polyline(coords, {
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
    motionLine.remove();
    const antLine = L.polyline.antPath(coords, {
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
    if (onComplete) onComplete();
  }, ROUTE_ANIM_MS);
}

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

  const mins = Math.floor(r.total_time_s / 60);
  const secs = Math.round(r.total_time_s % 60);
  aedPin.bindTooltip(
    `AED ${r.aed_id} · ${mins}m ${secs}s`,
    { permanent: false, direction: "top" }
  );
  state.routeLayers.push(aedPin);
}

function renderDemoPanel(results) {
  const best = results[0];
  document.getElementById("result-best").innerHTML =
    buildCard(best, true);
  document.getElementById("result-alternatives").innerHTML =
    results.slice(1).map(
      r => buildCard(r, false, best.total_time_s)
    ).join("");

  document.getElementById("results").style.display = "block";
}

function buildCard(r, isBest, bestTime = 0) {
  const mins = Math.floor(r.total_time_s / 60);
  const secs = Math.round(r.total_time_s % 60);
  const timeStr = `${mins}m ${secs}s`;
  const distStr = `${Math.round(r.total_length_m)} m`;
  const rankLabel = isBest ? "⭐ Nearest AED" : `#${r.rank}`;
  const cardClass = isBest ? "best" : "alternative";

  let extraHtml = "";
  if (!isBest) {
    const extra = r.total_time_s - bestTime;
    const eMins = Math.floor(extra / 60);
    const eSecs = Math.round(extra % 60);
    extraHtml = `<div class="extra-time">+${
      eMins > 0 ? eMins + "m " : ""}${eSecs}s longer</div>`;
  }

  return `
    <div class="result-card ${cardClass}">
      <div class="rank-label">${rankLabel}</div>
      ${extraHtml}
      <div class="time">${timeStr}</div>
      <div class="distance">${distStr}</div>
      <div class="aed-meta">
        ID: ${r.aed_id}<br>
        ${r.aed_access
          ? "Access: " + r.aed_access
          : "Access: public"}
      </div>
    </div>`;
}

// ── Compare routes toggle ───────────────────────────────────────
document.getElementById("btn-compare")
  .addEventListener("click", () => {
  state.showAlternatives = !state.showAlternatives;
  const btn = document.getElementById("btn-compare");
  btn.classList.toggle("active", state.showAlternatives);
  btn.textContent = state.showAlternatives
    ? "Hide alternatives" : "Compare routes";

  const altDiv = document.getElementById(
    "result-alternatives");
  altDiv.style.display =
    state.showAlternatives ? "block" : "none";

  state.altLayers.forEach(l => l.remove());
  state.altLayers = [];

  if (state.showAlternatives) {
    DEMO_DATA.results.slice(1).forEach(r => {
      const latlngs = [];
      r.edges.forEach(edge => {
        (edge.coords || []).forEach(([lon, lat]) => {
          latlngs.push([lat, lon]);
        });
      });
      if (latlngs.length < 2) return;

      const border = L.polyline(latlngs, {
        color: "#1a6fcc", weight: 8, opacity: 0.5,
      }).addTo(map);
      const fill = L.polyline(latlngs, {
        color: "#6eaaec", weight: 5, opacity: 0.7,
      }).addTo(map);
      state.altLayers.push(border, fill);
    });
  }
});

// ── Init ───────────────────────────────────────────────────────
loadAEDs().catch(err => console.error("Failed to load AEDs:", err));
loadBoundary().catch(err => console.error("Failed to load boundary:", err));
loadIsochrones().catch(err => console.error("Failed to load isochrones:", err));
