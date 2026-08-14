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

---

## 2026-08-14 — Fase 3(b): puerto canónico unificado a 5000 — cierra: C7 (con riesgo de despliegue pendiente de verificar, ver más abajo)

Unificado a **5000** en `app/app.py` (era 5050 en su bloque `__main__`),
`README_deploy.md`, `docs/routing_methodology.md` y
`docs/network_and_graph_build.md`. `app/wsgi.py`, `Dockerfile`,
`docker-compose.yml` y `docs/apache.conf` ya usaban 5000, sin cambios.

**El valor se eligió por consistencia entre los artefactos de este
repositorio (4 de 5 ya usaban 5000; el 5050 vivía en un bloque `__main__`
que ningún camino de arranque documentado ejecuta) — NO se ha verificado
contra la configuración real del proxy inverso desplegado en el servidor
de HCU.** `docs/apache.conf` es un snippet guardado en este repo, no una
prueba de lo que está efectivamente configurado en producción hoy.

**Riesgo explícito, sin mitigar todavía:** si el Apache real de producción
apunta a 5050 (el valor que `app/app.py` usaba hasta este commit), este
cambio dejaría el servicio inaccesible en el próximo despliegue hasta que
alguien actualice esa configuración de Apache para que coincida. Verificar
la configuración real del proxy inverso ANTES del próximo despliegue queda
como acción pendiente explícita — no se puede cerrar como "hecho" solo con
este commit.

---

## 2026-08-14 — Fase 4(a): `SHORTLIST_EUCLIDEAN_K` = 5, aprobado — implementación diferida a la Fase 8 — cierra: C6

Aprobado subir `SHORTLIST_EUCLIDEAN_K` de 3 (código actual) a 5 (valor ya
justificado en `docs/routing_methodology.md`, sección "Why K=5"). **No se
implementa en esta fase.** Cuando se implemente en la Fase 8: cambiar
`config.py`, y corregir en la documentación la afirmación de "Compare
routes toggle showing up to 4 alternative routes" — con K=5, el máximo de
4 alternativas solo se alcanza si las 5 búsquedas A* tienen éxito (ninguna
descartada por `NetworkXNoPath` o snap fallido); no asumir "hasta 4" como
un techo garantizado sin verificarlo contra el comportamiento real de
`find_nearest_aeds` en ese momento.

## 2026-08-14 — Fase 4(b): retirar `index.html`/`app.js` y reemplazar `README.md`, aprobado — implementación diferida a un commit propio en la Fase 8 — cierra: C1 (código huérfano), C9

Aprobado retirar `static/index.html`, `static/app.js`, `static/styles.css`
y los tres `static/data/hamburg_mitte_*.geojson` (el conjunto huérfano
completo), y reemplazar el contenido de `README.md` por un aviso corto que
remita a `README_deploy.md`. **No se ejecuta en esta fase, ni junto a
ningún otro cambio — va en su propio commit dedicado en la Fase 8.**
Precondición explícita antes de borrar en la Fase 8: verificar por grep en
todo el árbol (incluido `scratch/`) que `styles.css` y los tres
`hamburg_mitte_*.geojson` no los referencia nada más — esa verificación
tampoco se hace en esta fase, es el primer paso de ese commit futuro, no
un prerequisito ya cumplido.

Pendiente, explícitamente del usuario y no de este agente: confirmar con
su equipo si alguien tiene enlazada la URL `/static/index.html` desde
fuera de este repositorio antes de borrar los archivos.

## 2026-08-14 — Fase 4(c): mitigación del fallo silencioso en resultados vacíos, aprobada — pasa a ser el PRIMER ítem de la Fase 8 — cierra: hallazgo nuevo de UX (registrado 2026-08-14, ver entrada de smoke test)

Aprobadas ambas partes, a implementar juntas en la Fase 8 como primer paso
(antes que cualquier otro cambio de esa fase):
1. Mensaje explícito en `renderPanel()` (`static/app_original.js:132-133`)
   cuando `state.results.length === 0`, en vez de reutilizar el hint
   genérico pre-click. Cubre Car, clicks sobre agua, y clicks fuera de
   `MAX_SNAP_DISTANCE_M` con el mismo mensaje.
