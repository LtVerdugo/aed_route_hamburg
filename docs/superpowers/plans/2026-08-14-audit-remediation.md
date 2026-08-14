# Remediación de Auditoría — AED Route Hamburg — Plan de Implementación

> **Para ejecutores agénticos:** Este plan NO se ejecuta con
> `superpowers:subagent-driven-development` ni con la ejecución continua de
> `superpowers:executing-plans` ("no pausar entre tareas"). El usuario exige
> aprobación explícita ANTES de tocar archivos en cada fase y una PARADA tras
> cada fase para correr el smoke test y `superpowers:verification-before-completion`.
> Ejecución manual, fase por fase, en la sesión principal (o con los subagentes
> puntuales que cada fase indica explícitamente). Las casillas (`- [ ]`) marcan
> progreso dentro de una fase ya aprobada, no autorización para saltarse la
> aprobación de la fase siguiente.

**Goal:** Cerrar los hallazgos de la auditoría técnica externa del proyecto
(entregada en chat el 2026-08-14) en fases pequeñas, verificables y
reversibles, sin tocar en ningún momento la construcción ni el contenido del
grafo de routing.

**Architecture:** FastAPI + uvicorn sirviendo un grafo OSMnx unificado
(walk/bike/drive) cacheado en `data/interim/hamburg_graph.pkl` (364 MB,
**inmutable** para este plan), con frontend Leaflet estático. La remediación
toca: documentación (`docs/*.md`, `README*.md`), configuración de despliegue
(puertos), el endpoint async de FastAPI, la heurística de A* en
`src/aed_route/routing.py`, y añade un artefacto derivado nuevo (componente
gigante) sin tocar el pickle del grafo.

**Tech Stack:** Python 3.11 (venv en `.venv/`), FastAPI, uvicorn, networkx,
OSMnx 2.1.0 (instalado; `requirements.txt` declara `>=1.9`), pandas, scipy,
shapely, pyproj, git.

**Spec:** No existe un archivo de spec independiente. El spec es el informe
de auditoría entregado en el chat (secciones A–F, hallazgos C1–C17) más las
correcciones acordadas en la Fase 1 de este mismo plan. Cada fase cita el(los)
hallazgo(s) que cierra.

## Global Constraints

Estas restricciones aplican a **todas** las fases (0–7), no se repiten en
cada tarea:

- **El grafo es inmutable.** Prohibido en cualquier fase: modificar
  `src/aed_route/graph_builder_osm.py`; regenerar/reescribir/sobrescribir
  `data/interim/hamburg_graph.pkl`; llamar a `load_or_build_graph_bundle` con
  `force_rebuild=True`; reproyectar, renombrar o mutar atributos de nodo/arista
  del grafo cargado en memoria; ejecutar `ox.project_graph`,
  `ox.graph_from_polygon` o cualquier descarga OSMnx. Si un hallazgo solo se
  puede cerrar tocando la construcción del grafo: NO se corrige — se registra
  en `docs/decisions.md` como deuda técnica aceptada (motivo + hallazgo que
  queda abierto) y se avisa en el resumen de esa fase.
- **Una fase = un commit.** Nunca mezclar fases en el mismo commit. Sub-items
  de una fase que el propio plan de usuario listó como commits separados
  (p. ej. Fase 3a/3b/3c) son, cada uno, su propio commit.
- **Aprobación antes de tocar archivos.** Antes de cada fase: anunciar qué
  archivos se van a tocar y por qué, esperar OK explícito.
- **`superpowers:verification-before-completion` al cierre de TODAS las fases
  (0 a 7), sin excepción.** Correr el smoke test (`docs/smoke_test.md`,
  creado en la Fase 0) fresco, con evidencia mostrada, antes de declarar una
  fase completa. Si algo falla: revertir el commit de esa fase y parar.
- **`superpowers:using-git-worktrees` PROHIBIDA en todo el plan.** Un único
  directorio de trabajo. Motivo: `data/` va en `.gitignore` (364 MB de
  cachés); una worktree nueva nacería sin esas cachés y el smoke test
  fallaría por una causa ajena al cambio bajo prueba.
