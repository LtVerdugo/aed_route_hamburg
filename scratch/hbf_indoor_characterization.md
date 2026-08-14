# Caracterizacion de datos indoor — Hamburg Hauptbahnhof (Fase 2a)

Fuente: `data/interim/indoor_probe_hamburg_hauptbahnhof.json` — 563 elementos (84 nodes, 474 ways, 5 relations).

## 1. Niveles (`level` y tags relacionados)

### `level` — presente en 526 elementos
Clasificacion de valores: {'entero': 389, 'lista': 137}
Valores distintos (top 15, con conteo): `0`=183, `-1`=128, `-1;0`=59, `-2`=49, `1`=27, `0;-1`=17, `-2;-1`=16, `-1;-2`=13, `0;1`=10, `-3;-2`=9, `-2;-3`=4, `-3;0`=2, `-3;-1`=2, `-3`=2, `-2;0`=2

### `repeat_on` — presente en 7 elementos
Clasificacion de valores: {'entero': 3, 'lista': 4}
Valores distintos (top 15, con conteo): `-1;0`=3, `-3`=2, `1`=1, `-1;0;1`=1

### `level:ref` — presente en 0 elementos
No aparece en el dataset.

### `min_level` — presente en 0 elementos
No aparece en el dataset.

### `max_level` — presente en 0 elementos
No aparece en el dataset.

### `layer` vs `level`
- Elementos con AMBOS `layer` y `level`: **121**
- Elementos con `layer` pero SIN `level`: **0**
- Elementos con `level` pero SIN `layer`: **405**
- Casos donde `layer` != `level` en el mismo elemento (posible fuente de confusion — `layer` es orden de dibujo/apilado, no piso fisico):
  - node 2264152042: layer=`-1`, level=`0` (tag principal: `None`)
  - node 6920651502: layer=`-1`, level=`-2` (tag principal: `None`)
  - node 7038736689: layer=`-1`, level=`-2` (tag principal: `None`)
  - node 7038736692: layer=`-1`, level=`-2` (tag principal: `None`)
  - node 13948102741: layer=`1`, level=`0` (tag principal: `yes`)

## 2. Vias horizontales: lineas vs areas

- `highway=corridor` (ways = lineas navegables): **0**
- `highway=footway` + `indoor=yes` (ways = lineas navegables): **215**
- `indoor=corridor` como tag principal (sin `highway=corridor`, suele ser poligono de pasillo): **25**
- `indoor=area` / `indoor=room` (poligonos de sala/area, NO lineas navegables): **129**

Desglose por tipo de elemento OSM y tag:

| tipo | tag | conteo |
|---|---|---|
| way | highway=footway+indoor=yes | 215 |
| way | indoor=room | 116 |
| way | indoor=corridor | 22 |
| way | indoor=area | 10 |
| relation | indoor=area | 3 |
| relation | indoor=corridor | 2 |
| node | indoor=corridor | 1 |

**Conclusion de la seccion:** hay **215** elementos tipo *linea navegable* (`highway=corridor` o `footway`+`indoor=yes`) y **154** elementos tipo *poligono* (`indoor=area/room/corridor`). Ambos coexisten en este dataset — el routing indoor de Hbf no puede basarse solo en lineas: una parte relevante del espacio (salas, vestibulos, la 'Galerie') solo esta mapeada como poligono sin una linea de centro explicita.

Ejemplo `indoor=area`/`indoor=room`:
```json
{
  "type": "way",
  "id": 99048980,
  "center": {
    "lat": 53.5522659,
    "lon": 10.009557
  },
  "tags": {
    "access": "customers",
    "area": "yes",
    "bench": "yes",
    "bin": "yes",
    "customers": "HVV",
    "indoor": "area",
    "layer": "-2",
    "level": "-2",
    "name": "Hauptbahnhof Süd",
    "public_transport": "platform",
    "railway": "platform",
    "railway:track_ref": "4",
    "ref": "4",
    "ref:IFOPT": "de:02000:10906:2:109017",
    "subway": "yes",
    "tactile_paving": "yes",
    "tunnel": "yes",
    "wheelchair": "yes"
  }
}
```

## 3. Conexiones verticales

