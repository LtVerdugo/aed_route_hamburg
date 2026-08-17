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

**[CORREGIDO 2026-08-17 — premisa equivocada, ver la entrada de esa fecha
"Corrección: qué hay realmente publicado..." más abajo]:** este párrafo
asumía que borrar archivos de ESTE repositorio podía afectar a una URL
pública real. Es falso: lo publicado en producción es una carpeta
subida a mano, no derivada de este repositorio en absoluto. El borrado
de la Fase 8A(3) no tuvo ni pudo tener ningún efecto sobre esa URL.

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

---

## 2026-08-14 — Fase 7: revisión de código obligatoria — 2 hallazgos "Important" verificados y corregidos

Revisor independiente cargó el pickle real de producción tres veces y
verificó de forma empírica cada cifra (tamaño del componente gigante, los
9 AEDs excluidos coincidiendo carácter a carácter, conteos de golden
files) — todo confirmado correcto. Encontró además, exactamente sobre el
punto que se le pidió verificar explícitamente (invalidación de caché
ante un pickle que cambiara), un problema real que reproduje yo mismo
antes de corregirlo:

1. **La lectura de la caché no era resistente a corrupción — CONFIRMADO
   con dos repros directos, corregido.** `read_json` sobre un JSON
   truncado/corrupto lanza `json.JSONDecodeError` sin capturar; una caché
   con el checksum correcto pero sin `excluded_node_keys` lanza `KeyError`
   sin capturar — ambos crashean el arranque en vez de recomputar, pese a
   que el mecanismo de invalidación por checksum en sí funcionaba bien
   para el caso que se pidió verificar (checksum ausente o de tipo
   incorrecto sí caía correctamente en la rama de recómputo). Reproducidos
   ambos casos con un script mínimo antes de tocar nada. **Corregido**:
   la lógica de caché se extrajo de `app.py` a una función propia y
   testable, `load_or_compute_giant_component` (`nearest.py`), que
   envuelve la lectura completa (parseo JSON, tipo de la raíz, presencia y
   tipo de `excluded_node_keys`) en un único `try/except`, tratando
   cualquier fallo igual que un checksum desactualizado: log de WARNING y
   recómputo, nunca una excepción sin capturar.
2. **Sin cobertura de test para `compute_giant_component_node_keys`,
   `filter_node_index_to_keys` ni la lógica de caché — mismo tipo de hueco
   ya señalado y cerrado una fase antes para `_car_max_speed_m_s`.**
   **Corregido**: `tests/test_giant_component.py` (13 tests) — componente
   gigante sobre grafos sintéticos con componentes de tamaños distintos,
   direccionalidad "weakly connected", grafo vacío; filtrado de
   `node_index` preservando la correspondencia key↔coordenada y
   reconstruyendo el `cKDTree` sobre el subconjunto correcto; y las 6
   ramas de `load_or_compute_giant_component` (miss, hit válido, checksum
   obsoleto, JSON corrupto, esquema incompleto, raíz no-dict) — estas dos
   últimas son regresiones directas de los repros del hallazgo 1, no
   solo cobertura genérica.

**Recomendación del revisor incorporada, no solo anotada:** "weakly
connected" es una condición más débil que "alcanzable con `astar_path`
para un modo concreto" (la direccionalidad de coche puede dejar un nodo
del componente gigante inalcanzable igualmente). Añadida como nota
explícita en el docstring de `compute_giant_component_node_keys` — el
logging de `NetworkXNoPath` ya añadido en el commit anterior es lo que da
visibilidad sobre esos casos residuales, que siguen siendo posibles y
esperados.

**Hallazgos "Minor" corregidos de paso** (bajo impacto, pero triviales de
aplicar): `del node_index_unfiltered` tras filtrar (evita mantener un
segundo `cKDTree` de 658k puntos en memoria sin necesidad);
`compute_giant_component_node_keys` ahora falla con un `ValueError`
explícito sobre un grafo sin nodos, en vez de un `ValueError` críptico de
`max()` sobre secuencia vacía; el campo `note` de
`tests/golden/MANIFEST.json` corregido para no afirmar "generado ANTES de
cualquier fix" cuando en realidad registra el commit de la última
regeneración (que ya incluye las Fases 6 y 7). El comentario en español
dentro de `config.py` (única inconsistencia de idioma señalada, el resto
del archivo está en inglés) se dejó sin cambiar — cosmético, y el propio
revisor confirmó que ya hay comentarios en español en otras partes del
proyecto.

Verificado tras las correcciones: 20/20 tests en verde
(`pytest tests/ -v` → "20 passed": 5 de `test_car_max_speed.py` + 2 de
`test_heuristic_admissibility.py` + 13 nuevos de
`test_giant_component.py`). Golden files sin cambios de contenido (solo
el hash de commit y el texto de `note` en `MANIFEST.json`, ambos
actualizaciones intencionadas de esta revisión). Arranque verificado en
vivo: mismo comportamiento exacto que antes del refactor (mismos logs,
mismos 9 AEDs, mismo WARNING).

