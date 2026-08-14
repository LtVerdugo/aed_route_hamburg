# Extraccion exploratoria por level — Hamburg-Mitte (Fase 2b)

## Parte A — Descarga

- Archivo: `data/interim/mitte_level_elements.json` — **2886.1 KB**
- Nodes: **15124**, Ways: **3520**, Relations: **34**
- Total elementos crudos (con posibles duplicados node id por `._; >;`): 18678

Verificado: **0 relations `type=route`** — confirmado, no aparecen (a diferencia del bbox crudo de Hbf en la Fase 2a.2, donde `>;` sin filtro de `level` arrastraba rutas de bus/tren completas). Aqui el filtro `nwr["level"]` en el primer paso evita ese problema porque las relations de ruta no llevan tag `level`.

Tipos de relation presentes: {'multipolygon': 29, 'level': 5}

## Parte B.1 — Catalogo de tags

Total claves de tag distintas: **847**

Top 40 por frecuencia:

| clave | # elementos |
|---|---|
| `level` | 6367 |
| `indoor` | 2055 |
| `highway` | 2027 |
| `name` | 1748 |
| `surface` | 1588 |
| `railway` | 1461 |
| `layer` | 1420 |
| `lit` | 1254 |
| `wheelchair` | 1118 |
| `ref` | 1058 |
| `operator` | 1005 |
| `tunnel` | 922 |
| `amenity` | 875 |
| `check_date` | 873 |
| `opening_hours` | 856 |
| `shop` | 616 |
| `incline` | 581 |
| `addr:street` | 525 |
| `addr:housenumber` | 518 |
| `access` | 471 |
| `electrified` | 460 |
| `gauge` | 460 |
| `frequency` | 457 |
| `voltage` | 457 |
| `brand` | 428 |
| `addr:city` | 425 |
| `railway:signal:direction` | 422 |
| `railway:signal:position` | 414 |
| `addr:postcode` | 410 |
| `website` | 404 |
| `brand:wikidata` | 401 |
| `entrance` | 392 |
| `description` | 387 |
| `tactile_paving` | 375 |
| `check_date:opening_hours` | 369 |
| `step_count` | 367 |
| `smoothness` | 313 |
| `network` | 295 |
| `phone` | 290 |
| `railway:pzb` | 276 |

### Desglose de valores para tags clave

**`indoor`** — 2055 elementos
`yes`=1193, `room`=491, `door`=151, `corridor`=92, `area`=77, `wall`=27, `no`=16, `elevator`=2, `steps`=2, `shop`=2, `stairs`=1, `hall`=1

**`highway`** — 2027 elementos
`footway`=1184, `steps`=579, `elevator`=110, `service`=52, `corridor`=35, `primary`=13, `crossing`=11, `secondary`=9, `construction`=7, `cycleway`=7, `bus_stop`=5, `pedestrian`=4, `traffic_signals`=3, `path`=3, `residential`=2, `tertiary`=2, `road`=1

**`door`** — 229 elementos
`yes`=118, `hinged`=54, `no`=22, `double`=17, `sliding`=9, `automatic`=4, `overhead`=3, `manual`=2

**`entrance`** — 392 elementos
`yes`=245, `main`=53, `emergency`=29, `shop`=15, `staircase`=11, `service`=11, `home`=10, `secondary`=7, `exit`=3, `elevator`=3, `office`=2, `gate`=2, `room`=1

**`railway`** — 1461 elementos
`signal`=445, `rail`=195, `subway`=176, `switch`=151, `subway_entrance`=125, `stop`=112, `light_rail`=84, `platform`=62, `milestone`=54, `key_switch`=15, `railway_crossing`=9, `train_station_entrance`=7, `phone`=7, `buffer_stop`=6, `platform_edge`=4, `station`=3, `derail`=3, `observation`=1, `abandoned`=1, `disused`=1

**`emergency`** — 63 elementos
`fire_extinguisher`=17, `defibrillator`=15, `fire_hose`=10, `fire_hydrant`=9, `phone`=8, `yes`=3, `fire_alarm_box`=1

**`shop`** — 616 elementos
`clothes`=146, `bakery`=50, `vacant`=38, `kiosk`=24, `supermarket`=22, `hairdresser`=21, `shoes`=20, `jewelry`=17, `florist`=15, `chemist`=14, `mobile_phone`=11, `beauty`=11, `books`=11, `perfumery`=11, `optician`=10, `ticket`=9, `cosmetics`=9, `convenience`=9, `travel_agency`=8, `telecommunication`=8

**`amenity`** — 875 elementos
`vending_machine`=129, `fast_food`=123, `restaurant`=111, `waste_basket`=60, `cafe`=52, `parking_entrance`=47, `toilets`=33, `atm`=32, `bar`=31, `bench`=29, `doctors`=27, `dentist`=18, `pharmacy`=13, `pub`=12, `nightclub`=10, `ice_cream`=10, `social_facility`=9, `shelter`=9, `photo_booth`=8, `library`=8