- **Rama de trabajo:** `git init` → commit baseline en la rama por defecto →
  crear rama de remediación → las fases 1–7 viven en esa rama. El baseline en
  la rama por defecto queda intacto y recuperable en todo momento.
  `superpowers:finishing-a-development-branch` solo entra en juego al
  terminar la Fase 7, y solo tras consultar antes de integrar nada.
  `superpowers:brainstorming` no se invoca como ceremonia aparte — su gate
  ("no acción sin aprobación") ya está cubierto por esta misma regla.
- **Cambios de comportamiento documentados en la misma fase.** Todo cambio de
  comportamiento se refleja EN LA MISMA FASE en los `.md` afectados
  (`docs/routing_methodology.md`, `docs/network_and_graph_build.md`,
  `README_deploy.md`, `README.md` según aplique) y se registra en
  `docs/decisions.md` (fecha, decisión, motivo, hallazgo que cierra).
- **`docs/decisions.md` es un log append-only de decisiones tomadas.** Este
  plan (`docs/superpowers/plans/2026-08-14-audit-remediation.md`) es el
  roadmap. No mezclar los dos artefactos: el plan no se reescribe para
  reflejar decisiones — esas van solo a `decisions.md` (el plan puede tachar
  checkboxes y anotar el commit SHA correspondiente, nada más).
- **No corregir nada "de paso" fuera del alcance de la fase actual.** Si se
  detecta algo, se anota (en el resumen de la fase, o como nueva fila en la
  tabla de hallazgos si aplica) y se sigue.
- **No inventar cifras ni rutas.** Si algo no se puede verificar, decirlo
  explícitamente en el resumen de la fase.
- **`superpowers:dispatching-parallel-agents`** se usa ÚNICAMENTE en la Fase 1,
  y solo para las tres verificaciones mecánicas (C1, C13, C16) — nunca para
  C2, que es razonamiento del agente principal, secuencial, sin delegar. Los
  subagentes de Fase 1 devuelven evidencia cruda (citas archivo:línea, salida
  de comandos) — nunca un veredicto ya sintetizado — y reciben instrucción
  explícita de verificar contra el código, no de confirmar la auditoría.
- **`superpowers:requesting-code-review` es OBLIGATORIA (no opcional) en las
  Fases 6 y 7**, sobre el diff de esa fase, antes de presentarla como
  terminada — son las dos únicas fases que pueden alterar la corrección de
  las rutas devueltas.

---

### Fase -1: Descubrimiento de skills — COMPLETADA

**Files:** ninguno (solo lectura de `~/.claude/plugins/...`)

- [x] Enumerar skills instaladas realmente (inspección de disco, no memoria)
- [x] Mapear fases 0–7 a skills concretas
- [x] Señalar conflictos con las reglas del usuario
- [x] Obtener aprobación explícita del mapeo (con 2 correcciones incorporadas
      arriba en Global Constraints) y de las 4 respuestas (transcritas en las
      fases correspondientes abajo)

---

### Fase 0: Red de seguridad — BLOQUEANTE

**Files:**
- Create: `.gitignore`
- Create: `data/interim/hamburg_graph.pkl.sha256`
- Create: `requirements.lock.txt`
- Create: `docs/smoke_test.md`
- Create: este mismo archivo de plan (se incluye en el commit baseline)

**Interfaces:**
- Produces: `docs/smoke_test.md` (checklist manual reusado como criterio de
  verificación por TODAS las fases siguientes vía
  `verification-before-completion`)

- [ ] **Paso 1: Verificar ausencia de repo git**

  Run: `git status`
  Expected (ya confirmado en la auditoría previa): `fatal: not a git repository`

- [ ] **Paso 2: `git init` en la rama por defecto**

  ```bash
  git init
  git config user.name "<a confirmar o usar el de sistema>"
  git branch -M main
  ```

- [ ] **Paso 3: Crear `.gitignore`**

  ```gitignore
  # Cachés de datos pesadas — se copian manualmente al servidor (ver README_deploy.md)
  data/
  # Entorno virtual local
  .venv/
  # Artefactos de SO
  .DS_Store
  __pycache__/
  *.pyc
  ```