---

## 2026-08-14 — Fase 8A(1): mitigación del fallo silencioso implementada — cierra: hallazgo del fallo silencioso (registrado en la verificación visual de Fase 5/6)

**Implementado en el frontend vivo** (`static/index_original.html`,
`static/app_original.js`, `static/styles_original.css` — confirmado de
nuevo que estos son los archivos servidos en `/`, no los huérfanos):

1. Nuevo elemento `#no-results`, distinto de `#hint` (que antes se
   reutilizaba también para "sin resultados", impidiendo distinguir
   "no has hecho click" de "hiciste click y no hay ruta"). `renderPanel()`
   ahora llama a `showNoResults()` en vez de `showHint()` cuando
   `state.results.length === 0`.
2. Botón "Car" deshabilitado (`disabled` en el HTML — un botón disabled no
   dispara `click`, no hizo falta tocar el handler del selector de modo),
   con una nota permanente visible (`#car-disabled-note`) y `title` como
   tooltip, ambos con el mismo texto.
3. **Texto aislado en `UI_COPY`** (`static/app_original.js`), marcado
   explícitamente en el propio código como BORRADOR pendiente de
   aprobación del equipo, con el texto exacto que ya estaba en borrador
   en esta misma entrada (Fase 4(c), 2026-08-14) — sin redactarlo de
   nuevo. Cambiar el texto solo requiere editar las cadenas de `UI_COPY`,
   sin tocar `renderPanel()`, `showNoResults()` ni ninguna otra lógica.

**Verificado que la nueva rama cubre los tres casos legítimos de "sin
resultados"**, pedido explícitamente: consultado `POST /api/route` en
vivo para agua (53.5080, 9.9350), Clausewitz-Kaserne/fuera de
`MAX_SNAP_DISTANCE_M` (53.5624, 9.8327), y un origen fuera del componente
gigante sin flip (53.577362, 9.881057) — los tres devuelven exactamente
`{"results": []}`, la misma forma exacta que consume
`renderPanel()`. El backend no distingue el motivo en la respuesta, así
que una única rama en el frontend basta para los tres — no fue necesario
(ni se intentó) que el frontend adivinara la causa.

Verificado también que el camino de éxito no se rompió (mismo resultado
exacto que antes, 165.8s en `dense_urban`) y que los 20 tests de backend
siguen en verde (este cambio es puramente de frontend, no debería
afectarlos, y no lo hizo).

---

## 2026-08-14 — Fase 8A(1): revisión de código — 5 hallazgos "Important" verificados y corregidos

Revisor independiente arrancó el frontend real, reprodujo los tres casos
legítimos de "sin resultados" y el camino de éxito contra el backend real
(coincidiendo exactamente con lo ya verificado), corrió `node --check` y
el suite de pytest — todo confirmado. Encontró además 5 problemas reales
en la lógica del propio ítem, no solo de estilo, todos reverificados por
mí antes de corregirlos:

1. **Errores reales del backend se interpretaban como "sin AED
   alcanzable" — CONFIRMADO y corregido.** `fetch` no lanza excepción por
   un status HTTP de error; sin comprobar `res.ok`, un 400 (modo
   inválido) o un 500 real caían en la misma rama que `results: []`,
   haciendo una afirmación específica y potencialmente falsa. Reproducido
   con `mode: "bogus"` → 400 real. **Corregido**: `res.ok` se comprueba
   antes de leer `data.results`; cualquier fallo de red, HTTP o forma de
   respuesta inesperada va a una función nueva, `showRequestError()`, con
   su propio texto (`UI_COPY.requestError`), distinta tanto de "sin
   resultados" como del hint inicial.
2. **El `catch` de errores de red seguía usando `showHint()`** — el mismo
   texto genérico de "haz click en el mapa" reaparecería justo después de
   que el usuario ya hubiera hecho click, contradiciendo lo que acababa
   de hacer. **Corregido**: usa `showRequestError()` también.
3. **Carrera de `state.mode` — CONFIRMADO y corregido.** Si el usuario
   cambia de modo mientras una petición sigue en vuelo, `showNoResults()`
   leía `state.mode` en el momento de la respuesta, no el modo con el que
   realmente se hizo la petición que falló — pudiendo mostrar "no se
   pudo por bike" para una petición que en realidad se hizo por walk.
   **Corregido**: el modo se captura en una constante local al enviar la
   petición y se pasa explícitamente a `showNoResults(mode)`.
