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

// ── Textos de interfaz — BORRADOR, pendiente de aprobación del equipo ──
// (ver docs/decisions.md, Fase 8A(1), 2026-08-14). Cambiar SOLO estas
// cadenas aquí no requiere tocar ninguna lógica de renderPanel(),
// showNoResults() ni el resto del archivo — ese es el propósito de
// aislarlas en este objeto.
const UI_COPY = {
  // {mode} se sustituye por "walk"/"bike" en tiempo de ejecución (car está
  // deshabilitado, así que este mensaje nunca se dispara para ese modo).
  // NOTA para quien apruebe el texto (señalado en la revisión de código de
  // este mismo ítem, 2026-08-14): con car deshabilitado, si falla walk,
  // el mensaje sugiere "Try Walk" — el mismo modo que acaba de fallar.
  // Revisar antes de aprobar definitivamente.
  noResults:
    "No AED could be reached from here by {mode}. Try Walk or Bike, " +
    "or call emergency services if this is urgent.",
  carDisabledNote: "Car routing temporarily unavailable",
  // Distinto de noResults a propósito: esto es un fallo de la petición en
  // sí (red caída, error del backend), no "no hay AED alcanzable" — no
  // hacer una afirmación específica y potencialmente falsa sobre rutas
  // cuando en realidad no se sabe si existe una.
  requestError: "Something went wrong contacting the server. Please try again.",
};

const APP_BASE = (() => {
  const path = window.location.pathname.replace(/\/index\.html$/, "");
  const staticIndex = path.indexOf("/static");
  if (staticIndex >= 0) return path.slice(0, staticIndex).replace(/\/$/, "");
  return path.replace(/\/$/, "");
})();

const API_BASE = (window.AED_ROUTE_API_BASE || `${APP_BASE}/api`).replace(/\/$/, "");
const apiUrl = (path) => `${API_BASE}/${path.replace(/^\/+/, "")}`;

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
  const res = await fetch(apiUrl("aeds"));
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
    // Corregido en la revisión de código de la Fase 8A(1): el botón Car
    // usa aria-disabled (no el atributo nativo disabled) para que lectores
    // de pantalla en modo de lectura lineal SÍ lo encuentren y anuncien
    // como "no disponible" en vez de que desaparezca sin más — pero
    // aria-disabled, a diferencia de disabled, NO bloquea el evento click
    // por sí solo, así que hay que comprobarlo aquí explícitamente.
    if (btn.getAttribute("aria-disabled") === "true") return;
    document.querySelectorAll(".mode-btn").forEach(
      (b) => b.classList.remove("active")
    );
    btn.classList.add("active");
    state.mode = btn.dataset.mode;
  });
});

// Car deshabilitado (ver docs/decisions.md, Fase 8A(1)): sin cobertura
// real hoy (ver Fase 4/decisions.md sobre el modo car). Se usa
// aria-disabled + tabindex="-1" en vez del atributo nativo `disabled`
// (corregido en la revisión de código de este ítem): un botón
// nativamente disabled se saca por completo del árbol de accesibilidad en
// varias combinaciones navegador/lector de pantalla, así que un usuario
// navegando en modo de lectura lineal nunca se enteraría de que Car
// existe ni de por qué falta. Con aria-disabled sigue apareciendo y
// anunciándose como no disponible; tabindex="-1" lo saca de la navegación
// por Tab (igual que un botón realmente disabled, consistente con que un
// usuario de ratón tampoco puede activarlo). El guard de más arriba en el
// handler de click es lo que de verdad impide activarlo.
{
  const carBtn = document.getElementById("btn-mode-car");
  if (carBtn) {
    carBtn.title = UI_COPY.carDisabledNote;
    carBtn.setAttribute("aria-label", `Car — ${UI_COPY.carDisabledNote}`);
  }
  const carNote = document.getElementById("car-disabled-note");
  if (carNote) carNote.textContent = UI_COPY.carDisabledNote;
}

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

  // Capturado en el momento del envío, no leído de nuevo cuando llegue la
  // respuesta — corregido en la revisión de código de la Fase 8A(1): si
  // el usuario cambia de modo mientras la petición está en vuelo,
  // state.mode ya no describe la petición que realmente se hizo.
  const requestMode = state.mode;

  try {
    const res = await fetch(apiUrl("route"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat, lon: lng, mode: requestMode }),
    });

    // Corregido en la revisión de código de la Fase 8A(1): antes no se
    // comprobaba res.ok, así que un error real del backend (400 modo
    // inválido, 500, etc.) se interpretaba igual que "sin resultados" —
    // una afirmación específica y potencialmente falsa sobre rutas,
    // cuando en realidad no se sabe si existe una.
    if (!res.ok) {
      console.error("Routing error: HTTP", res.status);
      showRequestError();
      return;
    }

    const data = await res.json();
    if (!Array.isArray(data.results)) {
      console.error("Routing error: unexpected response shape", data);
      showRequestError();
      return;
    }

    state.results = data.results;
    state.lastRequestMode = requestMode;
    renderPanel();
    drawRoutes();
  } catch (err) {
    console.error("Routing error details:", err);
    showRequestError();
  }
});