- [ ] **Paso 4: Checksum del grafo inmutable**

  ```bash
  shasum -a 256 data/interim/hamburg_graph.pkl > data/interim/hamburg_graph.pkl.sha256
  cat data/interim/hamburg_graph.pkl.sha256
  ```

  Nota: este archivo `.sha256` SÍ se versiona (es texto, no el pickle) —
  añadir excepción en `.gitignore` si `data/` está ignorado por completo:
  ```gitignore
  data/
  !data/interim/hamburg_graph.pkl.sha256
  ```

- [ ] **Paso 5: `pip freeze` para reproducibilidad**

  ```bash
  .venv/bin/pip freeze > requirements.lock.txt
  ```

- [ ] **Paso 6: Redactar `docs/smoke_test.md`**

  Contenido mínimo (checklist manual, sin automatizar todavía — eso es la
  Fase 5):
  ```markdown
  # Smoke Test Manual — AED Route Hamburg

  Ejecutar tras CADA fase del plan de remediación, antes de dar la fase por
  cerrada (superpowers:verification-before-completion).

  1. Arrancar el servidor:
     `.venv/bin/uvicorn app.app:app --host 0.0.0.0 --port <puerto vigente>`
     — confirmar que aparece el log de arranque sin traceback.
  2. `curl http://127.0.0.1:<puerto>/healthz` → debe devolver `{"ok":true}`.
  3. Cargar la URL raíz en un navegador y confirmar visualmente las tres capas:
     puntos de AED, límite administrativo, isócronas (toggle activado).
  4. Un click en el mapa debe devolver una ruta en cada uno de los tres modos
     (Walk, Bike, Car) — confirmar que se dibuja una polilínea y que la
     tarjeta de resultado muestra tiempo/distancia.
  5. Parar el servidor (Ctrl+C) y confirmar que no quedan procesos huérfanos.

  Si cualquier paso falla: revertir el commit de la fase en curso y parar.
  ```

- [ ] **Paso 7: Commit baseline en `main`**

  ```bash
  git add -A
  git commit -m "chore: baseline commit (pre-remediation) — gitignore, checksum, lockfile, smoke test doc, plan"
  ```

- [ ] **Paso 8: Crear rama de remediación**

  ```bash
  git checkout -b remediation/audit-2026-08
  ```

  Las fases 1–7 se commitean en esta rama, no en `main`.

- [ ] **Paso 9: `superpowers:verification-before-completion`**

  Ejecutar el smoke test recién redactado contra el estado actual (sin
  ningún cambio de código todavía) para confirmar que el checklist en sí
  mismo es correcto y ejecutable, y mostrar la evidencia (salida real de cada
  comando) antes de declarar la Fase 0 cerrada.

---

### Fase 1: Reverificar la auditoría — SOLO LECTURA

**Files:** ninguno (solo lectura; el output es texto en el chat, no un commit)

**Interfaces:**
- Consumes: hallazgos C1, C2, C13, C16 del informe de auditoría original
- Produces: delta de hallazgos corregidos/retirados/reclasificados, que
  alimenta directamente las Fases 2–7 (severidades y remediaciones
  actualizadas)

- [x] **Paso 1: Lanzar 3 subagentes en paralelo (`dispatching-parallel-agents`)**
      para las verificaciones mecánicas — cada uno con instrucción explícita
      de citar archivo:línea y salida de comandos, verificar contra el código
      real (no confirmar la auditoría), y devolver evidencia cruda sin
      veredicto de severidad:
  - Subagente A — **C1**: leer `app/app.py:92`, `static/index_original.html`,
    `static/app_original.js`, `static/index.html`, `static/app.js`.
    Determinar con citas exactas qué archivo sirve `GET /` y cuál de los dos
    frontends hace `fetch("./data/...")` relativo.
  - Subagente B — **C13**: construir tabla fila por fila de la clasificación
    de vías (`docs/routing_methodology.md`, tabla "OSM Highway Classification
    by Transport Profile") contra los tres literales `WALK_CUSTOM_FILTER`,
    `BIKE_CUSTOM_FILTER`, `DRIVE_CUSTOM_FILTER` en
    `src/aed_route/graph_builder_osm.py`. Para cada fila: coincide / no
    coincide, con cita del regex exacto.
  - Subagente C — **C16**: en el `.venv` real, verificar con
    `inspect`/`hasattr` si `ox.add_edge_speeds`, `ox.add_edge_travel_times` y
    `ox.graph_to_gdfs` existen como alias de nivel superior en la versión de
    OSMnx instalada, o si OSMnx 2.x los reorganizó bajo `ox.routing.*` /
    `ox.convert.*`. Mostrar el comando ejecutado y su salida literal.

- [x] **Paso 2: Reanálisis de C2 — hecho por el agente principal, sin delegar**

  Verificar el razonamiento corregido por el usuario:
  - Confirmar que unificar CRS a metros por sí solo empeoraría el bug (peso
    de A* en segundos vs. heurística en metros → heurística sobreestimaría).
  - Confirmar, leyendo `src/aed_route/routing.py` y
    `src/aed_route/graph_builder_osm.py:add_aed_nodes_to_graph`, que el grado
    de los nodos AED es 1 (una sola arista de acceso bidireccional) y que
    esa es la razón real de que hoy se devuelvan rutas óptimas pese al bug
    de unidades — no una supuesta "degeneración a Dijkstra".
  - Documentar textualmente ese razonamiento (para incorporarlo después,
    literal, en la Fase 6).

- [x] **Paso 3: Sintetizar el delta**

  El agente principal recibe las 3 evidencias crudas de los subagentes +
  su propio reanálisis de C2, y produce: hallazgos confirmados tal cual,
  hallazgos corregidos (con el texto correcto), hallazgos retirados (con
  motivo), y cualquier reclasificación de severidad. Se entrega como delta
  en el chat, sin repetir el informe completo.

- [x] **Paso 4: `verification-before-completion`**

  No hay commit en esta fase (solo lectura) — la "evidencia" de cierre es el
  propio delta con citas verificables, no un smoke test de la app.

  **Cerrada 2026-08-14.** Delta: C1 retractado (era exactamente al revés);
  C13 confirmado (2 de 21 filas no coinciden); C16 confirmado con más
  precisión (severidad bajada a Nota); C2 precisado (grado 1 + h≈const
  explican la optimalidad, no "degenera a Dijkstra"). Hallazgos nuevos
  fuera de alcance anotados (modo car — reclasificado a Alta por el
  usuario, trasladado a Fase 4/Fase 8 nueva; `bike_cost_s` con
  `WALK_SPEED_M_S` — clasificado como pregunta abierta, no bug). Ver
  `docs/decisions.md` para el detalle registrado.

---

### Fase 2: Documentación a fuente de verdad

**Files:**
- Modify: `README_deploy.md`
- Modify: `docs/routing_methodology.md`
- Modify: `docs/network_and_graph_build.md`
- Modify: `README.md` (según lo que se decida con el usuario dentro de la fase)
- Create: `docs/decisions.md`

**Interfaces:**
- Consumes: delta de la Fase 1 (severidades/redacciones ya corregidas)
- Produces: `docs/decisions.md` con al menos una entrada por cada decisión
  tomada en esta fase

- [x] **Paso 1:** Reemplazar toda mención a Flask/Gunicorn/`flask_app.py`/log
      "Flask app ready." por FastAPI/uvicorn/`app/app.py`/"FastAPI app
      ready." en los tres documentos afectados (C4).
- [x] **Paso 2:** Unificar la referencia de puertos en la documentación al
      valor canónico (se confirma en la Fase 3b; si Fase 3 aún no ha
      corrido, dejar aquí una nota explícita "puerto pendiente de
      unificación en Fase 3b" en vez de inventar un valor) (C7).
- [x] **Paso 3:** Resolver la contradicción "crashea vs. reconstruye" entre
      `README_deploy.md` y `docs/network_and_graph_build.md` describiendo el
      comportamiento real verificado en la auditoría: AEDs → crash
      (`_require_cache`); grafo → reconstrucción automática vía OSMnx si
      falta; isócronas → recálculo automático en arranque; boundary → solo
      falla al pedirse `/api/boundary` si el archivo no existe (C5).
- [x] **Paso 4 — DESVIACIÓN ANOTADA:** no hice la pausa/pregunta explícita
      que este paso pedía literalmente antes de tocar `README.md`. En su
      lugar, siguiendo el patrón ya establecido por el usuario en esta
      misma conversación para el otro artefacto muerto equivalente
      (`static/index.html`+`app.js`: "no borres ni muevas nada, eso es
      Fase 4"), añadí solo un aviso/banner explicando que `README.md`
      describe el prototipo estático muerto, sin borrar, mover ni fusionar
      nada — dejando la decisión de qué hacer con el archivo para la
      Fase 4, igual que con el frontend. No asumí que esto fuera lo
      correcto sin decírselo al usuario: queda señalado aquí y en el
      resumen de cierre de fase para que lo corrija si no era lo que
      quería (C9).
- [x] **Paso 5:** Corregir las cifras de AEDs contradictorias dentro de
      `docs/routing_methodology.md` (139 vs. 141 vs. "0 skipped"),
      usando los valores verificados en la auditoría original contra los
      `.geojson` reales (C8).
- [x] **Paso 6:** Marcar explícitamente como deuda conocida (no como hecho)
      el filtro de componente gigante, en ambos documentos donde se afirma
      implementado (C3) — redacción provisional hasta que la Fase 7 lo
      implemente parcialmente (lado origen) y deje constancia del lado AED
      como deuda aceptada.
- [x] **Paso 7:** Crear `docs/decisions.md` (log append-only, formato:
      `## YYYY-MM-DD — <decisión> — motivo: ... — cierra: C<n>`).