4. **Accesibilidad: `disabled` nativo saca el botón Car del árbol de
   accesibilidad — CONFIRMADO, corregido.** Un lector de pantalla en modo
   de lectura lineal nunca se encontraría con el botón ni sabría por qué
   falta. **Corregido**: `aria-disabled="true"` + `tabindex="-1"` en vez
   de `disabled`; como `aria-disabled` no bloquea `click` por sí solo, se
   añadió el guard explícito correspondiente en el handler existente.
   `aria-label` añadido con el motivo.
5. **El modal de ayuda seguía diciendo "Select Walk, Bike or Car... each
   mode uses different road rules"** — contradicción inmediata con el
   botón recién deshabilitado. **Corregido**: texto actualizado para
   mencionar que Car no está disponible temporalmente.

**Hallazgo sobre el propio texto en borrador, NO corregido en el código a
propósito** (es una cuestión de redacción, no de lógica, y el usuario
pidió usar el texto ya acordado sin reescribirlo): con Car deshabilitado,
si falla walk, el mensaje dice "Try Walk or Bike" — sugiriendo repetir el
modo que acaba de fallar. Señalado explícitamente aquí para que el equipo
lo tenga en cuenta al aprobar el texto definitivo; no se ha tocado
`UI_COPY.noResults`.

**Refactor de paso, motivado directamente por el hallazgo 1**: las cinco
funciones que muestran/ocultan los paneles de la barra lateral
(`hint`/`loading`/`no-results`/`request-error`/`results`) ahora comparten
un único `hideAllPanels()` en vez de repetir la lista de "ocultar los
demás" en cada una — el propio hallazgo 1 mostró en la práctica lo fácil
que es olvidar un panel al añadir uno nuevo. `showHint()` quedó sin
ninguna llamada real tras separar sus dos usos anteriores en funciones
distintas — se retiró en vez de dejarla como código muerto nuevo.

Verificado tras las correcciones: 20/20 tests de backend en verde (sin
cambios, es un cambio de frontend), `node --check` sin errores, y en
vivo: un modo inválido real devuelve 400 y ya no se confunde con "sin
resultados"; los tres casos legítimos de agua/fuera de
`MAX_SNAP_DISTANCE_M`/fuera del componente gigante siguen devolviendo
`results: []` sin cambios; el HTML servido incluye `aria-disabled`,
`tabindex="-1"` y el nuevo `#request-error`.

## 2026-08-14 — Ítem 8A(2): `SHORTLIST_EUCLIDEAN_K` = 5, implementado — cierra: C6

Implementado lo aprobado teóricamente en la Fase 4(a) (ver entrada de
arriba). `config.py`: `SHORTLIST_EUCLIDEAN_K` de 3 a 5.

**Validación empírica que la decisión no tenía hasta ahora — deja de ser
una justificación teórica.** Regenerados los 9 casos golden con K=5 real
(tras resolver un falso negativo de proceso, ver nota de más abajo) y
comparados caso por caso contra los golden K=3 committeados:

- **`isolated_flip_c`, modo walk: cambia el rank 1.** Con K=3 el mejor
  resultado era el AED `3325525940` (1606.2 s). Con K=5, el AED
  `3024050425` — que con K=3 nunca se evaluaba, por no estar entre los 3
  euclídeo-más-cercanos desde ese origen — entra en la shortlist y resulta
  **90.2 s más rápido a pie** (1516.0 s). Es la prueba de que el prefiltro
  euclídeo con K=3 podía (y en este caso concreto lo hacía) devolver una
  ruta subóptima como "mejor ruta", porque cercanía en línea recta no
  implica cercanía en red. Este es el hecho concreto que faltaba: la
  Fase 4(a) justificaba K=5 citando `docs/routing_methodology.md`, pero
  sin una demostración de un caso real afectado.
- Ningún otro origen cambia de rank 1.
- 5 de los 9 orígenes ganan alternativas (los que ya tenían resultado);
  19 rutas-alternativa adicionales en total repartidas en walk/bike
  (dense_urban, boundary_edge, isolated_flip_c: +2/+2; isolated_flip_d:
  +2 walk / +1 bike; isolated_partial_e: +2/+2). Car sigue en 0 en todos
  los casos — no relacionado con K, es el fallo estructural C_car
  (Fase 8B, sin resolver).
- Ningún origen que hoy tenía resultados pasa a tener menos.

**Coste medido** (no invocado, medido directamente sobre
`find_nearest_aeds` con los 9 orígenes, 2 repeticiones): en el caso
típico (orígenes con buena conectividad en el modo evaluado) el coste
extra de K=5 es de ~15–150 ms, barato. En orígenes con conectividad
parcial por modo, el coste puede dispararse a varios segundos por cada
candidato euclídeo-cercano-pero-inalcanzable — ver hallazgo abierto
inmediatamente debajo, registrado aparte porque es un problema
preexistente que K=5 solo multiplica, no algo introducido por este
cambio.