### highway=steps — total 110, por tipo: {'way': 110}
Forma del tag `level` en estos elementos: {'lista': 104, 'entero': 6}
Ejemplos:
```json
{
  "type": "way",
  "id": 28686946,
  "center": {
    "lat": 53.5516345,
    "lon": 10.0051982
  },
  "tags": {
    "conveying": "reversible",
    "description": "Mö-Passage / Mönckebergstr. (Südseite)",
    "handrail": "yes",
    "highway": "steps",
    "incline": "up",
    "level": "-1;0",
    "lit": "yes",
    "ref": "65605782 200",
    "step_count": "23",
    "surface": "metal",
    "time": "18 sec",
    "width": "100 cm"
  }
}
```
```json
{
  "type": "way",
  "id": 28686956,
  "center": {
    "lat": 53.5522133,
    "lon": 10.0063809
  },
  "tags": {
    "handrail": "yes",
    "highway": "steps",
    "incline": "up",
    "indoor": "yes",
    "level": "-1;0",
    "lit": "24/7",
    "platform_lift": "no",
    "step_count": "32",
    "surface": "concrete",
    "tactile_paving": "yes",
    "tactile_writing": "yes"
  }
}
```
```json
{
  "type": "way",
  "id": 28686963,
  "center": {
    "lat": 53.5522662,
    "lon": 10.0082057
  },
  "tags": {
    "highway": "steps",
    "incline": "up",
    "indoor": "yes",
    "level": "-2;-1",
    "note": "die beiden Treppen liegen direkt übereinander",
    "surface": "paving_stones",
    "tactile_paving": "yes"
  }
}
```

### highway=elevator — total 13, por tipo: {'node': 2, 'way': 11}
Forma del tag `level` en estos elementos: {'lista': 13}
Ejemplos:
```json
{
  "type": "node",
  "id": 3260318503,
  "lat": 53.553283,
  "lon": 10.0078101,
  "tags": {
    "customers": "HVV",
    "description": "Straße/Bahnsteig , Gleis 1+2 (S-Bahn)",
    "highway": "elevator",
    "level": "-1;0",
    "manufacturer": "Brobeil Aufzüge GmbH & Co. KG",
    "name": "Aufzug zu Gleis 1/2 (S-Bahn)",
    "operator": "DB Station&Service AG",
    "ref:manufacturer_inventory": "046952",
    "ref:operator_inventory": "10028020",
    "source": "http://data.deutschebahn.com/dataset/aufzug/",
    "start_date": "2004",
    "wheelchair": "yes"
  }
}
```
```json
{
  "type": "node",
  "id": 4351224000,
  "lat": 53.5519062,
  "lon": 10.0087167,
  "tags": {
    "description": "Straße/Schalterhalle",
    "highway": "elevator",
    "level": "0;-1",
    "manufacturer": "Hütter Aufzüge",
    "operator": "Hamburger Hochbahn AG",
    "ref": "951436",
    "since": "1996",
    "wheelchair": "yes"
  }
}
```
```json
{
  "type": "way",
  "id": 408843250,
  "center": {
    "lat": 53.5539093,
    "lon": 10.0051121
  },
  "tags": {
    "access": "customers",
    "building": "yes",
    "description": "Straße/Bahnsteig U2, Richtung: Mümmelmannsberg",
    "highway": "elevator",
    "indoor": "room",
    "level": "-3;0",
    "manufacturer": "Hütter Aufzüge",
    "operator": "Hamburger Hochbahn AG",
    "ref": "1000963",
    "since": "2006",
    "tactile_writing": "yes",
    "wheelchair": "yes",
    "width": "2.2"
  }
}
```

### conveying=yes (escaleras mecanicas / cinta) — total 0, por tipo: {}
No aparece en el dataset.

### stairs=yes — total 2, por tipo: {'way': 2}
Forma del tag `level` en estos elementos: {'lista': 2}
Ejemplos:
```json
{
  "type": "way",
  "id": 343467770,
  "center": {
    "lat": 53.5535512,
    "lon": 10.0064851
  },
  "tags": {
    "indoor": "area",
    "level": "-1;0",
    "stairs": "yes",
    "stairwell": "yes"
  }
}
```
```json
{
  "type": "way",
  "id": 733736733,
  "center": {
    "lat": 53.5535004,
    "lon": 10.0063688
  },
  "tags": {
    "indoor": "area",
    "level": "0;1",
    "stairs": "yes"
  }
}
```

## 4. Conectividad