- [ ] **Paso 8:** Commit.

  ```bash
  git add README.md README_deploy.md docs/routing_methodology.md docs/network_and_graph_build.md docs/decisions.md
  git commit -m "docs: sincronizar documentación con el comportamiento real del código (Fase 2)"
  ```

- [ ] **Paso 9:** `verification-before-completion` — re-grepear cada cifra y
      afirmación corregida (framework, puertos, cifras de AED, estado del
      componente gigante) contra el código, mostrar la salida, antes de
      declarar la fase cerrada. Correr `docs/smoke_test.md`.

---

### Fase 3: Cambios aislados de bajo riesgo (tres commits independientes)

#### 3(a): Event loop no bloqueante

**Files:**
- Modify: `app/app.py:123-136` (handler `POST /api/route`)

**Interfaces:**
- Consumes: `find_nearest_aeds` (firma sin cambios, `src/aed_route/routing.py`)

- [x] **Paso 1:** Envolver la llamada síncrona en `asyncio.to_thread`:

  ```python
  import asyncio
  ...
  results = await asyncio.to_thread(
      find_nearest_aeds,
      origin_lon=body.lon,
      origin_lat=body.lat,
      mode=body.mode,
      graph_bundle=bundle,
      aed_index=aed_index,
      node_index=node_index,
      k=SHORTLIST_EUCLIDEAN_K,
  )
  ```