**Corrección de doc, verificada no asumida:**
`docs/routing_methodology.md` afirmaba "Compare routes toggle showing up
to 4 alternative routes" como si fuera una garantía. Con K=5 el máximo
teórico es 4 alternativas (rank 2-5), pero solo si las 5 búsquedas A*
tienen éxito — verificado que esto NO siempre ocurre
(`isolated_flip_d`/bike se queda en 3 alternativas porque un candidato es
descartado por `NetworkXNoPath`). Corregida la frase para reflejar la
condicionalidad real.

**Nota de proceso — falso negativo por servidor con config en memoria:**
la primera medición tras editar `config.py` dio resultados idénticos a
K=3 y cero descartes registrados, una combinación internamente
inconsistente. Causa: el proceso uvicorn usado había arrancado 97 s ANTES
del cambio en `config.py` (confirmado con `ps -o lstart`, no con la
primera línea del log de arranque, que es engañosa — ver precaución
añadida en `docs/smoke_test.md`). Proceso reiniciado, medición repetida
correctamente. Ver `docs/smoke_test.md` para el procedimiento a seguir en
el futuro.

`tests/golden/*.json` y `MANIFEST.json` regenerados con K=5 real y
committeados junto con el cambio de `config.py`.

## 2026-08-14 — Ítem 8A(2): hallazgo abierto — latencia de candidatos euclídeo-cercanos pero inalcanzables (NO implementado)

**No se implementa en esta fase — queda abierto para decidir con el
equipo si va junto a la Fase 8B (modo car) o después.**

Al medir el coste de K=5 (ver entrada de arriba) se observó que, cuando
uno de los K candidatos euclídeo-más-cercanos a un origen resulta
inalcanzable en el modo consultado, el coste de descartarlo por
`NetworkXNoPath` no es barato: A* debe explorar buena parte (o la
totalidad) del componente conexo alcanzable antes de poder concluir que
no existe camino. Medido directamente sobre `find_nearest_aeds`:

- `isolated_flip_d`, modo bike: 25 ms (K=3, los 3 candidatos son
  alcanzables) → **5.1 s** (K=5, el 5º candidato euclídeo,
  `aed_4160068089`, no es alcanzable en bici desde ese origen).
- `isolated_flip_d`, modo car: 7.4 s (K=3, los 3 candidatos ya fallan,
  ~2.5 s cada uno) → **12.4 s** (K=5, 5 candidatos fallan).

Esto es **preexistente** — ya ocurría con K=3, es inherente a tener un
grafo con componentes desconectados por modo y usar `NetworkXNoPath`
como señal de descarte — pero K=5 lo expone en más combinaciones
origen/modo al evaluar 2 candidatos euclídeos más por consulta, cada uno
con su propio riesgo de ser una búsqueda fallida cara.

**Por qué importa más de lo que parece:** `app/app.py` arranca uvicorn
sin especificar `--workers` (por tanto 1 worker); aunque `POST
/api/route` usa `asyncio.to_thread` (Fase 3a), eso mueve el trabajo a un
hilo del threadpool, no lo paraleliza de verdad frente a otras peticiones
que compitan por el mismo threadpool. Con `--workers 1`, varios segundos
de exploración A* fallida en una petición pueden degradar la latencia
percibida por otros usuarios concurrentes, no solo por quien hizo la
consulta cara.

**Línea de solución probable a evaluar más adelante (no implementada
aquí):** comprobar la pertenencia al componente conexo del modo ANTES de
lanzar A* hacia un candidato, en vez de descubrir la inalcanzabilidad
mediante una búsqueda completa que falla. Ya existe la maquinaria de
componente gigante de la Fase 7
(`compute_giant_component_node_keys`/`filter_node_index_to_keys` en
`nearest.py`) para el lado del origen; para car, la Fase 4 ya midió los
componentes del subgrafo drivable. Si el candidato y el origen no
comparten componente conexo en el modo consultado, la inalcanzabilidad es
segura por definición, y descartarlo cuesta una consulta de pertenencia a
un set en vez de una exploración completa de A*. Requiere diseño propio
(qué componente por modo, cómo cachearlo, coste de mantenerlo
sincronizado con el filtrado ya existente) — no se evalúa ni se implementa
en este ítem.

## 2026-08-17 — Ítem 8A(4): `README.md` reemplazado por un aviso corto — cierra: C1 (parte doc), C9

Implementado lo aprobado en la Fase 4(b) (ver entrada de 2026-08-14 más
arriba). Contenido anterior de `README.md` (describía el prototipo
estático de Hamburg-Mitte, ya retirado en el Ítem 8A(3)) sustituido por
un aviso corto que:

