# Indoor Navigation — Hamburg Hauptbahnhof (Fase 3, paso 1)

## Estado

Este documento describe el primer paso de implementacion del grafo indoor:
parseo de niveles y construccion de un grafo independiente para Hbf. **No
hay routing ni integracion con el grafo base todavia** — eso es el paso 2.

Todo el codigo vive en `src/aed_route/indoor.py`, un modulo nuevo y aislado.
No se modifico `graph_builder_osm.py`, `routing.py`, `nearest.py` ni `app.py`.
La unica modificacion a un archivo existente fue anadir una seccion nueva al
final de `config.py` (ver mas abajo) — nada de lo previo se toco.

## Fuente de datos

El grafo se construye a partir de `data/interim/hbf_indoor_isolated.json`,
producido en fases anteriores de investigacion (solo lectura, sin codigo de
produccion):

1. **Fase 2b** — extraccion por semantica: `nwr["level"]` sobre el area
   administrativa de Hamburg-Mitte (relation 28971), con recursion de nodos
   referenciados. Guardado en `data/interim/mitte_level_elements.json`.
2. **Fase 2c** — aislamiento de Hbf: filtrado espacial de ese archivo por un
   bbox amplio (sur=53.5505, oeste=10.0025, norte=53.5560, este=10.0110) que
   cubre superficie y el subsuelo de U-Bahn/S-Bahn bajo Kirchenallee y
   Monckebergstrasse. Verificado que no se cuela ningun edificio ajeno
   (los "vecinos" detectados automaticamente — nodos "ZOB" y "Schauspielhaus"
   — resultaron ser entradas de metro del propio Hbf, nombradas por el punto
   de referencia en superficie, no edificios distintos).

Este paso (Fase 3) NO vuelve a tocar la red — lee `hbf_indoor_isolated.json`
tal cual quedo.

## Esquema de claves de nodo

- **Nodos de via indoor:** `in_{osmid}_L{nivel:g}` — el id de nodo OSM
  combinado con el nivel (formato `:g`, sin ceros decimales sobrantes:
  `in_315308772_L0`, `in_28686946_L-1`, `in_4059555116_L0.5`). Un mismo
  `osmid` presente en varios niveles genera un nodo por nivel — son copias
  independientes en el grafo, sin arista automatica entre ellas salvo que
  exista un conector vertical real que las una.
- **El DEA:** `aed_{id}` (`aed_13948102741`), reutilizando la convencion ya
  existente en `graph_builder_osm.py` para el grafo base, aunque este es un
  grafo completamente separado.

## Parser de niveles (`parse_level`)

Funcion pura en `indoor.py`. Nunca lanza excepcion: cualquier valor no
parseable se registra con `logger.warning` y contribuye `[]` (se ignora, no
rompe la construccion del grafo).

Casos manejados:
- Enteros: `"0"` -> `[0.0]`
- Listas `;`: `"-1;0"` -> `[-1.0, 0.0]`
- Decimales: `"-0.5"` -> `[-0.5]` (confirmado en datos reales de Mitte/Hbf)
- Rangos `-`: `"0-2"` -> `[0.0, 1.0, 2.0]` (robustez — no aparecio en Hbf,
  pero si es un patron OSM valido en general)

El orden de comprobacion (entero/decimal ANTES que rango) es lo que
distingue el signo negativo del separador de rango: `"-1"` se reconoce como
entero antes de intentar interpretarlo como rango, y `"-3--1"` (rango de
`-3` a `-1`) solo se prueba como rango despues de fallar como entero/decimal
simple.

**El tag `layer` se ignora deliberadamente** en todo el modulo — es un
concepto OSM distinto (orden de renderizado/apilamiento), no una planta
fisica. Ya se habia confirmado en fases anteriores que `layer` y `level`
pueden coexistir con valores distintos en el mismo elemento (incluido el
propio DEA: `layer=1`, `level=0`).

## Modelo del grafo

`networkx.MultiGraph` — **NO dirigido**. El movimiento a pie indoor es
bidireccional por naturaleza, coherente con la filosofia de emergencia ya
aplicada al grafo base (las bicis ignoran `oneway` en exterior). Usar un
grafo realmente no dirigido evita el bug silencioso de aristas de un solo
sentido creadas por olvido. Es "Multi" porque puede haber varias vias
distintas entre el mismo par de nodos.