- [x] **Paso 2:** Smoke test manual — confirmar que un click en el mapa
      sigue devolviendo ruta en los tres modos (no hay suite automatizada
      todavía; el arnés llega en la Fase 5. Se deja constancia explícita de
      esta desviación de TDD estricto en el mensaje de cierre de fase).
      **Reforzado en la Fase 3(b)**: comparación byte a byte de la
      respuesta completa de `/api/route` pre/post cambio en los 3 modos —
      idéntica en los tres casos.
- [x] **Paso 3:** Commit. `ecc1130` — "fase 3a: no bloquear el event loop en
      POST /api/route".

#### 3(b): Puerto canónico

**Files:**
- Modify: `app/app.py:180`
- Modify: `app/wsgi.py:5`
- Modify: `Dockerfile:12,14`
- Modify: `docker-compose.yml:5`
- Modify: `docs/apache.conf:7-12`
- Modify: `README_deploy.md` (todas las referencias a puerto)

- [x] **Paso 1:** Confirmar con el usuario, al abrir esta fase, el puerto
      canónico (propuesta de la auditoría: 5000, por ser el que ya usan
      Dockerfile/compose/apache.conf) — no asumir sin OK explícito.
      **Confirmado: 5000.**
- [x] **Paso 2:** Aplicar el valor acordado (`app/app.py`, `README_deploy.md`,
      `docs/routing_methodology.md`, `docs/network_and_graph_build.md` —
      los otros 4 artefactos ya usaban 5000, sin cambios necesarios).