**`tourism`** — 43 elementos
`information`=11, `artwork`=9, `gallery`=6, `attraction`=5, `museum`=5, `viewpoint`=4, `hotel`=2, `picnic_site`=1

## Parte B.2 — Niveles

### `level` — presente en 6367 elementos
Forma de los valores: {'entero': 5464, 'otro/no-numerico': 14, 'lista': 770, 'decimal': 110, 'rango': 9}
Top 20 valores: `0`=1899, `-1`=1810, `1`=886, `-2`=372, `-1;0`=256, `2`=165, `0;1`=98, `-3`=98, `3`=64, `-1;-2`=60, `-4`=58, `-2;-1`=56, `0;-1`=54, `0.5`=38, `-5`=34, `1;2`=27, `6`=22, `-0.5`=22, `-3;-2`=19, `4`=18

**Decimales confirmados (110):** node 10709905762 (level=`0.5`), node 540173279 (level=`1.5`), node 540173291 (level=`1.5`), node 3032552838 (level=`1.5`), node 4054330987 (level=`1.5`), node 6638343468 (level=`0.5`), node 4925162245 (level=`-0.5`), node 4059555116 (level=`0.5`), node 4059555117 (level=`0.5`), node 4059555118 (level=`0.5`)

### `repeat_on` — presente en 42 elementos
Forma de los valores: {'entero': 22, 'lista': 19, 'decimal': 1}
Top 20 valores: `1`=16, `1;2;3`=7, `-1;1;2;3`=5, `-1;0`=4, `2`=3, `-3`=2, `1;2`=2, `-1`=1, `-1;0;1`=1, `1.5`=1

## Parte B.3 — Comparacion con taginfo de indoorequal

taginfo.json: **351** pares (key,value) / **45** claves distintas declaradas por indoorequal.

### Claves del taginfo presentes en nuestros datos (40)

`level`=6367, `indoor`=2055, `highway`=2027, `name`=1748, `railway`=1461, `layer`=1420, `wheelchair`=1118, `ref`=1058, `amenity`=875, `opening_hours`=856, `shop`=616, `access`=471, `website`=404, `entrance`=392, `phone`=290, `conveying`=263, `public_transport`=255, `door`=229, `contact:phone`=160, `contact:website`=153, `vending`=129, `room`=116, `barrier`=105, `office`=84, `emergency`=63, `tourism`=43, `repeat_on`=42, `contact:facebook`=24, `leisure`=19, `landuse`=18, `information`=11, `name:de`=11, `craft`=11, `sport`=8, `name:en`=4, `opening_hours:url`=2, `religion`=2, `station`=2, `uic_ref`=2, `facebook`=1

### Claves del taginfo que NO aparecen en Hamburg-Mitte (5)

`aerialway`, `aeroway`, `exhibit`, `funicular`, `mapillary`

### Tags nuestros relevantes que NO estan en el taginfo de indoorequal (4) — posibles huecos de su lista

`tactile_paving`=375, `ramp`=199, `stairs`=6, `level:ref`=4

## Parte B.4 — Routeable vs Shape vs POI

- (a) Routeable (footway+indoor, corridor, steps, elevator, conveying): **1440**
- (b) Shape/estructura (indoor=room/area/corridor/wall/column): **687**
- (c) POI/semantica (shop/amenity/tourism): **1531**

**Solapes (un elemento puede caer en mas de un grupo — no son mutuamente excluyentes):**
- routeable ∩ shape: **112** (esperado: `indoor=corridor` cuenta en ambos grupos segun la definicion dada)
- shape ∩ poi: **356** (p. ej. una sala `indoor=room` que ademas es `amenity=cafe`, como el caso DB Lounge visto en Hbf)
- routeable ∩ poi: **3**
- en los tres grupos a la vez: **1**

- Elementos que NO caen en ninguno de los tres grupos: **15490** de 18678 totales (tienen `level` pero ninguna de las semanticas pedidas — p. ej. `door`/`entrance` puros, u otras combinaciones de tags).

## Parte B.5 — Gap de elementos SIN `level`

Conteo UNIVERSO en Hamburg-Mitte (4 queries separadas, `out count;`, SIN filtro de `level`) vs. cuantos de esos YA tienen `level` en `mitte_level_elements.json`:

| categoria | universo (todo Mitte) | con `level` | SIN `level` (gap) | % gap |
|---|---|---|---|---|
| highway=steps | 2120 | 579 | 1541 | 72.7% |
| highway=elevator | 132 | 98 | 34 | 25.8% |
| node door | 272 | 214 | 58 | 21.3% |
| node entrance | 6691 | 207 | 6484 | 96.9% |

Estos elementos SIN `level` (o sin ser miembros de ningun way con `level`) son **invisibles para la query `nwr["level"]` de la Parte A** — solo se revelan con una query sin ese filtro, como las 4 usadas aqui. Este es el numero a tener en cuenta para decidir si la extraccion final debe complementarse con una pasada adicional no filtrada por `level` para estos 4 tags clave.