- describe el producto real (Hamburg completa, con backend, city-wide);
- dice explícitamente que la app se sirve en la raíz de la ruta pública
  (`.../demos/aed-routing/`), **no** bajo `/static/`;
- deja constancia de que `.../demos/aed-routing/static/` dejó de servir
  la app (404) al retirarse el prototipo en 8A(3) — para quien la tenga
  enlazada;
- no afirma nada sin matizar sobre el modo car: dice que está
  deshabilitado en la UI a la espera de una decisión de equipo (Fase 8B);
- remite a `README_deploy.md` para instalación/despliegue, sin duplicar
  sus instrucciones.

**Pendiente, explícitamente del usuario y no de este agente (reafirma lo
ya anotado en la entrada de Fase 4(b) de arriba, sigue sin verificarse):**
avisar a su equipo de que la URL `.../demos/aed-routing/static/` dejó de
funcionar, por si está enlazada desde la web institucional o algún
material publicado. Este agente no tiene forma de verificar enlaces
externos al repositorio.

**[CORREGIDO 2026-08-17 — ver la entrada de esa fecha "Corrección: qué
hay realmente publicado..." más abajo]:** esta afirmación es incorrecta.
Esa URL NO ha dejado de funcionar — sigue sirviendo, sin verse afectada
por nada de este trabajo. El texto de `README.md` que decía "it now
returns 404" también se ha corregido. No hay nada que avisar hoy; el
aviso real (o una redirección) hará falta el día que se despliegue la
versión con backend, si es que llega a desplegarse.

## 2026-08-17 — Ítem 8A(5): `README_deploy.md` corregido — cierra: parte del riesgo de despliegue explícito registrado en la entrada del 2026-08-14 sobre `PUBLIC_BASE_PATH`

Corregido, verificable directamente contra el repositorio, sin suponer
nada sobre el servidor real de HCU:

1. **`PUBLIC_BASE_PATH` marcado explícitamente como NO soportado.**
   Sustituida la instrucción rota (mandaba "arrancar uvicorn con
   `PUBLIC_BASE_PATH`" mostrando un comando que ni siquiera fijaba esa
   variable, porque el código nunca la lee — ya diagnosticado el
   2026-08-14) por una explicación directa: si el proxy real no retira el
   prefijo `/demos/aed-routing/` antes de reenviar, TODAS las rutas —
   incluida la raíz — devuelven 404 del backend antes de servir ningún
   HTML, porque `FastAPI()` se instancia sin `root_path` ni middleware de
   `X-Forwarded-*` (verificado leyendo `app/app.py`, no ha cambiado desde
   el diagnóstico de Fase 4). Soportarlo exigiría un cambio de código
   (`root_path`/middleware), fuera de alcance de esta remediación.
2. **Los dos bloques nginx casi-duplicados, consolidados en uno solo** —
   el del modo que sí funciona (proxy retira el prefijo). Se eliminó el
   segundo bloque, asociado al modo ahora marcado como no soportado.
3. **Párrafo sobre "dos variantes de frontend" en `static/`, corregido**
   — quedó desactualizado por el propio Ítem 8A(3) (el prototipo huérfano
   ya no existe). Ahora describe correctamente una sola variante viva.
4. **Árbol de archivos de la sección "Copy the project", corregido en dos
   puntos** verificables por `find` sobre el repo real: (a) listaba
   `static/app.js`/`index.html`/`styles.css` (retirados en 8A(3)) en vez
   de `static/app_original.js`/`index_original.html`/`styles_original.css`;
   (b) listaba `wsgi.py` en la raíz del proyecto cuando en realidad vive
   en `app/wsgi.py` — este segundo error no tiene relación con 8A(3), es
   una inexactitud preexistente detectada al revisar el árbol completo.

**Pedido explícitamente por el usuario: revisar si quedaba alguna otra
afirmación sobre el despliegue sin verificar, listando sin corregir las
que exigirían suponer algo sobre el servidor real de HCU.** Resultado de
esa revisión completa del documento:

- **No se encontró ninguna afirmación NUEVA que requiera esa suposición.**
  Las dos únicas que sí la requieren (el puerto 5000 vs. 5050, y si el
  proxy real retira el prefijo) ya estaban honestamente marcadas como "no
  verificado contra la configuración real" desde fases anteriores (Fase
  3b y este mismo ítem) — no hacía falta añadir nada.