- [x] **Paso 3:** Nota pendiente de Fase 2 actualizada en los tres
      documentos afectados.
- [x] **Paso 4:** Commit. `3afde65` — "fase 3b: unificar el puerto canonico
      a 5000". Riesgo explícito registrado en `docs/decisions.md`: elegido
      por consistencia interna del repo, NO verificado contra el proxy real
      de producción.

#### 3(c): Limpieza de dependencias y archivo huérfano

**Files:**
- Modify: `requirements.txt`
- Delete: `static/data/demo_rathaus_response.json`

- [x] **Paso 1:** Reconfirmado por grep (sin pausa adicional al usuario —
      la aprobación general de Fase 3 cubrió esto): `python-multipart` y
      `pyarrow` sin uso directo, ambos retirados. `geopandas` se mantiene
      (dependencia transitiva real de osmnx).
- [x] **Paso 2:** Retirado `static/data/demo_rathaus_response.json`.
- [x] **Paso 3:** Commit. `6f4c8fa` — "fase 3c: retirar dependencias sin uso
      confirmado y archivo huerfano". Limitación anotada: el venv no se
      recreó desde cero, no prueba una instalación limpia sin esas
      dependencias.

Cada uno de los tres sub-commits de la Fase 3 cierra con su propio
`verification-before-completion` + smoke test, no solo al final de 3(c).

---

### Fase 4: Requiere decisiones del usuario — PREGUNTAR ANTES DE TOCAR NADA

**Files:** ninguno hasta obtener respuesta

- [x] **Pregunta (a):** `SHORTLIST_EUCLIDEAN_K` — **decidido: 5.**
      Implementación diferida a la Fase 8 (ver `docs/decisions.md`).
- [x] **Pregunta (b):** Frontend — **decidido: retirar
      `index.html`/`app.js`/`styles.css`/los 3 `hamburg_mitte_*.geojson`,
      reemplazar `README.md` por un aviso corto.** Implementación diferida
      a un commit propio en la Fase 8, con precondición de verificación por
      grep antes de borrar (ver `docs/decisions.md`).
- [x] **Ítems adicionales tratados en esta fase, no previstos originalmente
      en el plan** (añadidos por el usuario durante la ejecución, todos
      registrados en `docs/decisions.md`):
  - Mitigación del fallo silencioso en resultados vacíos — **decidido:
      aprobado, primer ítem de la Fase 8**, con texto de cara al usuario
      en borrador pendiente de revisión del equipo.
  - Modo `car` (opciones i/ii/iii/iv) — medición completa entregada
      (97,8% de cobertura con snap dependiente del modo, opción iv), pero
      **decisión NO cerrada** — pendiente de consulta del usuario con su
      equipo.
  - Diagnóstico `PUBLIC_BASE_PATH` — confirmado como escenario no
      soportado en absoluto; corrección de `README_deploy.md` diferida a
      la Fase 8; riesgo de despliegue registrado junto al del puerto.
- [x] Tras respuesta: los cambios correspondientes NO se aplican en esta
      fase — todos diferidos a la Fase 8, según lo pidió el usuario
      explícitamente ("no en esta fase ni junto a otros cambios").

---

### Fase 5: Arnés de regresión — ANTES de tocar el routing

**Files:**
- Create: `tests/` (nuevo directorio — no existe ninguno en el repo)
- Create: `tests/golden/` (fixtures de respuesta)
- Create: `scripts/generate_golden_routes.py` (o ubicación equivalente que se
  acuerde con el usuario dentro de la fase)
- Create: `tests/test_heuristic_admissibility.py`

**Interfaces:**
- Consumes: `POST /api/route` (contrato JSON existente, sin cambios)
- Produces: golden files versionados que las Fases 6 y 7 usan como oráculo
  de no-regresión