**Excepcion documentada (PROVISIONAL):** las escaleras mecanicas
(`conveying=forward/backward`) pueden tener sentido unico fisico. En este
MVP se tratan como bidireccionales igual que el resto — a revisar en una
fase posterior si se decide modelar direccionalidad real de conveyors.

### Aristas horizontales

De cada way `highway=footway`+`indoor=yes`, se crean aristas entre nodos
consecutivos de su lista de nodos, replicadas para cada nivel que el
`level` parseado indique (si el way tiene `level="-1;0"`, se crean dos
copias completas de sus segmentos, una en nivel -1 y otra en nivel 0 —
son "universos paralelos" sin conexion automatica entre si).

- `cost_s = longitud_m / WALK_SPEED_M_S` (misma velocidad de caminar del
  proyecto — no se crearon constantes de velocidad nuevas).
- Longitud calculada en EPSG:25832 (proyectada); geometria de la arista
  guardada en EPSG:4326, igual que el grafo base.
- `can_walk=True`, `can_bike=False`, `can_drive=False`.

`highway=corridor` como **linea** no aparecio en absoluto en el dataset de
Hbf (confirmado en la Fase 2a.2 y de nuevo aqui) — todos los `indoor=corridor`
son poligonos cerrados, tratados como shape (ver mas abajo), no como via.

### Aristas verticales

`highway=steps`, `highway=elevator` (nodo o way) y `conveying` (way) con
`level` conteniendo 2+ valores distintos crean aristas entre los nodos
correspondientes de niveles consecutivos (ordenados). Por ejemplo, un
conector con `level="-1;0;1"` genera dos aristas: `-1<->0` y `0<->1` (no una
directa `-1<->1`).

El "ancla" de un conector vertical es cada uno de sus propios node ids
(el/los nodo(s) del elemento OSM, no un nodo sintetico nuevo). Esto es una
simplificacion documentada: en OSM, un way de escalera suele mapearse como
una linea 2D corta en la misma posicion fisica para ambos niveles (no hay
coordenada Z real), asi que reutilizar sus propios node ids para generar
las copias por nivel es razonable, pero significa que la arista vertical
solo "engancha" con la red horizontal si ese mismo node id coincide con un
nodo de un footway en el nivel correspondiente — **la mayoria de las veces
no coincide** (ver limitaciones).