2. Botón "Car" deshabilitado visualmente con una nota, hasta que exista una
   solución real (Fase 8 más allá de este primer paso, o posterior).

**Texto de cara al usuario — BORRADOR, pendiente de revisión del equipo
antes de publicarse, NO aprobado para producción todavía:**

> "No AED could be reached from here by [mode]. Try Walk or Bike, or call
> emergency services if this is urgent."

(para el botón Car deshabilitado, nota corta junto al botón, también
borrador:)

> "Car routing temporarily unavailable"

Ninguno de los dos textos está aprobado — se preparan aquí solo para que
el equipo tenga algo concreto sobre lo que opinar, no para implementarse
tal cual.

## 2026-08-14 — Fase 4(d): modo `car` — recomendación (iv) aceptada como DIRECCIÓN, decisión NO cerrada, pendiente de consulta con el equipo del usuario

**Verificación previa solicitada por el usuario, resuelta:** el conteo de
314.640 componentes en el subgrafo `car` es, tal como sospechaba el
usuario, un artefacto de `subgraph_view` + `connected_components`:
313.945 de esas 314.640 componentes (99,8%) son nodos aislados de tamaño 1
(nodos sin ninguna arista `can_drive`, que `subgraph_view` conserva como
nodos del grafo aunque pierdan todas sus aristas). Solo 695 componentes
tienen 2 o más nodos. **La métrica principal (nearest_node de AED dentro
del componente gigante) se recalculó contando solo componentes de 2+
nodos y el resultado se mantiene exactamente igual: 58/139 = 41,7%** — no
era un artefacto, es un dato real. Desglose completo de los 139
`nearest_node` de AED: 58 (41,7%) en el componente gigante; 3 (2,2%) en
otro fragmento drivable pequeño y aislado; 78 (56,1%) sin ninguna arista
`can_drive` en absoluto (nodos puramente peatonales/ciclistas).

**Medición pedida — nodo drivable dentro de `MAX_SNAP_DISTANCE_M` (100 m),
con snap dependiente del modo (opción iv), CRS reproyectado correctamente
a metros (no reutilizando el bug de unidades de C2):**

| Universo de snap para `car` | AEDs con nodo drivable ≤100 m | Distancia resultante (de los que sí tienen) |
|---|---|---|
| Restringido al componente gigante `car` (el que de verdad importa para (iv)) | **136 / 139 (97,8%)** | media 29,4 m, máxima 94,8 m, mínima 2,6 m |
| Cualquier nodo con arista `can_drive` (incluye fragmentos aislados pequeños, no recomendado como base real de (iv)) | 138 / 139 (99,3%) | media 29,7 m, máxima 95,3 m, mínima 2,6 m |

Referencia: snap peatonal actual, media ~17,3 m, máxima 60,0 m.

**Esto cambia sustancialmente el diagnóstico frente al 41,7% inicial**: el
41,7% mide si el `nearest_node` YA elegido (sin filtro de modo, snap
peatonal) coincide por casualidad con la red drivable — un número bajo
porque nunca se buscó allí. Si en cambio se hace un snap propio para
`car`, restringido al componente gigante drivable (que es exactamente lo
que propone la opción iv), la cobertura sube a **97,8%** (136 de 139
AEDs), con distancias de acceso razonables (media 29,4 m, siempre por
debajo de `MAX_SNAP_DISTANCE_M`). Solo 3 AEDs quedarían sin ningún nodo
drivable dentro de 100 m incluso con este enfoque — candidatos a una
excepción documentada individual o a un radio de snap mayor solo para
`car`, a decidir en la Fase 8.

**Decisión NO cerrada.** La opción (iv) queda aceptada como dirección de
diseño, pero su implementación y el compromiso de producto que implica
(cobertura del 97,8%, no del 100%) se consultan con el equipo del usuario
antes de proceder. La medición de esta entrada es la que se necesitaba
para que esa conversación sea informada.

## 2026-08-14 — Diagnóstico `PUBLIC_BASE_PATH` confirmado como escenario NO soportado en absoluto — corrección de `README_deploy.md` diferida a la Fase 8 — riesgo de despliegue explícito