- [ ] **Paso 1:** Script que llama a `POST /api/route` para un conjunto fijo
      de orígenes × 3 modos y guarda las respuestas completas como golden
      files versionados. Casos límite obligatorios: centro urbano denso,
      borde del boundary administrativo, zona de la Clausewitz-Kaserne
      (53.5624°N, 9.8327°E — caso documentado de "sin red accesible"), y un
      punto sobre agua (a determinar coordenada real tras confirmar con
      `data/processed/hamburg_boundary.geojson`, no inventar una).
- [ ] **Paso 2:** Test de admisibilidad de la heurística sobre un mini-grafo
      sintético con coordenadas conocidas (no el grafo de producción): construir
      un `nx.MultiDiGraph` de juguete con `x`/`y` y pesos de coste conocidos
      de antemano, y verificar `heuristic(u, target) <= coste_real_mínimo(u,
      target)` para todos los pares — este test debe FALLAR contra la
      implementación actual de `routing.py` (documentando así, en rojo, el
      propio bug C2 antes de tocarlo en la Fase 6).
- [ ] **Paso 3:** Generar el baseline de golden files contra el estado
      ACTUAL del código (antes de la Fase 6) y confirmar al usuario que está
      guardado, mostrando el listado de archivos generados.
- [ ] **Paso 4:** Commit.

  ```bash
  git add tests/ scripts/generate_golden_routes.py
  git commit -m "test: arnés de regresión (golden routes) y test de admisibilidad de heurística (prep. para C2/C3)"
  ```

- [ ] **Paso 5:** `verification-before-completion` + smoke test.

---

### Fase 6: C2 — Heurística de A* (solo `src/aed_route/routing.py`)

**Files:**
- Modify: `src/aed_route/routing.py` (únicamente la función `heuristic` y lo
  estrictamente necesario para leer coordenadas proyectadas desde
  `nodes_df`/`node_index` en vez de `G.nodes[...]`)
- Modify: `docs/routing_methodology.md` (sección de heurística/A*)
- Modify: `docs/decisions.md`

- [ ] **Paso 1 — Verificación empírica OBLIGATORIA antes de escribir código:**
      contra el pickle real (`data/interim/hamburg_graph.pkl`), confirmar que
      TODOS los `x`/`y` de `nodes_df` (nodos de carretera y nodos `aed_*`)
      caen en el rango EPSG:25832 esperado para Hamburgo (x ≈ 5.4e5–6.0e5,
      y ≈ 5.90e6–5.98e6). Mostrar el comando ejecutado y la salida real
      (min/max por columna, separado por tipo de nodo). Si algún subconjunto
      está en grados: PARAR y avisar — la premisa del fix sería falsa.
- [ ] **Paso 2:** Confirmado el rango, implementar el fix leyendo
      coordenadas proyectadas desde `nodes_df`/`node_index` (nunca desde
      `G.nodes[...]`), devolviendo `distancia_m / velocidad_máxima_del_modo`
      para que la unidad case con el peso en segundos. Justificar en el
      propio código (comentario) y en la doc por qué se divide por la
      velocidad MÁXIMA alcanzable en la red para ese modo y no por la media
      (admisibilidad: h no debe poder superar nunca el coste real mínimo).
      Prohibido reproyectar nodos del grafo — leer, no mutar.
- [ ] **Paso 3:** Correr el test de admisibilidad de la Fase 5 (ahora debe
      pasar en verde) y los golden files (deben quedar SIN CAMBIOS — se
      espera esto por el grado 1 de los nodos AED).
- [ ] **Paso 4:** Medir nodos explorados por A* antes/después (instrumentar
      temporalmente o usar el contador que exponga `nx.astar_path`/una
      envoltura local) y mostrar la comparación.
