# Decisiones — Remediación de auditoría AED Route Hamburg

Log append-only. No editar entradas existentes; añadir nuevas al final.
Formato: `## YYYY-MM-DD — <decisión> — motivo: ... — cierra: <hallazgo o N/A>`

---

## 2026-08-14 — El commit baseline usa el prefijo `chore:`, no `fase 0:` — motivo: es pre-fase por diseño — cierra: N/A (convención de proceso)

El commit baseline (`860b5d7`, rama `main`) se titula
`chore: baseline commit (pre-remediation) — ...` en vez de seguir el
formato `fase N: <qué cambia>` acordado para el resto del plan (ver
Regla Global 3, 2026-08-14). Es intencional: ese commit captura el estado
del proyecto ANTES de cualquier remediación y es el único punto de retorno
de todo el plan — no se enmienda por consistencia cosmética. La convención
`fase N: ...` arranca desde el primer commit hecho en la rama de
remediación (`remediation/audit-2026-08`), en adelante.

---

## 2026-08-14 — Respaldo externo de `data/interim/hamburg_graph.pkl` (y del resto del proyecto) confirmado en Google Drive — motivo: `data/` está gitignorado por diseño (364 MB de cachés) — cierra: punto 2 del cierre de Fase 0

`data/interim/hamburg_graph.pkl` (364 MB) y el resto del proyecto están
subidos a Google Drive; la subida y su verificación fueron hechas
manualmente por el propietario del proyecto, fuera de esta sesión — no se
ha intentado ni se intentará automatizar esa subida ni crear una copia
local secundaria desde aquí. Como `data/` queda fuera de control de
versiones (`.gitignore`, ver commit baseline `860b5d7`), este respaldo
externo es el único mecanismo de recuperación de esos artefactos si se
perdieran localmente. Integridad verificable localmente vía
`data/interim/hamburg_graph.pkl.sha256` (creado en la Fase 0), que sí está
versionado.

Además, en esta misma fecha se aplicó `chmod 444` a
`data/interim/hamburg_graph.pkl`: dado que el grafo es inmutable durante
las 8 fases del plan (Restricción Global 1), este permiso hace que esa
inmutabilidad la imponga el sistema de archivos y no solo la disciplina del
plan. Si alguna operación futura falla por permisos sobre ese archivo
específico, es la salvaguarda funcionando como se pretende — no se debe
revertir el `chmod` para sortearla sin decisión explícita.

---

## 2026-08-14 — Fase 1 (reverificación de auditoría): C1 se retracta por completo; C13 y C16 se reclasifican; C2 se precisa — cierra: C1, C13, C16, C2

Verificación independiente (subagentes de solo lectura + verificación propia
para C2) contra el código real, sin acceso a la auditoría original:

- **C1 estaba invertido.** `app/app.py:92` sirve `index_original.html` +
  `app_original.js` en `GET /`, y esa es la variante **viva**, conectada al
  backend (`apiUrl()`, `POST /api/route`, capas AED/boundary/isochrones vía
  `/api/*`). `index.html` + `app.js` (no servido en ninguna ruta, solo
  alcanzable navegando a `/static/index.html`) es el prototipo **muerto**:
  `DEMO_DATA` hardcodeado, fetches literales a `./data/hamburg_mitte_*`,
  scope Hamburg-Mitte. La app en producción funciona correctamente hoy; no
  hay rotura de capas. Severidad retractada de Crítico a Bajo/Nota (código
  huérfano, no funcionalidad rota).
- **C13 confirmado, no retirado.** De 21 filas de la tabla de clasificación
  de vías, 19 coinciden con los filtros reales; 2 no (`motorway_link` y
  `trunk_link`, columna Walk: la tabla decía `No`, el filtro real los
  incluye). Corregido en `docs/routing_methodology.md`.
- **C16 confirmado con más precisión, severidad bajada a Nota.** OSMnx 2.1.0
  instalado: `ox.add_edge_speeds`, `ox.add_edge_travel_times` y
  `ox.graph_to_gdfs` existen a nivel superior y son *el mismo objeto*
  (identidad verificada con `is`) que sus equivalentes en
  `ox.routing`/`ox.convert`. Cero riesgo de incompatibilidad hoy.
- **C2 precisado.** Verificado contra el pickle real y el código fuente de
  `networkx==3.6.1` instalado: la razón de que hoy se devuelvan rutas
  óptimas pese al bug de unidades de la heurística no es una vaga
  "degeneración a Dijkstra", sino dos hechos concretos combinados: (1) la
  heurística es casi constante (~5.970.071,6 ± 0,3) para cualquier nodo
  regular de Hamburgo, lo que preserva el orden Dijkstra-correcto entre
  ellos; (2) cada nodo AED tiene grado 1 (una sola arista de acceso), y
  `nx.astar_path` devuelve el camino en cuanto extrae el `target` de la
  cola (sin comprobar si queda algo más barato sin explorar) — con h=0
  exacto en el AED, esa única relajación se produce siempre a través del
  predecesor correcto. Un AED con grado >1 rompería esta garantía en
  silencio. Ver detalle completo en el mensaje de la Fase 1 (2026-08-14).

## 2026-08-14 — Fase 2: documentación sincronizada con el comportamiento real — cierra: C4, C5, C7 (parcial), C8, C13

- Flask → FastAPI corregido en `README_deploy.md`, `docs/routing_methodology.md`
  y `docs/network_and_graph_build.md` (incluyendo el log "Flask app ready."
  → "FastAPI app ready." y el comando inexistente `app/flask_app.py` →
  `app/app.py` vía uvicorn).