Confirmado (ver mensaje de la Fase 4, Paso 2): `app/app.py` instancia
`FastAPI()` sin `root_path`, sin middleware, sin lectura de cabeceras
`X-Forwarded-*`; todas las rutas están registradas en su path exacto. Si
el proxy inverso real reenvía la petición SIN eliminar el prefijo público
(el modo "PUBLIC_BASE_PATH" que describe `README_deploy.md`), el backend
recibe la ruta con el prefijo intacto y devuelve 404 en TODAS las rutas,
incluida la página raíz — no es un caso de "funciona por accidente del
frontend", **no funciona en absoluto, ni siquiera se llega a servir el
HTML**. La corrección de `README_deploy.md` para documentar esto
correctamente (marcar el escenario como no soportado) queda diferida a la
Fase 8.

**Riesgo de despliegue explícito, junto con el del puerto (ver entrada de
Fase 3b):** antes del próximo despliegue real en el servidor de HCU hay
que verificar DOS cosas contra la configuración real de Apache — (1) que
efectivamente escucha/reenvía al puerto 5000 y no 5050, y (2) que el modo
de proxy configurado SÍ elimina el prefijo público antes de reenviar (no
el modo "PUBLIC_BASE_PATH"). Si cualquiera de las dos no se cumple, la
aplicación no arrancará o no será accesible tras este trabajo de
remediación.

---

## 2026-08-14 — Matiz sobre el 97,8% de cobertura del modo car (opción iv) — precisión de interpretación, no cambia el dato

El 97,8% (136/139 AEDs con un nodo drivable alcanzable a ≤100 m, dentro
del componente gigante car) es una **métrica de cobertura de snap**: mide
si existe un punto de entrada a la red drivable cerca de cada AED. **No es
una garantía de que A* encuentre ruta desde un origen arbitrario** — un
origen concreto podría estar, a su vez, fuera del componente gigante
drivable, o más allá de `MAX_SNAP_DISTANCE_M` de cualquier nodo drivable,
independientemente de que el AED de destino tenga buena cobertura. Es la
métrica correcta para decidir si la opción (iv) merece implementarse, pero
no debe leerse ni comunicarse como "97,8% de consultas con éxito" — son
dos cosas distintas. Anotado explícitamente para que no se malinterprete
al llevarlo a discusión de equipo.

---

## 2026-08-14 — Fase 5: arnés de regresión creado — cierra: preparación de C2 (Fase 6) y C3 (Fase 7)

**Dependencia de test:** `pytest>=8.0,<9.0` (rango acotado, no abierto —
instalado 8.4.2) en `requirements-dev.txt`, archivo nuevo y separado de
`requirements.txt` — no se instala en producción.

**Golden files** (`tests/golden/*.json`, generados con
`scripts/generate_golden_routes.py`, commit `adf2f53`, registrado en
`tests/golden/MANIFEST.json`): 9 orígenes × 3 modos, JSON con claves
ordenadas e indentado para diffs legibles. Cada caso lleva grabada su
propia `expectation_fase7` (`no_change` / `expected_change` /
`expected_improvement`) con el motivo — la predicción se escribió ANTES de
tocar el snapping de origen en la Fase 7, no se interpretará a posteriori:

- `dense_urban`, `boundary_edge`: funcionan hoy (walk/bike con resultado,
  car=0 estructural) — `no_change` esperado.
- `clausewitz_kaserne`: sin ningún nodo a ≤100 m del punto documentado en
  `routing_methodology.md` — nodo del componente gigante más cercano a
  164,8 m, sigue fuera de rango tras la Fase 7 — `no_change`.
- `water_point` (53.5080, 9.9350): verificado MIDIENDO, no asumido —
  3 de 4 candidatos en el Elba snapearon a infraestructura real (muelles/
  ferris); este quedó confirmado a 236,4 m del nodo más cercano —
  `no_change`.
- `isolated_stays_empty_a`/`b`: snapean hoy a un nodo fuera del componente
  gigante general; su nodo gigante real más cercano está a 186,4 m / 342,3
  m — fuera de `MAX_SNAP_DISTANCE_M` incluso tras el filtro de la Fase 7 —
  `no_change` (aislamiento genuino, no solo snap mal filtrado).