- **Dos hallazgos SÍ verificables sin suponer nada de HCU, pero que
  cambian una recomendación de comportamiento en vez de solo corregir un
  dato — no implementados aquí, a la espera de decisión explícita:**
  - El comando de arranque recomendado en el paso 5
    (`uvicorn app.app:app --host 0.0.0.0 --port 5000 --reload`) incluye
    `--reload`, una opción de uvicorn documentada como solo para
    desarrollo (vigila el sistema de archivos y reinicia el proceso en
    cada cambio). Esto es inconsistente con el propio `Dockerfile` del
    repo, cuyo `CMD` arranca uvicorn SIN `--reload`, y con la precaución
    recién añadida en `docs/smoke_test.md` (Ítem 8A(2)) que asume
    explícitamente un servidor sin `--reload`. Nunca se había discutido
    ni verificado en ninguna fase anterior (`grep -- "--reload"` en todo
    el repo antes de esta revisión solo encontraba las dos apariciones en
    este mismo documento). No se ha corregido porque cambia el
    procedimiento de despliegue recomendado, no solo un dato — decisión
    a tomar explícitamente, no asumida por este agente.
  - "Python 3.10 or higher" (Prerequisites) no está verificado contra
    ninguna restricción formal del proyecto (no hay `pyproject.toml` ni
    `setup.cfg` con `requires-python`); el `.venv` usado durante toda
    esta remediación corre Python 3.13.13 sin problema, lo cual no
    contradice la afirmación pero tampoco la confirma como mínimo real.
    Prioridad baja, mencionado por completitud de la revisión pedida.

Verificado tras las correcciones: `git diff README_deploy.md` revisado
línea por línea; ninguna sección de las ya verificadas en fases
anteriores (nota de puerto, notas de arranque, coste de startup, verificación
de caches) fue tocada. No requiere `requesting-code-review` (solo
documentación, sin cambios de código).

## 2026-08-17 — Ítem 8A(6): script de benchmark K=3 vs K=5, commiteado — cierra: Minor de requesting-code-review sobre 8A(2)

`scripts/benchmark_shortlist_k.py`, nuevo. Reconstruye el benchmark ad hoc
usado en el Ítem 8A(2) (entonces solo en `/tmp`, no reproducible) como un
script versionado, con la misma metodología: llama DIRECTAMENTE a
`find_nearest_aeds` (no vía HTTP) pasando `k` explícito, precisamente para
que el resultado nunca dependa de `SHORTLIST_EUCLIDEAN_K` en `config.py` ni
de si un servidor vivo llegó a cargar esa constante — evita a propósito el
falso negativo de proceso documentado en la entrada de 8A(2) de más arriba.
Reutiliza los 9 orígenes de `scripts/generate_golden_routes.py` (import
directo de `CASES`, no una copia).

**Verificado reproduciendo las cifras del Ítem 8A(2)** con
`.venv/bin/python3 scripts/benchmark_shortlist_k.py --repeat 2`:
walk K3=565.7ms→K5=586.4ms (+3.7%), bike K3=571.8ms→K5=1154.8ms (+102.0%),
car K3=1638.6ms→K5=2719.7ms (+66.0%) — coinciden con el orden de magnitud
registrado entonces (+4.7%/+101.5%/+65.5%); la pequeña variación entre
ejecuciones es ruido normal de medición de tiempo real (wall-clock), no un
cambio de comportamiento.

## 2026-08-17 — Ítem 8A(7): `--reload` retirado del comando de arranque recomendado en `README_deploy.md` — cierra: hallazgo (a) registrado en 8A(5)

Quitado `--reload` del único comando de arranque de producción que lo
tenía (Paso 5). Motivo, ya registrado en 8A(5): es un flag de desarrollo
de uvicorn (reinicia el proceso entero al detectar cualquier cambio de
archivo bajo el árbol vigilado); con el grafo de 364 MB, un reinicio
espurio (p. ej. por un log, o por un edit de docs dentro del árbol
vigilado) deja el servicio caído ese tiempo, en producción, sin motivo.
Contradecía además al `Dockerfile` propio, cuyo `CMD` nunca lo incluyó.

**Verificado tras el cambio:** el comando resultante
(`uvicorn app.app:app --host 0.0.0.0 --port 5000`) es ahora **idéntico**
(mismo host, mismo puerto) al `CMD` del `Dockerfile`
(`["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "5000"]`).
Ninguno de los dos fija `--workers` explícitamente — ambos dependen del
valor por defecto de uvicorn (1), que es exactamente el requisito que la
sección "Important notes" del propio documento ya exige por separado
("--workers must be 1"); no hacía falta añadir el flag explícito para
cumplirlo, solo dejar de contradecirlo con `--reload`.

No requiere `requesting-code-review` (solo documentación).

## 2026-08-17 — Corrección del usuario: qué hay realmente publicado en `.../demos/aed-routing/static/`, y que ninguna corrección de las Fases 0-8A está en producción

**Corrección aportada por el usuario, no descubierta por este agente.**
Dos afirmaciones de este log y de `README.md` eran incorrectas por una
premisa equivocada: que la URL pública real derivaba de este
repositorio. No es así.

