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

---

## 2026-08-14 — Corrección al análisis del modo `car`: agujero compartido por (i)/(ii), cuarta opción (iv), medición que abre la Fase 4, y verificación de PUBLIC_BASE_PATH diferida — cierra: N/A (ampliación del análisis del hallazgo nuevo del modo car; no se implementa nada aquí)

**Agujero compartido por (i) y (ii), no visto en el análisis original:** el
nodo de snap de cada AED se eligió sobre TODOS los nodos de carretera, sin
filtro de modo — `add_aed_nodes_to_graph` construye el `cKDTree` sobre
`nodes_df[road_mask]` completo, sin distinguir `can_drive`. Como
`can_drive` cubre solo el 43,9% de las aristas del grafo unificado, el
`nearest_node` de un AED puede no tener ninguna arista drivable. Si eso
ocurre:
- **(i)** (hacer drivable la arista de acceso) no arregla nada: el
  `nearest_node` sigue siendo inalcanzable en el subgrafo de coche; la
  arista de acceso ahora drivable no sirve si no se puede llegar hasta el
  otro extremo.
- **(ii)** (enrutar al nodo de carretera más cercano al AED) falla igual:
  el objetivo pasaría a ser exactamente ese mismo nodo inalcanzable.

Ninguna de las dos opciones originales ataca esta causa; ambas asumían
implícitamente que el `nearest_node` ya está en el componente drivable.

**Opción (iv) — snap dependiente del modo (nueva, al mismo nivel de detalle
que las otras tres):**
Para el modo `car` específicamente, mapear cada AED al nodo de carretera
más cercano **que tenga aristas `can_drive`**, usando un `cKDTree`
construido en memoria al arranque solo sobre el subconjunto de nodos con
al menos una arista drivable — no sobre todos los nodos de carretera como
hace hoy `add_aed_nodes_to_graph`. Ataca la causa real (snap sin filtro de
modo), no el síntoma. No requiere rebuild del grafo ni tocar
`graph_builder_osm.py` — es un índice espacial adicional en memoria al
arranque, igual que `build_node_index`/`build_aed_index` ya existentes,
pero restringido a nodos drivables. Coste: la distancia de acceso en coche
para cada AED superará previsiblemente los ~17 m medios actuales
(calculados sin ese filtro), y hay que decidir cómo se refleja ese tramo
adicional en `total_cost_s` y en lo que se dibuja en el mapa.

**Medición que abre la Fase 4 (solo lectura, NO ejecutada ahora):** de los
139 nodos AED del grafo, ¿cuántos tienen su `nearest_node` (el mismo que ya
usa `add_aed_nodes_to_graph`) alcanzable en el subgrafo `can_drive=True`?
Si son pocos, (i) es viable con excepción documentada caso por caso; si son
muchos, solo (iv) o (iii) tienen sentido real. Este conteo será el primer
paso de la Fase 4, antes de decidir entre las cuatro opciones.

**Nueva pregunta abierta condicional:** si se elige (i), la velocidad
asumida para la arista de acceso en coche sería una constante nueva sin
respaldo bibliográfico (no es velocidad de conducción normal, es una
maniobra de acceso/aparcamiento) — va a la lista de preguntas abiertas de
`docs/routing_methodology.md` si y cuando se elija esa opción; no se
inventa un valor ahora.

**`PUBLIC_BASE_PATH` — verificación diferida a la Fase 4 (solo lectura):**
que esta variable no exista en el código (confirmado en la Fase 2) implica
que el escenario de proxy que NO elimina el prefijo público podría no estar
soportado por el backend. Pendiente de verificar en la Fase 4, sin tocar
código: (1) si `static/app_original.js` tolera ese escenario por su cuenta,
vía el cálculo de `APP_BASE` desde `window.location.pathname`; (2) si los
endpoints `/api/*` responderían correctamente bajo ese prefijo tal como
está montado hoy en `app/app.py`. Según el resultado, `README_deploy.md`
tendrá que documentar ese escenario como inviable, o como uno que funciona
hoy por un efecto colateral del frontend y no por diseño explícito del
backend — ninguna de las dos cosas está determinada todavía.

---

## 2026-08-14 — Fase 3(a): `POST /api/route` ya no bloquea el event loop — cierra: C10

`find_nearest_aeds` (síncrona, corre A* hasta `SHORTLIST_EUCLIDEAN_K` veces
sobre un grafo de ~658k nodos) se llamaba directamente dentro del handler
`async def route(...)` de `app/app.py`, bloqueando el único hilo del event
loop de uvicorn durante toda la búsqueda — cualquier petición concurrente
(incluido `/healthz`) quedaba en cola detrás. Corregido envolviendo la
llamada en `await asyncio.to_thread(find_nearest_aeds, ...)`. No hay suite
automatizada todavía para verificar esto con un test de concurrencia real
(el arnés llega en la Fase 5); verificado manualmente con el smoke test
(arranque + rutas en los tres modos) — ver registro en `docs/smoke_test.md`.

---

## 2026-08-14 — Fase 3(c): dependencias sin uso confirmado retiradas de `requirements.txt`; archivo huérfano eliminado — cierra: C15, C17

Reconfirmado por grep (sin uso directo en `app/` ni `src/`) antes de tocar
nada: `python-multipart` (solo necesario en FastAPI para `Form`/`UploadFile`,
ninguno usado aquí) y `pyarrow` (sin ningún `import pyarrow` ni uso de
motor Arrow explícito en el código). Ambos retirados de `requirements.txt`.
`geopandas` SÍ se mantiene, pese a no importarse directamente en el código
propio: es dependencia transitiva real de `osmnx` (usada indirectamente vía
`ox.graph_to_gdfs` en `isochrones.py`), declararla explícitamente es
razonable.

`static/data/demo_rathaus_response.json` eliminado — huérfano, sin ninguna
referencia en el JS/HTML del repo (reconfirmado por grep antes de borrar).

**Limitación de esta verificación, dicha explícitamente:** el `.venv` de
este entorno ya tenía `python-multipart`/`pyarrow` instalados antes de este
cambio; retirarlos de `requirements.txt` no los desinstala del venv
actual, así que el smoke test de este commit no prueba de verdad que el
proyecto siga instalando y arrancando correctamente con un `pip install -r
requirements.txt` limpio y sin ellos — solo prueba que el código sigue
funcionando con el venv ya existente. No se ha creado un venv nuevo para
verificar esto de forma más rigurosa en esta pasada.