- `isolated_flip_c`/`d`: mismo mecanismo, pero su nodo gigante real está a
  6,4 m / 43,9 m — dentro de rango — `expected_change`. Si estos dos NO
  cambian tras la Fase 7, el filtro de componente gigante no está
  funcionando.
- `isolated_partial_e`: único caso con resultado parcial hoy (walk=1,
  bike=0, car=0) por conectividad interna de su propia componente aislada;
  nodo gigante a 14,2 m — `expected_improvement`. El golden guarda la
  respuesta COMPLETA (no solo el conteo) para que la Fase 7 pueda comparar
  si mejora la calidad de la ruta, no solo la cantidad.

**Determinismo verificado en dos niveles** (no solo dentro del mismo
proceso, que hubiera sido insuficiente): (1) doble generación completa
contra el mismo servidor en ejecución — idéntico byte a byte; (2)
generación repetida tras **reiniciar** el servidor (proceso nuevo) para
`dense_urban` e `isolated_partial_e` — idéntico byte a byte también. Un
orden de iteración dependiente del proceso se habría detectado en esta
segunda comprobación, no en la primera.

**Test de admisibilidad** (`tests/test_heuristic_admissibility.py`):
`routing.py` define su heurística como closure interna de
`find_nearest_aeds`, no importable sin tocar el archivo (prohibido en esta
fase) — el test replica la fórmula actual explícitamente, documentando que
es una copia y que debe sincronizarse cuando la Fase 6 toque el original.
Dos casos:
- Destino de grado 1 (topología real de un AED): **FALLA hoy, como se
  esperaba** — `h=141.42 > coste_real=117.65` en el nodo de origen del
  mini-grafo sintético, viola `h(n) <= h*(n)` por el problema
  metros-vs-segundos (aislado deliberadamente del bug de CRS ya conocido
  como C2, que es un problema distinto).
- Destino de grado 2 (topología hipotética, no la actual): **PASA hoy**
  — demuestra de forma concreta y reproducible (no solo teórica) que
  `nx.astar_path` devolvería una ruta subóptima (coste 1050 vs. óptimo
  real 1010) si un AED tuviera alguna vez más de un nodo de acceso. Sirve
  de guardarraíl de regresión para cualquier futura implementación de la
  opción (iv) del modo car.

Ningún archivo de `src/aed_route/` ni `app/app.py` se tocó en esta fase
(verificado por `git status` antes de commitear) — solo `tests/`,
`scripts/`, `pytest.ini`, `requirements-dev.txt` y `.gitignore`
(añadido `.pytest_cache/`).

---

## 2026-08-14 — Fase 6: heurística de A* corregida en `src/aed_route/routing.py` — cierra: C2

**Paso 1 obligatorio, verificación de la premisa CRS contra `nodes_df` real
(no contra `G.nodes[...]`, que es donde vive el bug):** primera pasada con
el rango esperado original (x≈5.4e5–6.0e5, y≈5.90e6–5.98e6) marcó
"premisa falsa" para los nodos de carretera (mínimo real x=463.423). **Esto
NO era el bug de CRS reapareciendo** — investigado antes de parar: ese
nodo (x mínimo) corresponde a lon=8.4425, lat=53.9621, es decir, el exclave
de Neuwerk (descubierto en la Fase 5 al inspeccionar `hamburg_boundary.
geojson`, que tiene 3 partes: la Hamburgo continental y dos exclaves). Mi
rango esperado original era simplemente demasiado estrecho — no conocía
Neuwerk al escribirlo. Verificación de fondo, la que de verdad importa:
cero filas con valores en escala de grados (<1000); el 100% de 657.870
nodos de carretera y 139 nodos AED caen dentro de un rango de metros
plausible para EPSG:25832 en el norte de Europa (x: 1e5–9e5, y:
5.0e6–6.5e6). **Premisa confirmada** — `nodes_df` proyecta a todos los
nodos de forma consistente a metros; el bug real está solo en que
`routing.py` leía `G.nodes[...]` en vez de `nodes_df`.