**Limitacion importante del dataset actual:** la query de la Fase 0 uso `out tags center;`, que devuelve solo tags + un punto centroide para ways y relations — **no incluye la lista de nodos que componen cada way** (474 de 474 ways sin `nodes`/`geometry`). Por tanto, **no es posible verificar desde este JSON si dos corridors/footways comparten un nodo real** (topologia navegable en el sentido de grafo). Para confirmarlo se necesitaria re-descargar con `out geom;` o `out body; >; out skel qt;` y comparar IDs de nodo compartidos entre ways. Esto es un requisito a resolver antes de diseñar el parser — no se puede asumir conectividad de grafo solo con centroides.

- Nodos con tag `door`: **41**
- Nodos con tag `entrance`: **51**
- De los 41 nodos `door`, **41** estan a <=15 m del centroide de alguna via/area indoor routeable (proxy grosero de 'sobre la via', ya que no tenemos geometria exacta de las ways).
- De los 51 nodos `entrance`, **36** estan a <=15 m del centroide de alguna via/area indoor routeable.

Nota: estos nodos `door`/`entrance` **no tienen coordenadas del way al que pertenecen** — son nodos independientes con lat/lon propio; en el modelo OSM real suelen estar insertados como vertices de un way de edificio o de un corridor, pero eso solo se confirma con la lista completa de nodos del way (ver limitacion arriba).

### Entradas por nivel
| level | # entradas |
|---|---|
| -1 | 3 |
| 0 | 19 |
| 1 | 1 |
| sin level | 28 |

La mayoria de nodos `entrance` **no llevan tag `level` propio** — el nivel al que da una entrada normalmente se infiere del way de edificio en el que esta insertada, no del nodo mismo. Con los datos actuales (sin membership de ways) no podemos asignar con certeza cuantas entradas dan a level 0 vs otros niveles.

## 5. Valores de `access`

Sobre 483 elementos indoor/routeables relevantes:

| access | conteo |
|---|---|
| (sin tag) | 438 |
| customers | 37 |
| yes | 5 |
| emergency | 2 |
| no | 1 |

- Elementos con `access=no` o `access=private`: **1** de 483. Con el filtro actual del proyecto (`access!~no|private` aplicado a las 3 redes de calle), estos quedarian excluidos tambien dentro del edificio si se reutiliza la misma regla para indoor.

## 6. El DEA ganador (nodo 13948102741)

Tags completos:
```json
{
  "type": "node",
  "id": 13948102741,
  "lat": 53.5534056,
  "lon": 10.0074164,
  "tags": {
    "access": "yes",
    "check_date": "2026-06-14",
    "defibrillator:location": "Eingangsbereich DB Lounge, am oberen Ende der Treppe gleich links, nahe dem Tresen",
    "emergency": "defibrillator",
    "indoor": "yes",
    "layer": "1",
    "level": "0",
    "opening_hours": "Mo-Fr 06:00-22:00; Sa,Su,PH 07:30-20:30",
    "operator": "Deutsche Bahn",
    "source": "estimate; extrapolate; survey"
  }
}
```

- `level` = `0`
- `indoor` = `yes`
- `defibrillator:location` (texto libre) = "Eingangsbereich DB Lounge, am oberen Ende der Treppe gleich links, nahe dem Tresen"

Elementos routeables/indoor mas cercanos (por distancia al centroide, linea recta, no por red):

| distancia (m) | tipo | id | tag principal | level |
|---|---|---|---|---|
| 1.7 | way | 733736697 | room | 0 |
| 7.1 | way | 733736715 | room | 0 |
| 8.3 | way | 733736701 | room | 0 |
| 11.3 | way | 344257661 | footway | 0 |
| 13.3 | way | 733736730 | steps | 0;1 |
| 13.4 | way | 733736707 | area | 0;1 |
| 14.1 | way | 733736657 | footway | 0 |
| 14.8 | way | 344257663 | footway | 0 |

El elemento routeable/indoor mas cercano es way `733736697` a **1.7 m** (distancia recta centroide-a-punto, no de red) con level=`0`. El DEA esta en level=`0`; coincide con el nivel del elemento mas cercano — a verificar manualmente antes de asumir que es el punto de enganche correcto, dado que la distancia es centroide-a-centroide (los ways no tienen geometria completa en este dataset, ver seccion 4).

