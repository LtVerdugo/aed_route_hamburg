# Aislamiento de Hbf desde Mitte + verificacion del recorte (Fase 2c)

Fuente: `data/interim/mitte_level_elements.json` — 15124 nodes, 3520 ways, 34 relations totales en Mitte.

## Parte A — Recorte espacial

Bbox: sur=53.5505, oeste=10.0025, norte=53.556, este=10.011

- Nodes dentro del bbox: **3385** de 15124
- Ways dentro del bbox (por centroide): **794** de 3520
- Relations dentro del bbox (por centroide de miembros): **7** de 34

## Parte B.1 — Edificios dentro del bbox

### Top nombres (`name`) dentro del bbox (149 distintos)

`Hamburg Hauptbahnhof`=28, `Lübeck-Hamburger Bahn`=17, `Berlin-Hamburger Bahn`=14, `Hauptbahnhof Nord`=12, `Verbindungsbahn`=10, `Hauptbahnhof Süd`=8, `City-S-Bahn`=7, `Wallringtunnel`=5, `Hamburg Hbf`=5, `von Allwörden`=4, `Mö-Passage`=3, `Le Crobag`=3, `McDonald's`=2, `Nur Hier`=2, `Adenauerallee`=2, `KFC`=2, `Asiahung`=2, `Punto Ernesto`=2, `Ditsch`=2, `Dunkin'`=2, `Tunnel Döner`=2, `Starbucks`=2, `Relay`=2, `U-Store`=2, `small talk`=2, `HVV-Servicestelle`=2, `Hochbahnwache`=2, `Backwerk`=2, `Rail & Fresh`=2, `Nordsteg`=2

### Top operadores (`operator`) dentro del bbox (39 distintos)

`Hamburger Hochbahn AG`=66, `DB Netz AG`=47, `DB InfraGO AG`=46, `S-Bahn Hamburg GmbH`=40, `DB Vertrieb GmbH`=26, `DB Station&Service AG`=26, `Reisebank`=7, `Hamburger Verkehrsverbund`=4, `Geile Warenautomaten GmbH`=4, `ME Group Germany GmbH`=3, `metronom`=3, `DB`=3, `HOCHBAHN`=2, `Deutsche Post`=2, `Hering Sanikonzept GmbH`=2, `Deutsche Bahn Connect GmbH`=1, `Hamburger Volksbank eG`=1, `Hamburger Volksbank`=1, `Hamburger Sparkasse`=1, `Diana Fronecke-Dreyer`=1

### Chequeo de vecinos ajenos conocidos (Kunsthalle, ZOB, MediaMarkt, etc.)

**Se colaron elementos de edificios vecinos:**

| name | tipo | id | lat | lon | keyword |
|---|---|---|---|---|---|
| ZOB | node | 480372897 | 53.552068 | 10.010535 | zob |
| Schauspielhaus | node | 311930237 | 53.5543073 | 10.0083986 | schauspielhaus |

Nombres relacionados directamente con Hbf/anden/via en el top 15: ['Hamburg Hauptbahnhof', 'Hauptbahnhof Nord', 'Hauptbahnhof Süd', 'Hamburg Hbf']

## Parte B.2 — Dispersion por nivel

Elementos con `level` dentro del bbox: **1531**

| level | # elementos |
|---|---|
| -3 | 23 |
| -3;-1 | 2 |
| -3;0 | 2 |
| -3;-2 | 9 |
| -2 | 90 |
| -2;0 | 2 |
| -2;-1 | 22 |
| -2;-3 | 4 |
| -1 | 741 |
| -1;0 | 68 |
| -1;-2 | 19 |
| -1;-3 | 1 |
| -1;-0.5 | 2 |
| -1;0;1 | 1 |
| -0.5 | 2 |
| -0.5;0 | 1 |
| 0 | 440 |
| 0;1 | 15 |
| 0;-1 | 23 |
| 0;-1;-2 | 2 |
| 1 | 59 |
| 2 | 2 |
| 5 | 1 |

Niveles de sotano detectados (-1/-2/-3, incluye listas que los mencionen): **si** — ejemplos: ['-1', '-2', '0;-1', '0;-1;-2', '-3', '-1;0', '-1;-2', '-2;0', '-2;-1', '-3;-1']
Decimales detectados (p.ej. -0.5): **si** — valores: ['-1;-0.5', '-0.5', '-0.5;0']

## Parte B.3 — Inventario de conectores

### Vias routeable
- `highway=footway`+`indoor=yes`: **236** — por nivel: {'-1': 114, '-2': 30, '0': 77, '-1;0': 1, '1': 11, '-3': 2, '-0.5': 1}
- `highway=corridor`: **0** — por nivel: {}

### Verticales
- `highway=steps`: **129** — por nivel: {'-1;0': 59, '0;-1': 13, '-1': 3, '-1;-2': 7, '-2;0': 2, '-2;-1': 21, '0': 3, '-3;-1': 1, '-1;-3': 1, '0;1': 7, '-1;-0.5': 1, '-2;-3': 4, '-3;-2': 6, '-0.5;0': 1}
- `highway=elevator`: **16** — por nivel: {'0;-1': 3, '0;-1;-2': 1, '-1;0': 6, '-1;-2': 2, '-3;0': 2, '-1;0;1': 1, '0;1': 1}
- `conveying=yes/forward/backward/reversible`: **62** — por nivel: {'-1;0': 28, '0;-1': 6, '-1': 1, '-1;-2': 5, '-2;0': 2, '-2;-1': 11, '-3;-1': 1, '-1;-3': 1, '0;1': 1, '-2;-3': 3, '-3;-2': 3}

### Puertas (dos convenciones distintas)
- tag `door=*` (node): **40** — por nivel: {'0': 21, 'sin level': 3, '-1': 4, '-2': 6, '1': 6}
- tag `indoor=door` (node): **29** — por nivel: {'0': 17, '-1': 3, '-2': 2, '1': 6, 'sin level': 1}
- nodos con AMBAS convenciones a la vez: **29**

### Shape (poligonos)
- `indoor=room`: **122** (88 con `name`)
- `indoor=area`: **11** (2 con `name`)
- `indoor=corridor`: **32** (0 con `name`)

### El DEA ganador

Nodo 13948102741 **SI esta dentro del bbox**. level=`0`, indoor=`yes`, lat=53.5534056, lon=10.0074164.

## Parte B.4 — Conectividad rapida (componentes por nivel)

Red routeable analizada: 236 ways (`footway+indoor=yes` + `highway=corridor`).

| level | # ways | # componentes | mayor componente (nodos) |
|---|---|---|---|
| -3 | 2 | 1 | 5 |
| -2 | 30 | 8 | 19 |
| -1 | 114 | 31 | 59 |
| -1;0 | 1 | 1 | 2 |
| -0.5 | 1 | 1 | 3 |
| 0 | 77 | 5 | 82 |
| 1 | 11 | 3 | 21 |

## Parte C — Parseo de niveles (verificacion)

Valores `level` distintos (raw): **23**, ocurrencias totales: **1531**

Clasificacion: {'entero': 1356, 'lista': 173, 'decimal': 2}

### Conjunto de plantas reales (normalizado)

Plantas detectadas tras expandir listas y rangos (nota: los conteos suman mas que el total de elementos porque una lista como `-1;0` cuenta para ambas plantas):

`-3`=41, `-2`=148, `-1`=881, `-0.5`=5, `0`=554, `1`=75, `2`=2, `5`=1

### Valores de `level` que la funcion NO supo parsear: **0**

(ninguno — todos los valores se parsearon)