**Velocidades máximas medidas contra el grafo real** (no inventadas, tal
como se pidió):
- Walk: constante exacta, 1.7 m/s en el 100% de 1.390.991 aristas
  `can_walk=True` (min=max=1.7 — coincide exactamente con
  `WALK_SPEED_M_S`).
- Bike: máximo real 4.5 m/s (coincide con `BIKE_SPEED_M_S`); mínimo 1.7
  m/s en un subconjunto — corresponde a las aristas de acceso a AED, que
  ya están registradas como pregunta abierta de metodología, no un
  hallazgo nuevo.
- Car: **sin constante única** — varía de 2,778 m/s (10 km/h) a 33,333 m/s
  (120 km/h) sobre 645.996 aristas `can_drive=True`; el máximo se repite en
  muchas aristas (categoría real de vía, no un valor atípico de datos).

**El fix:** `heuristic(u, v)` ahora lee `(x, y)` de un diccionario
`node_key -> (x, y)` construido una sola vez desde `nodes_df` (cacheado a
nivel de módulo), nunca de `G.nodes[...]`. Devuelve `distancia_m /
velocidad_máxima_del_modo` — se divide por la velocidad MÁXIMA, no la
media, porque dividir por la media sobreestimaría el coste de cualquier
arista más rápida que la media y volvería a romper la admisibilidad (la
media ya no es una cota inferior válida). Para `car`, la velocidad máxima
se mide directamente del grafo cargado (`_car_max_speed_m_s`) y se cachea,
para no recorrer ~646.000 aristas en cada petición. Ningún archivo aparte
de `routing.py` se tocó — la Restricción Global 1 (grafo inmutable, sin
reproyectar nodos) se respetó en todo momento.

**Verificación:**
- Test de admisibilidad: **verde** en ambos casos. El de grado 1
  (`test_fixed_heuristic_is_admissible_for_degree1_destination`) pasa
  ahora que se cumple h(n) <= h*(n). El de grado 2 se actualizó (ver commit
  separado en `tests/`) para exigir el óptimo real (1010) en vez de
  documentar el valor subóptimo anterior (1050) — verificado empíricamente
  ANTES de aplicar el fix que, con la heurística corregida, el mismo
  escenario sintético pasa de devolver 1050 a devolver 1010.
- Golden files: **sin cambios** en ninguno de los 9 casos (solo cambió el
  hash de commit dentro de `MANIFEST.json` al regenerar, revertido para no
  ensuciar el diff — no forma parte del oráculo de comparación). Esperado
  exactamente por el grado 1 de los nodos AED, documentado arriba.
- Nodos explorados por A* (instrumentado temporalmente parcheando
  `heappop` en el módulo de networkx, sin tocar ningún archivo
  permanente), antes vs. después del fix, mismo origen y modo:
  - `dense_urban` (walk): 2.560 → 255 (-90%)
  - `dense_urban` (bike): 2.722 → 485 (-82%)
  - `boundary_edge` (walk): 43.229 → 9.008 (-79%)

  Reducción visible confirmada en los tres casos — la heurística ahora sí
  guía la búsqueda; antes, por el motivo explicado arriba (heurística
  casi-constante para nodos regulares), se comportaba efectivamente como
  Dijkstra en cuanto a nodos explorados, pese a pagar el coste de
  calcularla.