- Contradicción "crashea vs. reconstruye" resuelta en `README_deploy.md`
  con el comportamiento real verificado por archivo de caché: AEDs →
  crashea (`_require_cache`); grafo → reconstrucción automática vía OSMnx
  si falta (lenta, depende de red); isócronas → recálculo automático en
  arranque; boundary → solo falla al pedirse `/api/boundary` si falta
  (500 no controlado), no en el arranque.
- Puertos: no unificados todavía (pendiente de la Fase 3b); se dejó nota
  explícita de la inconsistencia (5000 vs. 5050) en los tres documentos
  afectados, sin inventar un valor canónico.
- Tabla de clasificación de vías corregida (`motorway_link`/`trunk_link`,
  columna Walk: No → Yes), con nota de que la prosa del documento ya era
  correcta — cierra C13.
- Cifras de AEDs corregidas en `docs/routing_methodology.md` a los valores
  verificados: 141 AEDs en la fuente, 139 integrados en el grafo (2
  omitidos por `MAX_SNAP_DISTANCE_M`), 139 de 139 con isócrona completa
  (no "138 de 139") — cierra C8.
- `README.md` no se borra ni se mueve (eso es decisión de Fase 4): se le
  añadió un aviso explícito de que describe el prototipo estático muerto
  (Hamburg-Mitte, sin backend), no la app desplegada.

## 2026-08-14 — Filtro de componente gigante documentado como deuda conocida, NO implementado — motivo: afirmación previa en la documentación no correspondía al código — cierra: C3 (parcial; ver Fase 7)

`docs/routing_methodology.md` ("AED snap restricted to giant component") y
`docs/network_and_graph_build.md` ("Giant component constraint") afirmaban
que el snapping de AEDs se restringe al componente débilmente conexo mayor
del grafo. Verificado que `add_aed_nodes_to_graph`
(`src/aed_route/graph_builder_osm.py`) no implementa ningún filtro de
conectividad — el `cKDTree` de snapping se construye sobre todos los nodos
de carretera sin excepción. Ambos documentos se corrigieron para reflejar
esto como una brecha conocida, no como una funcionalidad existente. La
Fase 7 implementará el filtro solo para el snapping de ORIGEN (sin tocar el
grafo); el lado AED queda como deuda técnica aceptada porque requeriría
reconstruir las aristas de acceso del grafo inmutable.

## 2026-08-14 — Modo `car`: reclasificado de observación incidental a hallazgo de severidad ALTA; implementación diferida a una FASE 8 nueva, después de la Fase 7 — cierra: hallazgo nuevo (sin número de auditoría original; candidato a registrarse formalmente como tal)

Detectado durante la Fase 1 (verificación de C2): la arista de acceso de
cada AED se crea siempre con `can_drive=False`
(`add_aed_nodes_to_graph`), por lo que el modo `car` no puede llegar a
NINGÚN AED, en NINGÚN origen — no es un caso puntual de zona sin acceso
rodado, es estructural y universal. Confirmado además por el smoke test de
la Fase 0 (`car → 0 resultados` para el origen probado).

Decisión: no se corrige ahora. Se traslada como decisión de producto a la
Fase 4, junto con el resto de decisiones de esa fase. Se preparó (en
conversación, 2026-08-14, sin tocar ningún archivo) un análisis comparativo
de tres opciones: (i) hacer drivable la arista de acceso AED, (ii) enrutar
el modo car al nodo de carretera más cercano al AED en vez de al nodo AED,
(iii) retirar el modo car de la interfaz hasta resolverlo. Para cada una se
detalló qué mecanismo exige (rebuild del grafo — prohibido; parche
explícito y documentado en memoria al arranque — admisible a evaluar; o
solo cambio de frontend) y su impacto en `routing_methodology.md` y en el
contrato de `/api/route`. La implementación de lo que se decida será una
**Fase 8 nueva**, posterior a la Fase 7 — no se adelanta trabajo de
implementación en esta fase.

Nota sobre la Restricción Global 1: se matizó explícitamente que un parche
de atributos de arista en memoria al arranque (no una regeneración del
pickle, no una modificación de `graph_builder_osm.py`) es una opción
admisible a evaluar para esta decisión — sigue prohibido regenerar el
pickle, tocar `graph_builder_osm.py` o reproyectar nodos del grafo cargado.

## 2026-08-14 — `bike_cost_s` de la arista de acceso AED usa `WALK_SPEED_M_S`: clasificado como pregunta abierta de metodología, NO como bug — cierra: N/A (pregunta abierta, ver `docs/routing_methodology.md`, sección "Open Questions and Pending Decisions")

`add_aed_nodes_to_graph` calcula `access_time_s = dist_m / WALK_SPEED_M_S` y
reutiliza ese mismo valor tanto para `walk_cost_s` como para `bike_cost_s`
de la arista de acceso AED — es decir, el último tramo hasta el AED se
computa siempre a velocidad de caminar, incluso para el modo bici.
Explícitamente NO se clasifica como error: puede modelar razonablemente que
un ciclista desmonta y cubre a pie los últimos metros hasta el AED. Se
añadió como pregunta abierta de metodología en
`docs/routing_methodology.md`, junto a las que ya arrastraba el proyecto
(acceso privado en contexto de emergencia, umbrales de isócrona sin validar
con literatura clínica), pendiente de confirmación explícita del equipo
sobre si es una decisión deliberada.