Costes (constantes nuevas en `config.py`, seccion "Indoor navigation —
PROVISIONAL"):
- Escaleras: `STAIR_SECONDS_PER_LEVEL * plantas_salvadas`
- Mecanicas: `ESCALATOR_SECONDS_PER_LEVEL * plantas_salvadas`
- Ascensor: `ELEVATOR_WAIT_SECONDS + ELEVATOR_SECONDS_PER_LEVEL * plantas_salvadas`

`plantas_salvadas = abs(nivel_destino - nivel_origen)` (puede ser >1 si el
conector salta niveles, p. ej. `"-3;-1"` salvando 2 plantas de una vez).

**Todos estos valores de coste son PROVISIONALES** — un punto de partida
razonable, no calibrado con literatura cientifica sobre transito vertical
en estaciones o evacuacion de emergencia. Deben revisarse antes de usar el
grafo para cualquier decision operativa real.

### Salas (shape) — solo metadato

Poligonos `indoor=room`/`area`/`corridor` (ways) y relations multipolygon
`indoor=room`/`area` se reconstruyen como geometria shapely (con huecos
`inner` cuando aplica) y se guardan como una lista de `IndoorRoom` (id,
tipo OSM, nombre, niveles, poligono). **No son routeable en este paso** —
sirven para dibujar y para localizar visualmente donde cae el DEA, no para
buscar caminos dentro de ellas.

### Ruido conocido

`INDOOR_IGNORE_LEVELS = (5.0,)` — un unico elemento con `level=5` detectado
en fases anteriores de Hbf, sin verificar aun si es una antena/torre real o
un error de mapeo. Se filtra en todo el modulo (parser de niveles ya
excluye este valor de cualquier lista/rango que lo contenga).

## Verificacion (Fase 3, resumen real de la ejecucion)

Grafo resultante: **958 nodos, 802 aristas** totales.

| level | nodos | aristas horizontales |
|---|---|---|
| -3 | 46 | 4 |
| -2 | 125 | 52 |
| -1 | 402 | 216 |
| -0.5 | 5 | 2 |
| 0 | 326 | 146 |
| 1 | 53 | 30 |

Aristas verticales por tipo: `steps=259, elevator=93, conveying=0` (no
habia ningun `conveying` en el bbox aislado de Hbf).

### Componentes conexas por nivel — dos vistas

La verificacion pedia reproducir los numeros de la Fase 2c
(nivel 0 ~5 componentes/mayor 82, nivel -1 ~31 componentes/mayor 59).
Al construir tambien las aristas verticales, cada conector (steps/elevator)
anade nodos-ancla por nivel que **no siempre coinciden con un nodo de
footway en ese nivel** — esos nodos aparecen como componentes de tamano 1,
inflando el conteo total sin cambiar la componente mas grande. Por eso se
reportan dos vistas:

| level | footway-only: nodos/componentes/mayor | full (+anclas verticales): nodos/componentes/mayor |
|---|---|---|
| -3 | 5 / 1 / 5 | 46 / 42 / 5 |
| -2 | 60 / 8 / 19 | 125 / 73 / 19 |
| -1 | **245 / 31 / 59** | 402 / 188 / 59 |
| -0.5 | 3 / 1 / 3 | 5 / 3 / 3 |
| 0 | **147 / 5 / 82** | 326 / 184 / 82 |
| 1 | 31 / 3 / 21 | 53 / 25 / 21 |

La vista **footway-only reproduce EXACTAMENTE** los numeros de la Fase 2c
(nivel 0: 5 componentes/mayor 82; nivel -1: 31 componentes/mayor 59),
confirmando que el constructor de aristas horizontales es correcto. La
vista "full" revela un hallazgo real y no trivial: **179 de los 326 nodos
de nivel 0 (55%) y 157 de los 402 de nivel -1 (39%) son anclas de
conectores verticales que no comparten nodo con ningun footway en ese
nivel** — es decir, la mayoria de escaleras/ascensores en este dataset no
estan topologicamente "enganchados" a la red horizontal correspondiente en
ambos extremos. Esto no es un bug del constructor: es una propiedad real
del mapeo OSM de Hbf que cualquier fase de routing futura tendra que
resolver (p. ej. con snapping por proximidad en vez de solo por node id
compartido).

### DEA

Nodo `13948102741` -> `aed_13948102741`, level=0, presente en el grafo
como nodo aislado (sin aristas, como se pidio). El nodo routeable de nivel
0 mas cercano por coordenada es `in_315308772_L0`, a **8.98 m** — no se
crea la arista de enganche en este paso.

### Salas

168 poligonos cargados como metadato (91 con nombre, 168 con geometria
reconstruida exitosamente — 100%).

## Limitaciones conocidas

- **Nivel -1 fragmentado:** 31 componentes conexas reales (vista
  footway-only) para 245 nodos — el sotano principal de Hbf no es una red
  unica y conectada en los datos actuales.
- **`level=5` ignorado como ruido** — un unico elemento, sin verificar si
  es real (antena/torre) o error de mapeo.
- **Salas aun no routeables** — `indoor=room/area/corridor` son solo
  metadato geometrico en este paso.
- **Grafo NO dirigido** — simplificacion deliberada, coherente con el resto
  del proyecto.
- **Escaleras mecanicas tratadas como bidireccionales** aunque
  `conveying=forward/backward` pueda indicar sentido unico real — no
  aplica en este dataset especifico (0 conveyors en el bbox de Hbf), pero
  queda documentado para cuando aparezcan en otros edificios.
- **Conectores verticales mayormente desenganchados de la red horizontal**
  en al menos uno de sus extremos (ver tabla de componentes arriba) — el
  enganche steps/elevator <-> footway por proximidad (no solo por node id
  compartido) es trabajo pendiente para la fase de routing.
- **Costes de transito vertical PROVISIONALES**, sin calibrar con
  literatura cientifica.
- **Grafo completamente aislado del grafo base** (`hamburg_graph.pkl`) —
  no hay arista de enganche indoor<->outdoor todavia; ese es el objetivo
  explicito del proximo paso, no de este.