- `docs/routing_methodology.md` actualizado (sección "Why A* and not
  Dijkstra") con la corrección completa: qué estaba mal, por qué no
  producía rutas incorrectas hasta ahora (grado 1 de los AEDs), qué
  rompería esa garantía en silencio (un AED con más de un nodo de acceso —
  ver la opción (iv) del modo car), y las cifras de esta entrada.
- `requesting-code-review` pendiente de ejecutarse sobre el diff antes de
  cerrar la fase (obligatoria para Fases 6 y 7, acordado previamente).

---

## 2026-08-14 — Fase 6: revisión de código obligatoria — 4 hallazgos "Important" verificados y corregidos

Revisor independiente (subagente `general-purpose`, plantilla
`requesting-code-review`) sobre el diff `cbf4bd5..08842a7`. El revisor
cargó el pickle real de producción y verificó de forma independiente cada
cifra empírica del código/documentación (rangos de coordenadas, velocidades
por modo, grado de los AEDs, golden files) — todas se confirmaron
correctas. Hallazgos "Important", cada uno reverificado por mí antes de
actuar (no aplicados a ciegas):

1. **Admisibilidad no estrictamente cierta — CONFIRMADO independientemente
   y corregido.** El revisor encontró violaciones reales de h(n) <= h*(n)
   (125/74.816 pares en walk, 128/515.370 en bike) por una causa concreta:
   la distancia en línea recta calculada en coordenadas proyectadas
   EPSG:25832 puede superar el `length_m` que OSMnx calculó para esa misma
   arista (geodésico sobre WGS84) por la distorsión de escala de la
   proyección UTM. Reverificado por mí de forma independiente: 20.000
   aristas de muestra (100% con distancia proyectada > length_m, media
   0,177%, máximo 0,298%) y las 2.022 aristas del exclave de Neuwerk
   específicamente (máximo similar, 0,293% — no empeora lejos del
   meridiano central tanto como cabría esperar). **Corregido**: nuevo
   `_ADMISSIBILITY_SAFETY_MARGIN = 0.99` en `routing.py` (margen del 1%,
   >3x el peor caso medido), aplicado a la distancia antes de dividir por
   la velocidad. Verificado que no cambia ningún golden file ni la
   conclusión de las mediciones de nodos explorados (259/491/9.377 en vez
   de 255/485/9.008 — sigue siendo una reducción masiva frente a los
   2.560/2.722/43.229 de antes del fix).
2. **`_car_max_speed_cache` era una variable global sin keying — CONFIRMADO
   y corregido.** A diferencia de `_coord_lookup_cache` (keyed por
   `id(nodes_df)`), la caché de velocidad máxima de coche era una única
   variable compartida — si algún día se cargara más de un bundle en el
   mismo proceso, la segunda llamada reutilizaría en silencio la velocidad
   del PRIMER grafo. No se manifiesta hoy (un solo bundle por proceso),
   pero es un bug latente real, no cosmético. **Corregido**: cache ahora
   keyed por `id(G)`, igual que `_coord_lookup_cache`.
3. **`coord_lookup.get(u, (0.0, 0.0))` — fallo silencioso — CONFIRMADO y
   corregido.** Si un nodo faltara alguna vez en `nodes_df` (regresión
   futura en la construcción del grafo), la heurística degradaría en
   silencio a un punto en el origen de coordenadas (fuera de Hamburgo) en
   vez de fallar — exactamente el patrón que hizo posible el bug original
   de esta fase. **Corregido**: ahora lanza `KeyError` explícito con
   contexto si un nodo no está en el lookup, en vez de usar un valor por
   defecto silencioso.
4. **Sin test para la lógica de `_car_max_speed_m_s`** — sin cobertura
   automatizada (solo verificación manual contra el pickle real). Único
   entre las tres velocidades por ser lógica nueva no reducible a una
   constante conocida. **Corregido**: `tests/test_car_max_speed.py`
   (5 tests) cubre velocidades heterogéneas, aristas no drivables que no
   deben contaminar el máximo, aristas con `length_m`/`drive_cost_s`
   nulos o cero, el camino `ValueError` cuando no hay ninguna arista
   drivable válida, y que la caché por `id(G)` no mezcla dos grafos
   distintos en el mismo proceso.

**No corregido en esta fase, registrado como recomendación para más
adelante:** el revisor sugirió también conectar `scripts/
generate_golden_routes.py` a un test de pytest real (hoy la comparación de
golden files es manual, no forzada por CI) — no implementado aquí por ser
un cambio de infraestructura de test más amplio, no una corrección puntual
del fix; queda como recomendación abierta, no como deuda aceptada con
plazo.

Los otros hallazgos ("Minor") no se actuaron por ser de bajo impacto según
la propia calibración del revisor (comentario sobre condición de carrera
benigna en el warm-up de caché; cifras empíricas embebidas en docstrings
que podrían quedar desactualizadas si el grafo se reconstruyera; asimetría
de manejo de errores entre el `ValueError` de car y el resto de
`find_nearest_aeds`).

---

## 2026-08-14 — Dos anotaciones del usuario tras aprobar la Fase 6, antes de abrir la Fase 7

**(1) `_ADMISSIBILITY_SAFETY_MARGIN = 0.99` es una calibración específica
de Hamburgo/EPSG:25832, no un valor universal.** El 0,298% máximo medido
depende de cuán lejos está el área cubierta del meridiano central de la
zona UTM (32N, 9°E) — otra ciudad, otra zona UTM u otro CRS proyectado
tendría una distorsión distinta y este margen no se puede reutilizar sin
volver a medir. Añadido un comentario explícito junto a la constante en
`routing.py` con esta advertencia y el procedimiento a repetir (medir
distancia proyectada recta vs. `length_m` geodésico sobre una muestra
representativa de la nueva zona).

**(2) Conectar `scripts/generate_golden_routes.py` a un test de pytest
real (sugerencia del revisor de la Fase 6): pospuesta explícitamente a
DESPUÉS de la Fase 8**, no antes. Motivo: cambiar la infraestructura del
arnés de regresión justo antes de la fase (7) que más depende de él para
detectar diffs correctos es mala idea — se quiere el arnés estable
mientras se usa como oráculo, no en construcción. Queda como mejora
recomendada, con orden explícito de secuenciación (post-Fase 8), no como
deuda con plazo.

---

## 2026-08-14 — Fase 7: filtro de componente gigante para el snapping de origen — cierra: C3 (parcial — lado origen; lado AED sigue como deuda, ahora cuantificada)

**Implementación (sin tocar `graph_builder_osm.py` ni el pickle en ningún
momento):**
- `src/aed_route/nearest.py`: `compute_giant_component_node_keys(G)` (solo
  lectura, `nx.weakly_connected_components`, ~0,72s medido sobre el grafo
  real) y `filter_node_index_to_keys(node_index, allowed_keys)` (reconstruye
  un `cKDTree` nuevo sobre el subconjunto permitido, sin mutar el
  `node_index` original).
- `app/app.py`: al arranque, calcula (o carga de caché) el componente
  gigante; filtra el `node_index` usado por `snap_origin_to_graph` a esos
  nodos; detecta qué nodos `aed_*` quedan fuera y loguea WARNING con sus
  ids exactos.
- `src/aed_route/routing.py`: `find_nearest_aeds` ahora loguea (nivel
  INFO) cada vez que un candidato se descarta por `NetworkXNoPath` o
  `NodeNotFound`, con modo, nodo de origen y nodo objetivo — antes de esta
  fase ese descarte era completamente invisible.

**Caché atada al checksum del pickle (verificación pedida explícitamente
antes de cerrar la fase):** el artefacto derivado
(`data/processed/graph_giant_component_excluded_nodes.json`) guarda el
SHA-256 del pickle (`sha256_of_file`, nueva utilidad en
`src/aed_route/utils.py`, ~0,7s medido sobre los 364 MB) junto con la
lista de nodos excluidos. Al arranque, se recalcula el checksum del pickle
actual y se compara contra el guardado en la caché — si no coincide, se
loguea un WARNING explícito y se recalcula el componente gigante desde
cero, en vez de confiar en una caché que podría referenciar un grafo
distinto. Hoy el checksum nunca puede cambiar (grafo inmutable +
`chmod 444`, Fase 0), así que esta rama nunca se ejecuta en la práctica —
pero si algún día se hiciera un rebuild (p. ej. para la opción (iv) del
modo car), una caché obsoleta habría dado resultados de snapping
incorrectos en silencio sin este chequeo. Coste: el checksum se
recalcula en CADA arranque (no solo cuando la caché falta), lo que en la
práctica hace que "cachear" ya no ahorre mucho tiempo de reloj (el
chequeo de checksum cuesta casi lo mismo que recalcular el componente
gigante directamente) — se mantiene de todos modos por el rastro de
auditoría que deja en `data/processed/`, no como optimización de
rendimiento real.

**Coste de arranque medido:** ~0,85s adicionales en total (0,7s checksum +
~0,15s reconstruir el índice filtrado, esté o no la caché del componente
gigante actualizada) — insignificante frente a los ~5s de carga del
pickle y los ~20-30s documentados de arranque completo. Anotado también en
`README_deploy.md`.

**Los 9 AEDs fuera del componente gigante — cuantificados por primera vez,
y una métrica DISTINTA de los "2 AEDs omitidos" ya documentados:** el log
de arranque lista explícitamente los 9 node_keys:
`aed_1630112176, aed_2318325116, aed_3336946741, aed_5880920245,
aed_6276396178, aed_6276396179, aed_8840234226, aed_9828734877,
aed_10045300175`. Esto NO es lo mismo que "AED nodes skipped: 2" (ya
documentado en `docs/network_and_graph_build.md`/`routing_methodology.md`):
esos 2 nunca llegaron a ser nodos del grafo (ningún nodo de carretera a
menos de `MAX_SNAP_DISTANCE_M` en el momento de construir el grafo); estos
9 SÍ son nodos reales del grafo, conectados a la red — solo que a un
fragmento pequeño y aislado de ella, no a la red principal utilizable.
Aritmética completa: 141 AEDs en la fuente → 139 se integran como nodos
del grafo (2 omitidos) → de esos 139, 9 son prácticamente inalcanzables
(este hallazgo) y 130 están en el componente gigante y enrutan con
normalidad. Documentado con esta distinción explícita en ambos archivos
de metodología, para que nadie intente "reconciliar" ambas cifras en una
sola.

**Mecanismo del caso `isolated_partial_e` — falso positivo, antes
invisible, documentado como argumento para el rebuild:** antes de esta
fase, ese origen snapeaba (a 0,036 m, prácticamente el punto exacto del
click) a un nodo dentro de un fragmento aislado que tenía, por pura
coincidencia topológica, conectividad interna hacia `aed_5880920245` —
uno de los 9 AEDs fuera del componente gigante — devolviendo una ruta de
apariencia excelente (45,2 s). Esa ruta era completamente real *dentro*
del fragmento aislado, pero ese fragmento no tiene ninguna conexión con el
resto de la red utilizable de Hamburgo: ningún origen real fuera de ese
fragmento diminuto podría haber llegado nunca a ese AED por esa ruta. Era,
en efecto, un **falso positivo silencioso** — peor que una lista vacía,
porque parecía una respuesta correcta. Tras el fix de la Fase 7, el mismo
origen ahora snapea (a 14,2 m) al nodo real más cercano dentro del
componente gigante, y el AED aislado desaparece correctamente de los
resultados, sustituido por AEDs genuinamente alcanzables a un tiempo de
viaje realista (306-486 s). Documentado en detalle en
`docs/routing_methodology.md`, sección "Edge Cases and Observed
Anomalies" — es el argumento más concreto que existe hoy para justificar,
ante el equipo, un futuro rebuild del grafo que re-snapee los 9 AEDs
restantes: este riesgo no es hipotético, ya ocurrió, y era invisible hasta
que se investigó específicamente para construir el arnés de la Fase 5.

**Verificación de golden files — aprobada caso por caso antes de
regenerar, tal como se pidió:** de los 9 casos, exactamente los 3 con
`expectation_fase7: expected_change`/`expected_improvement` cambiaron
(`isolated_flip_c`: 0/0/0 → 3/3/0; `isolated_flip_d`: 0/0/0 → 3/3/0;
`isolated_partial_e`: 1/0/0 → 2/2/0 — con el AED `aed_5880920245`
desapareciendo del resultado, ver mecanismo arriba), y exactamente los 6
con `no_change` se mantuvieron idénticos byte a byte, incluidos los dos
casos ya marcados como "seguirá vacío incluso tras la Fase 7"
(`isolated_stays_empty_a`/`b`) y los dos de fallo estructural sin
relación con el componente gigante (`clausewitz_kaserne`, sin ningún nodo
a <=100m del punto exacto, ni antes ni después; `water_point`). Ningún
caso cambió fuera de lo predicho.