**(a) Qué hay publicado hoy en `https://www.cml.hcu-hamburg.de/demos/aed-routing/static/`:**
una carpeta `static/` subida A MANO, con solo los archivos necesarios
para un prototipo estático de Hamburg-Mitte con GeoJSON precomputados y
sin backend. **No es este repositorio** — ni el `static/` de este repo
antes de la Fase 8A(3), ni después. Sigue funcionando hoy exactamente
igual que siempre, sin verse afectada por nada de este trabajo,
incluido el borrado del prototipo huérfano en 8A(3) (`static/index.html`
+ `app.js` + `styles.css` + 3 geojson **de este repositorio**, un
conjunto de archivos distinto y sin relación con lo que hay subido en el
servidor real).

Corregidas las dos afirmaciones falsas resultantes de esa premisa:
- El "pendiente" registrado en la entrada de Fase 4(b) (2026-08-14) y
  reafirmado en la entrada del Ítem 8A(4) (2026-08-17) — "avisar de que
  la URL dejó de funcionar" — **no aplica hoy**. Marcado con un puntero
  a esta entrada en ambos sitios, sin borrar el texto original (este log
  es de solo-adición).
- `README.md` decía "it now returns 404" sobre esa URL — falso, corregido
  directamente en el archivo (ver commit de esta misma fecha). La URL
  seguirá funcionando hasta que, si alguna vez ocurre, se despliegue la
  versión con backend — momento en el que sí hará falta avisar al equipo
  o mantener una redirección. Hasta entonces no hay nada roto ni nada
  que comunicar.

**(b) Ninguna corrección de las Fases 0-8A está en producción — señalado
explícitamente porque es fácil perderlo de vista tras 30 commits de
trabajo:** todo este trabajo se ha hecho sobre código que nunca se ha
desplegado en ningún sitio. En particular:
- el bug de la heurística A* subóptima (Fase 6, corregido en `routing.py`),
- el fallo silencioso y el resto de correcciones del modo `car` (Fase 4,
  8A(1)),
- el filtro de snapping al componente conexo gigante (Fase 7),
- y el cambio de `SHORTLIST_EUCLIDEAN_K` (Ítem 8A(2)),

todos afectan exclusivamente a la aplicación con backend de este
repositorio, que hoy no corre en ningún servidor accesible al público.
Lo que la gente ve hoy en producción (el prototipo estático de
Hamburg-Mitte descrito en (a)) no tiene heurística A*, no tiene modo
car con fallo silencioso tal como lo describe este log, y no tiene
componente gigante que filtrar — es un artefacto distinto, generado por
otro proceso (`build_hamburg_mitte.py`, ni siquiera incluido en este
repo), no afectado por ninguna de estas 8 fases. Ver también la entrada
siguiente sobre la limitación estructural de infraestructura, que
explica por qué esto es así y probablemente seguirá siéndolo sin una
decisión de arquitectura explícita.

## 2026-08-17 — Limitación estructural del usuario: el servidor de HCU solo aloja archivos estáticos — la app con backend NO es desplegable en la infraestructura actual

**Aportado por el usuario, por encima en importancia de cualquier
corrección de las Fases 0-8A.** El servidor real de HCU
(`www.cml.hcu-hamburg.de`) solo tiene capacidad para alojar archivos
estáticos — no hay posibilidad de mantener un proceso Python
persistente. La aplicación con backend de este repositorio (FastAPI +
uvicorn + 364 MB de grafo cargados en memoria) **no es desplegable hoy
en esa infraestructura**, independientemente de lo correcto que sea el
código tras esta remediación.

`README_deploy.md` describe un procedimiento (Pasos 1-7) que asume un
proceso persistente arrancable por línea de comandos, con puerto propio
y proxy inverso delante — un modelo de despliegue que la infraestructura
actual no soporta en absoluto. Se ha añadido una nota al inicio de ese
documento para que nadie lo siga contra el servidor real (ver commit de
esta misma fecha).

**Desplegar esta versión no es "subir la carpeta nueva" como se hizo con
el prototipo estático** — es un despliegue de naturaleza distinta:
proceso persistente en segundo plano (no una petición-respuesta stateless
de servidor de archivos), proxy inverso para exponerlo bajo la ruta
pública, gestión de puerto, `--workers 1` obligatorio (el grafo de 364 MB
en memoria no es seguro de compartir entre procesos), y un arranque de
5-30s (según si el grafo se carga de caché o se reconstruye) que un
servidor de archivos estático no necesita gestionar en absoluto. Requiere
un tipo de infraestructura que hoy no existe para este proyecto, no una
variación del mecanismo de subida ya usado.