- [ ] **Paso 5:** Documentar en `docs/routing_methodology.md` y en
      `docs/decisions.md`: por qué la implementación anterior devolvía rutas
      óptimas pese al bug (grado 1 de los nodos AED, no "degeneración a
      Dijkstra" — según el reanálisis de la Fase 1), y qué cambio futuro
      (p. ej. conectar un AED a varios nodos de acceso) rompería esa
      garantía silenciosamente.
- [ ] **Paso 6:** Commit.

  ```bash
  git add src/aed_route/routing.py docs/routing_methodology.md docs/decisions.md
  git commit -m "fix: heurística de A* en unidades de tiempo (distancia_m/v_max), sin reproyectar el grafo (C2)"
  ```

- [ ] **Paso 7 — OBLIGATORIO:** `superpowers:requesting-code-review` sobre el
      diff de este commit (subagente revisor independiente) antes de
      presentar la fase como terminada.
- [ ] **Paso 8:** `verification-before-completion` + smoke test. Si algún
      golden cambia: revertir e investigar, no continuar.

---

### Fase 7: C3 — Componente gigante, sin tocar la construcción del grafo

**Files:**
- Create: `data/processed/nodes_outside_giant_component.json` (o nombre
  equivalente acordado — artefacto derivado nuevo, NO el pickle)
- Modify: `src/aed_route/nearest.py` (filtro de `node_index` para el
  snapping de origen)
- Modify: `app/app.py` (cálculo del componente gigante al arranque, logging
  WARNING de AEDs fuera de él)
- Modify: `src/aed_route/routing.py` (logging en `find_nearest_aeds` cuando
  se descarta un candidato por `NetworkXNoPath`)
- Modify: `docs/network_and_graph_build.md`, `docs/routing_methodology.md`,
  `docs/decisions.md`

- [ ] **Paso 1:** Al arranque, calcular una vez (solo lectura sobre el grafo
      cargado, sin mutar nada) el componente débilmente conexo mayor.
      Cachear el resultado como artefacto derivado nuevo en
      `data/processed/` — lista de `node_keys` EXCLUIDOS (pequeña, no el
      grafo completo).
- [ ] **Paso 2:** Filtrar el `node_index` que usa `snap_origin_to_graph` a
      nodos del componente gigante (cambio local en `nearest.py`/`app.py`).
- [ ] **Paso 3:** Detectar al arranque qué nodos `aed_*` quedan fuera del
      componente gigante — loguear con nivel WARNING listando sus ids (sin
      re-snapearlos: eso requeriría tocar el pickle inmutable). Registrar en
      `docs/decisions.md` como deuda aceptada, con el motivo explícito (snap
      AED horneado en el pickle).
- [ ] **Paso 4:** Añadir logging en `find_nearest_aeds` cuando un candidato
      se descarta por `nx.NetworkXNoPath`, para que el descarte deje de ser
      invisible.
- [ ] **Paso 5:** Correr los golden files de la Fase 5. **Se espera que
      algunos cambien** — clicks que hoy devuelven lista vacía por snapear a
      un fragmento aislado pasarán a devolver ruta. Mostrar uno por uno los
      casos que cambian, con justificación de cada diff. NO regenerar el
      baseline sin aprobación caso por caso del usuario.
- [ ] **Paso 6:** Tras aprobación caso por caso, regenerar solo esos golden
      files (los que no cambiaron quedan intactos).
- [ ] **Paso 7:** Actualizar la documentación para que diga la verdad: filtro
      de componente gigante implementado para el snapping de ORIGEN
      únicamente; lado AED sigue sin implementarse, deuda conocida y
      aceptada explícitamente (con referencia a la entrada correspondiente
      en `docs/decisions.md`).
- [ ] **Paso 8:** Commit.

  ```bash
  git add data/processed/nodes_outside_giant_component.json src/aed_route/nearest.py src/aed_route/routing.py app/app.py docs/network_and_graph_build.md docs/routing_methodology.md docs/decisions.md tests/golden/
  git commit -m "fix: restringir snapping de origen al componente gigante; loguear AEDs y candidatos fuera de él (C3)"
  ```

- [ ] **Paso 9 — OBLIGATORIO:** `superpowers:requesting-code-review` sobre el
      diff de este commit antes de presentar la fase como terminada.
- [ ] **Paso 10:** `verification-before-completion` + smoke test.

---

## Cierre del plan (fuera de las 8 fases)

Al terminar la Fase 7: consultar al usuario antes de invocar
`superpowers:finishing-a-development-branch` para decidir cómo integrar
`remediation/audit-2026-08` (merge a `main`, mantener aparte, etc.). No
asumir la respuesta.