// ── Render panel ───────────────────────────────────────────────
function renderPanel() {
  // Antes de la Fase 8A esto llamaba a showHint(), reutilizando el mismo
  // texto genérico de "haz click en el mapa" que se ve ANTES de cualquier
  // click — un usuario no podía distinguir "no has hecho click todavía"
  // de "hiciste click y no hay ruta" (ver docs/decisions.md, Fase 8A(1)).
  // Cubre por igual los tres casos legítimos de "sin resultados" que
  // llegan idénticos desde el backend (results: [] en los tres): un
  // click sobre agua, un click a más de MAX_SNAP_DISTANCE_M de cualquier
  // nodo, y un origen fuera del componente gigante (Fase 7) — el backend
  // no distingue el motivo en la respuesta, así que el frontend tampoco
  // necesita hacerlo aquí.
  if (!state.results.length) { showNoResults(state.lastRequestMode); return; }

  hideAllPanels();
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
  state.altLayers.forEach((l) => l.remove());
  state.altLayers = [];

  if (!state.showAlternatives || state.results.length < 2) return;

  state.results.slice(1).forEach((r) => {
    // Build full coord array for this alternative route
    const latlngs = [];
    r.edges.forEach((edge) => {
      if (!edge.coords || edge.coords.length < 2) return;
      edge.coords.filter(isValidCoord).forEach(([lon, lat]) => {
        latlngs.push([lat, lon]);
      });
    });

    if (latlngs.length < 2) return;

    // Google Maps style: thick dark border + thinner light fill on top
    const border = L.polyline(latlngs, {
      color: "#1a6fcc",
      weight: 8,
      opacity: 0.5,
    }).addTo(map);

    const fill = L.polyline(latlngs, {
      color: "#6eaaec",
      weight: 5,
      opacity: 0.7,
    }).addTo(map);

    state.altLayers.push(border, fill);
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
// Los cinco paneles de la barra lateral (hint / loading / no-results /
// request-error / results) son mutuamente excluyentes. Centralizado aquí
// tras la revisión de código de la Fase 8A(1): antes cada función
// show*() repetía su propia lista de "ocultar los demás", lo que ya
// había hecho fácil olvidarse de uno al añadir un panel nuevo (exactamente
// lo que pasó al añadir request-error) — con un único punto de reseteo,
// añadir un sexto panel en el futuro no puede volver a producir ese
// mismo error de omisión.
function hideAllPanels() {
  document.getElementById("hint").style.display = "none";
  document.getElementById("loading").style.display = "none";
  document.getElementById("no-results").style.display = "none";
  document.getElementById("request-error").style.display = "none";
  document.getElementById("results").style.display = "none";
}

function showLoading() {
  hideAllPanels();
  document.getElementById("loading").style.display = "block";
}

// No hay una función showHint() propia: el estado "antes de cualquier
// click" es simplemente el HTML de partida de #hint, visible por defecto
// (sin display:none ni inline ni por CSS) hasta el primer click. Antes de
// la revisión de código de la Fase 8A(1) sí existía una showHint(),
// reutilizada también para errores de red y para "sin resultados" — al
// separar esos dos casos en showRequestError()/showNoResults(), la
// función dejó de tener ninguna llamada real y se retiró en vez de
// dejarla como código muerto.

// Fase 8A(1), 2026-08-14: distinta de showHint() a propósito -- esta se
// usa SOLO cuando hubo un click y el backend respondió con results: []
// (agua / fuera de MAX_SNAP_DISTANCE_M / fuera del componente gigante,
// ver renderPanel()), no antes de cualquier click. Texto en UI_COPY,
// borrador pendiente de aprobación del equipo.
//
// `mode` se recibe como parámetro (el modo con el que se hizo la petición
// que de verdad falló, capturado en el map.on("click") — corregido en la
// revisión de código de este ítem) en vez de leer state.mode aquí dentro,
// que podría haber cambiado ya si el usuario cambió de modo mientras la
// petición seguía en vuelo.
function showNoResults(mode) {
  hideAllPanels();
  const el = document.getElementById("no-results");
  el.textContent = UI_COPY.noResults.replace("{mode}", mode);
  el.style.display = "block";
}

// Fase 8A(1), 2026-08-14 (añadida en la revisión de código de este mismo
// ítem): distinta tanto de showHint() como de showNoResults() a propósito
// -- esto es un fallo de la petición en sí (red caída, error HTTP del
// backend, forma de respuesta inesperada), no "no hay AED alcanzable
// desde aquí". No reusar showNoResults() aquí: haría una afirmación
// específica y potencialmente falsa sobre rutas cuando en realidad no se
// sabe si existe una.
function showRequestError() {
  hideAllPanels();
  const el = document.getElementById("request-error");
  el.textContent = UI_COPY.requestError;
  el.style.display = "block";
}

// ── Load and draw Hamburg boundary ────────────────────────────
async function loadBoundary() {
  const res = await fetch(apiUrl("boundary"));
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
  const res = await fetch(apiUrl("isochrones") + "?v=" + Date.now());
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