**Las tres verificaciones contra el servidor real de HCU registradas en
fases anteriores quedan reclasificadas de PENDIENTES a EN SUSPENSO** —
no tiene sentido verificarlas hasta que exista infraestructura capaz de
ejecutar la app:
1. Si el proxy real escucha/reenvía al puerto 5000 y no 5050 (Fase 3b).
2. Si el modo de proxy configurado retira el prefijo público antes de
   reenviar, o lo reenvía sin tocar — el escenario `PUBLIC_BASE_PATH`,
   ya marcado como no soportado por el código (Ítem 8A(5)).
3. Que ningún mecanismo real de arranque (systemd, supervisor, o
   cualquier otro que se use el día de un despliegue real) reintroduzca
   `--reload` u otra configuración de desarrollo (Ítem 8A(7)) — este
   repositorio ya no lo recomienda en ningún sitio, pero verificarlo
   contra el proceso REAL que arranque la app solo tiene sentido cuando
   ese proceso exista.

Las tres seguirán en suspenso hasta que haya una decisión de
infraestructura.

**Pregunta de arquitectura que esto abre, planteada aquí sin analizarla
— corresponde decidirla al usuario y su equipo, no a este agente:**
¿se consigue infraestructura distinta capaz de correr un proceso Python
persistente (VM, contenedor con orquestador, servicio gestionado), o se
adapta el enfoque de esta aplicación para precomputar resultados a
estático, como ya hace el prototipo de Hamburg-Mitte actualmente
desplegado? Esta segunda vía tendría implicaciones directas sobre qué
partes del trabajo de las Fases 0-8A siguen siendo aplicables (la
corrección de la heurística A* y el filtro de componente gigante son
relevantes en cualquier caso, para precomputar mejor; el modo car y el
snapping dependen de cómo se precompute). No evaluado aquí — es la
decisión previa de la que depende todo lo demás.

## 2026-08-17 — El repositorio local NO comparte historia de git con `origin/main` — decisión consciente de NO reescribir el historial antes de publicar

Verificado tras `git remote add origin` + `git fetch origin` (2026-08-17,
solo lectura, sin pull/merge/rebase/reset): `git merge-base HEAD
origin/main` no encuentra ningún ancestro común (exit code 1). El commit
baseline de este repositorio local (`860b5d7`, rama `main`, ver entrada
de más arriba sobre el prefijo `chore:`) no desciende de ningún commit
del histórico real de `origin/main` en GitHub (12 commits, desde
`2313c44 "Initial commit"` hasta `ac94b9c "chore: add original static
files and demo response data"`, HEAD remoto actual). Es decir: este
repositorio local se inicializó como una historia de git nueva y
separada en algún momento anterior a esta remediación (antes del commit
baseline), no como un clon de GitHub — un hecho estructural preexistente,
no introducido por este trabajo.

**El contenido, en cambio, es casi idéntico:** comparado el árbol de
`main` local contra `origin/main` (`git diff --stat`, no historia, solo
contenido), la diferencia son 29 archivos, todos preexistentes y sin
relación con la remediación — 17 archivos bajo `scratch/` y
`src/aed_route/indoor.py`, presentes en el repositorio local pero
ausentes en `origin/main`, más una diferencia menor de 16 líneas en
`src/aed_route/config.py` ya presente antes de la Fase 0. Ninguno de
estos 29 archivos fue tocado por ninguna fase de esta remediación.

**Consecuencia práctica, registrada para cuando se abra un PR:** al no
compartir historia, GitHub no podrá calcular un merge limpio entre
`remediation/audit-2026-08` y `origin/main` — mostrará "unrelated
histories" y es probable que el diff del PR incluya como "añadidos" esos
29 archivos preexistentes, ruido ajeno al trabajo real de las Fases 0-8A.
Con 90.288 inserciones ya en el diff real de la remediación, esta señal
adicional es marginal — el diff completo no es el mecanismo de revisión
previsto de todos modos; la revisión real se apoya en
`docs/decisions.md` (este archivo) y en el plan
(`docs/superpowers/plans/2026-08-14-audit-remediation.md`), no en leer
línea a línea un diff de ese tamaño.

**Decisión explícita del usuario: NO reescribir el historial de git
para reconciliarlo con `origin/main` antes de publicar.** Reescribirlo
significaría rehacer los 30 commits de esta rama (autoría, mensajes,
fechas relativas al historial real) sobre una base distinta, con riesgo
de invalidar el trabajo ya verificado (cada commit de esta rama fue
revisado y su `git log -1 --format=full` confirmado en su momento) a
cambio de un beneficio que hoy no aporta nada — el trabajo no es
desplegable de todos modos (ver entrada anterior sobre la
infraestructura de HCU) y no hay prisa de fusión. Publicar la rama ahora
resuelve lo urgente (el trabajo existe solo en este portátil) sin ese
riesgo; el problema de historia no compartida es una cuestión de
legibilidad de revisión a resolver más adelante, si acaso, no un
bloqueante técnico del push (`git push` crea una referencia nueva, no
toca `origin/main`).
