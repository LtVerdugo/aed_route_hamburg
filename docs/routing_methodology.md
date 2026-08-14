# Routing Methodology

## Purpose

This document defines the multimodal routing rules used in the **AED Route Hamburg** project. Its goal is to make the routing behaviour transparent, reproducible, and easy to explain.

The routing model is built from OpenStreetMap (OSM) data and supports three transport profiles:

- walking
- bicycle
- car

This document explains:

- which OSM ways are considered routable for each transport profile
- which access restrictions are applied
- how directionality is handled
- how travel-time assumptions are defined
- how the network is prepared before graph construction

---

## General Modelling Principles

The routing model follows these principles:

1. **Routing is always performed on the mapped network.**
   The model does not assume free movement across land-cover
   polygons such as parks, green areas, or open spaces.

2. **Movement through parks is only allowed if a traversable
   OSM way exists there.**
   For example, walking may use a footway or path, but the
   model does not assume unrestricted movement across a park
   polygon.

3. **Each transport profile has its own accessibility logic.**
   Walking, cycling, and driving are treated as separate routing
   modes with different permissions and travel-time assumptions.

4. **The car profile must only use legally and physically
   compatible infrastructure.**
   The model must never route cars through pedestrian-only or
   cycling-only infrastructure unless a valid drivable way is
   explicitly mapped in OSM.

5. **The network is cached and reused.**
   Heavy preprocessing steps such as network download and graph
   construction are performed once and stored locally. Only the
   final route search is executed on demand.

6. **The road network is downloaded using OSMnx.**
   OSMnx is used to download and construct the multimodal network
   from OpenStreetMap. Three separate networks are downloaded
   (walk, bike, drive) and merged into a single unified graph.

---

## Precedence of Access Rules

Access rules are applied by OSMnx internally during network
download, based on standard OSM tags. The following rules
summarise the behaviour:

### Strong Exclusion Rules

A way is excluded for a given mode if any of the following
conditions apply:

- access=no or access=private
- foot=no for walking
- bicycle=no for bicycle routing
- vehicle=no or motor_vehicle=no for car routing

### Explicit Inclusion Rules

A way is explicitly allowed for a given mode if any of the
following transport-specific tags are present:

- foot=yes, foot=designated, or foot=permissive for walking
- bicycle=yes, bicycle=designated, or bicycle=permissive for cycling
- vehicle=yes or motor_vehicle=yes for driving

These rules are enforced by OSMnx at download time and do not
require manual evaluation in the project code.

---

## Directionality Rules

Directionality is defined per mode and derived from OSM tags.

**Walking** is fully bidirectional by default. All walkable
segments have both forward and backward directions active
(100% of can_walk segments).

**Cycling** is fully bidirectional by design in this project.
In an emergency context, a person on a bicycle will not respect
oneway conventions. All bikeable segments have both forward and
backward directions active regardless of oneway tags. Missing
reverse edges are added explicitly after OSMnx download.

**Car** respects oneway restrictions. These reflect physical
infrastructure constraints, not behavioural conventions.

**Unified graph rule:** A forward edge A→B is created if at
least one mode has forward=True. A backward edge B→A is created
if at least one mode has backward=True. Each edge carries
can_walk, can_bike, can_drive so the router filters by mode
at query time.

---

## OSM Highway Classification by Transport Profile

| OSM highway    | Walk | Bike | Car | Notes                                                        |
|----------------|------|------|-----|--------------------------------------------------------------|
| motorway       | No   | No   | Yes | High-speed motor road. Excluded for safety, not convention   |
| motorway_link  | Yes  | No   | Yes | Motorway on/off ramp. Included for walk (verified in `WALK_CUSTOM_FILTER`); excluded for bike |
| trunk          | No   | No   | Yes | High-capacity road. Excluded for safety                      |
| trunk_link     | Yes  | No   | Yes | Trunk on/off ramp. Included for walk (verified in `WALK_CUSTOM_FILTER`); excluded for bike |
| primary        | Yes  | Yes  | Yes | Major urban road                                             |
| primary_link   | Yes  | Yes  | Yes | Primary connector ramp. Included in emergency context        |
| secondary      | Yes  | Yes  | Yes | District connector road                                      |
| secondary_link | Yes  | Yes  | Yes | Secondary connector ramp. Included in emergency context      |
| tertiary       | Yes  | Yes  | Yes | Local connector road                                         |
| tertiary_link  | Yes  | Yes  | Yes | Tertiary connector ramp. Included in emergency context       |
| unclassified   | Yes  | Yes  | Yes | Local road, no assigned category                             |
| residential    | Yes  | Yes  | Yes | Residential street                                           |
| service        | Yes  | Yes  | Yes*| Access road. Car included via custom filter                  |
| living_street  | Yes  | Yes  | Yes | Shared street, pedestrian priority                           |
| pedestrian     | Yes  | Yes  | No  | Pedestrian zone. Bike included in emergency context          |
| footway        | Yes  | Yes  | No  | Pavement or path. Bike included in emergency context         |
| path           | Yes  | Yes  | No  | Generic path                                                 |
| cycleway       | Yes  | Yes  | No  | Cycle lane. Walk included in emergency context. Car excluded: physically too narrow |
| track          | Yes  | Yes  | Yes*| Unpaved road. Car included via custom filter                 |
| steps          | Yes  | No   | No  | Stairs. Bike and car cannot use                              |
| road           | Yes  | Yes  | Yes | Unknown classification                                       |

*Included for car via custom_filter in emergency context.
All classes subject to access=no/private exclusions.

**Correction (2026-08-14):** this table previously marked `motorway_link`
and `trunk_link` as `No` for Walk. Verified directly against
`WALK_CUSTOM_FILTER` in `src/aed_route/graph_builder_osm.py`: both terms are
literally present in that filter's regex, so both are in fact included for
walking. The prose in this document (below, and in the "OSMnx Network
Download and Custom Filter" section) was already correct on this point —
only these two table cells were wrong. `motorway` and `trunk` themselves
(without the `_link` suffix) remain correctly excluded for walk, as the
table now shows: only the base `motorway`/`trunk` classes are excluded for
all non-car modes due to physical danger at high speeds — the only
restrictions maintained for safety reasons rather than
behavioural conventions. `_link` ramps are not excluded for walk.

---

## Interpretation by Transport Mode

### Walking Profile

The walking profile uses a custom OSMnx filter that extends
the default network_type="walk" to include cycleways and all
*_link connector ramps. In an emergency context, a person
will cross any infrastructure to reach an AED. Only motorway
and trunk classes are excluded due to physical danger at high
vehicle speeds.

### Bicycle Profile

The bicycle profile uses a custom OSMnx filter that extends
the default network_type="bike" to include pedestrian zones,
footways and all *_link connector ramps. All bikeable segments
are treated as bidirectional regardless of oneway tags.

### Car Profile

The car profile uses a custom OSMnx filter that extends the
standard network_type="drive" to include service and track roads.
See section "OSMnx Network Download and Custom Filter" for details.

---

## Parks and Green Areas

The model does not assume unrestricted movement across green areas.

- **Walking** may cross parks only through mapped walkable infrastructure.
- **Cycling** may cross parks only through mapped bicycle-compatible infrastructure.
- **Cars** may not cross parks unless a legally drivable road is explicitly mapped.

This means that the routing logic always follows the network and never assumes free movement across open land.

---

## Travel-Time Assumptions

Travel-time costs are mode-specific.

- The **walking profile** uses a constant emergency walking speed of **1.7 m/s**. This is consistent with the modelling parameter already used in the current AED project configuration
- The bicycle profile uses a constant cycling speed of 4.5 m/s.
- The **car profile** uses `maxspeed` when available in OSM; otherwise it falls back to conservative defaults by road class.

---

## OSMnx Network Download and Custom Filter

The road network is downloaded using OSMnx with custom filters
for all three modes. Default OSMnx network_type filters are
not used because they exclude infrastructure that is relevant
in an emergency context.

**Walk custom filter:**
Includes cycleways and all *_link connector ramps, which
OSMnx network_type="walk" excludes by default. In an emergency,
a person will cross any infrastructure to reach an AED.
Only motorway and trunk classes are excluded due to physical
danger at high vehicle speeds.

**Bike custom filter:**
Includes pedestrian zones, footways and all *_link connector
ramps, which OSMnx network_type="bike" excludes by default.
In an emergency, a cyclist will use any available infrastructure.
Only motorway and trunk classes are excluded.

**Drive custom filter:**
Includes service and track roads, which OSMnx
network_type="drive" excludes by default. In an emergency
context, a vehicle may need to use service roads (e.g. access
roads to hospital car parks) and unpaved tracks.
access=no and access=private are excluded in all modes.

**Why cycleways are excluded for car:**
Cycleways are physically too narrow (typically 1.5-2 metres)
for a car to use safely, even in an emergency. This is a
physical constraint, not a behavioural convention.

**Download parameters for all modes:**
- retain_all=True: preserves all connected components
- simplify=False: preserves all geometry vertices as nodes,
  ensuring node consistency across the three modal networks

**Empirical results — Hamburg unified graph:**

| Metric        | Value         |
|---------------|---------------|
| Nodes         | 658,009       |
| Edges         | 1,472,241     |
| can_walk      | 94.5%         |
| can_bike      | 98.2%         |
| can_drive     | 43.9%         |
| AED nodes     | 139           |

---

## Mode-Specific Routing Costs

The model distinguishes between physical travel time and routing cost.

- **Travel time** represents the estimated time needed to traverse a segment under normal assumptions for the selected mode.
- **Routing cost** represents the value used by the routing algorithm.

In the current implementation:

- walking uses `walk_cost_s`
- cycling uses `bike_cost_s`
- driving uses `drive_cost_s`


## Graph Representation

The project uses a single unified directed graph (MultiDiGraph) 
covering all three transport modes. Three separate networks are 
downloaded via OSMnx and merged into one graph.

Each edge in the unified graph:
- exists once as a physical segment (forward or backward direction)
- carries can_walk, can_bike, can_drive flags
- carries walk_cost_s, bike_cost_s, drive_cost_s for mode-specific routing
- is filtered by mode at query time, not at construction time

Empirical results of the unified graph (OSMnx):
- Nodes: 653,757
- Edges: 1,460,697
- can_walk=True: 1,321,694 edges (90.5%)
- can_bike=True: 888,674 edges (60.8%)
- can_drive=True: 645,996 edges (44.2%)

**Edge geometry orientation:**
Edge geometries are stored oriented in the direction of travel.
For forward edges (u→v), the geometry follows the original OSM
direction. For backward edges (v→u), the geometry is reversed
at graph construction time. This ensures that route geometries
can be drawn correctly without any runtime correction per query.

## Computational Strategy

To keep the application efficient:

1. The network is downloaded and cached locally.
2. The graph is built once and cached.
3. AED candidates are prefiltered by Euclidean distance.
4. The final path search is performed with **A\*** only on the shortlisted candidates.

This avoids repeated heavy preprocessing during normal app use.

---

## AED and Origin Snapping

**AED nodes** are integrated as permanent nodes in the unified
graph at graph construction time. Each AED is connected to its
nearest graph node via a bidirectional access edge whose cost
equals the Euclidean distance converted to travel time at
walking speed. This means the access distance is included in
the total route cost automatically.

This design ensures that:
- the access edge cost is part of the total route cost
- the access edge geometry is rendered as part of the route
- no special-case resolution is needed at query time

**Empirical results (corrected 2026-08-14 — verified against the actual
cached data, not the figures previously in this table):**

| Metric                                            | Value      |
|----------------------------------------------------|------------|
| AEDs in source (`data/processed/hamburg_aeds.geojson`) | 141    |
| AED nodes added to graph                          | 139        |
| AED nodes skipped (beyond `MAX_SNAP_DISTANCE_M` = 100 m) | 2    |
| Mean access edge length                           | 17.3 m     |
| Maximum access edge length                        | 60.0 m     |

The mean/maximum access edge length figures above were not re-verified in
this correction pass (doing so would require loading the 364 MB graph
bundle and recomputing them; they are left as previously recorded, not
independently re-confirmed).

**Origin snapping** is performed at query time. The user's
click coordinates are projected to EPSG:25832 and snapped to
the nearest graph node using a prebuilt spatial index
(build_node_index). If no node is found within
MAX_SNAP_DISTANCE_M, the query returns no results.

---

## Candidate Selection and Routing Algorithm

### Problem formulation

Given an origin point, the goal is to find the nearest AED by 
network distance, not by straight-line distance. The nearest AED 
in Euclidean space is not always the nearest by network — physical 
barriers such as rivers, motorways, or railways may make a 
geometrically closer AED unreachable or significantly more costly 
by the actual network.

### Two-stage approach

Routing is implemented in two stages:

**Stage 1 — Euclidean prefilter:**
From all 141 AEDs, the K nearest by straight-line distance are 
selected using a spatial index (cKDTree on EPSG:25832 coordinates). 
This is an O(log n) operation and runs in microseconds.

**Stage 2 — Network shortest path:**
A* is run from the origin node to each of the K candidate AED nodes. 
The candidate with the lowest network cost is selected as the result.

### Why A* and not Dijkstra

Both algorithms guarantee the optimal shortest path. A* is preferred 
because it uses a Euclidean heuristic h(n) to prioritise nodes in 
the direction of the destination, typically exploring 60-80% fewer 
nodes than Dijkstra for the same result on geographic networks.

The evaluation function is:

  f(n) = g(n) + h(n)

where g(n) is the accumulated cost from the origin and h(n) is the 
straight-line distance to the destination node. This heuristic is 
admissible — it never overestimates the true cost — which guarantees 
optimality.

### Why K=5

K=5 was selected based on the following reasoning:

- K=1 would assume the Euclidean nearest AED is always the network 
  nearest, which is not guaranteed in the presence of physical 
  barriers (rivers, motorways, railways).
- K=3 was used in a related routing project but provides limited 
  margin for barrier-induced detours.
- K=5 provides a conservative safety margin while keeping the number 
  of A* searches minimal (5 searches per query).
- K=15 (previous default) was an arbitrary value never validated 
  against empirical data and is disproportionate given the low AED 
  density in Hamburg (141 AEDs across the city).

This decision is documented explicitly and may be revised if future 
analysis identifies cases where K=5 fails to include the true 
network-nearest AED.

### Parameters

- SHORTLIST_EUCLIDEAN_K = 5 (updated from previous default of 15)
- Weight used for routing: walk_cost_s, bike_cost_s, or drive_cost_s 
  depending on the selected transport mode

---

## Isochrone Coverage Analysis

Walk isochrones are precomputed for each AED and cached
as a GeoJSON file (data/processed/hamburg_isochrones_walk.geojson).
They are loaded at FastAPI startup and served via /api/isochrones.

**Method:**
For each AED node and each time threshold, all reachable nodes
are found using nx.ego_graph (Dijkstra one-to-all) on the walk
subgraph. The isochrone polygon is then built by:
1. Converting reachable edges to a GeoDataFrame (ox.graph_to_gdfs)
2. Projecting to EPSG:25832 for accurate metric buffering
3. Buffering each edge by 25 metres
4. Unioning all buffers into a single polygon
5. Simplifying with tolerance 5 metres
6. Reprojecting to WGS84 for GeoJSON output

This edge-buffer approach produces isochrones that follow the
street network rather than abstract convex or concave hulls.

**Time thresholds:**
- 2 minutes (120s) — critical window. At WALK_SPEED_M_S = 1.7 m/s
  this corresponds to a network radius of ~204 m.
- 4 minutes (240s) — outer limit. Corresponds to ~408 m network radius.
  Survival rates from cardiac arrest drop significantly beyond
  this window without defibrillation.

Note: the specific time thresholds and speed assumptions require
validation against clinical literature. This is documented as
a pending task in Open Questions and Pending Decisions.

**Visualisation:**
- 4-minute isochrone: yellow (#eab308), fillOpacity 0.12
- 2-minute isochrone: green (#16a34a), fillOpacity 0.25
- Both layers toggled via "Show/Hide isochrones" button in the panel
- Isochrones are static — precomputed at build time, not per query

**Empirical results (corrected 2026-08-14 — verified directly against the
current cached file, `data/processed/hamburg_isochrones_walk.geojson`):**
- Features in cache: 278, confirmed to be exactly 139 unique AED ids × 2
  time thresholds, with no shortfall — i.e. **all 139 AED graph nodes have
  both isochrones**, not "138 of 139" as this section previously claimed.
  That earlier figure does not match the data currently cached; it may have
  reflected an older AED dataset or graph build, but is not accurate today.
- Cache file size: ~1 MB

---

## Known Limitations

**Private access restrictions in emergency context:**
Ways tagged access=no or access=private are excluded from all
transport modes. In an emergency context, a person running to
an AED may cross private premises. This restriction may be
relaxed in a future version after validation with domain experts.

**Small disconnected components:**
The unified graph may contain small isolated components
disconnected from the main network. These typically represent
private access roads, dead-end service paths, or minor OSM
mapping gaps. AEDs or origin points falling in these components
ideally require snapping to the nearest node within the giant component
before routing — **this is not implemented today** (corrected 2026-08-14;
see the "AED snap restricted to giant component" entry below, which
previously described this as already done).

**Car mode cannot route to any AED, in any origin, ever (known structural
limitation, added 2026-08-14):**
The access edge that connects every AED node to the road network is built
with `can_drive=False` unconditionally (`add_aed_nodes_to_graph` in
`src/aed_route/graph_builder_osm.py`). Since this is the only edge into an
AED node, the `car` subgraph view has zero in-degree at every AED node —
`POST /api/route` with `mode="car"` therefore returns an empty result list
for every possible origin, not just in specific unreachable areas. This is
tracked as a severity-High finding pending a product decision among three
options (make the access edge drivable, route car to the nearest road node
instead of the AED node itself, or remove the car mode from the UI until
resolved) — see `docs/decisions.md` for the full comparison. Not
implemented in this pass.

**OSMnx network coverage:**
OSMnx applies standard OSM access filters that may exclude some
infrastructure present in the previous Overpass-based network.
The empirical difference is documented in the "OSMnx Network
Download and Custom Filter" section.

**Snap to nearest node on long segments:**
The origin snapping uses nearest-node rather than
nearest-segment. On long road segments without intermediate
OSM vertices, the nearest node may be at an intersection
some distance away, causing the route to start from a
different street than expected. This is a known limitation
of the nearest-node approach and affects only cases where
OSM has not mapped intermediate vertices on a segment.

**AED snap NOT restricted to giant component — known gap, not yet fixed
(corrected 2026-08-14):**
This section previously claimed that AED nodes are snapped only to nodes
within the giant weakly connected component of the unified graph. That is
not what the code does: `add_aed_nodes_to_graph`
(`src/aed_route/graph_builder_osm.py`) builds its snapping `cKDTree` over
*all* road nodes, with no connectivity filter — verified directly against
the function body, and confirmed there is no `connected_components`/
`weakly_connected` check anywhere in `graph_builder_osm.py` or
`routing.py`. In practice, an AED whose nearest road node belongs to a
small disconnected component gets connected to that unreachable node, and
`find_nearest_aeds` will silently drop it as a candidate whenever
`nx.astar_path` raises `NetworkXNoPath` — with no log entry today, so this
failure mode is invisible unless investigated directly. Origin-side
filtering to the giant component is planned for a later remediation phase;
because the graph itself (including AED access edges) is not rebuilt as
part of this remediation, the AED side of this gap is accepted as known
technical debt rather than fixed — see `docs/decisions.md`.

## Routing Logic Summary

The project uses a cached multimodal OSM network with three transport 
profiles: walking, bicycle, and car. All profiles are stored in a single 
unified directed graph. Accessibility per mode is determined by can_walk, 
can_bike, can_drive attributes on each edge. Routing is always performed 
on the mapped network and never assumes free movement across open land 
or parks.

## Application Architecture

The routing model is served via a **FastAPI** web application (run with
`uvicorn`) with a Leaflet.js frontend. (Corrected 2026-08-14 — this section
previously said "Flask"; the code has always been FastAPI, see `app/app.py`.)

**Backend (FastAPI):**
- Loads the graph bundle, AED index and node index once at startup. In
  practice, with the cache files already present, this takes roughly 5
  seconds (measured directly against this repo's cached data, not the
  "20-30 seconds" previously claimed here). If `hamburg_graph.pkl` is
  missing, startup instead triggers a live OSMnx rebuild, which is much
  slower and depends on network conditions — see `README_deploy.md`.
- Exposes these endpoints:
  - GET / — serves the live HTML frontend
    (`static/index_original.html` + `static/app_original.js` — see the note
    on frontend variants below; the other pair, `static/index.html` +
    `static/app.js`, is an unlinked older prototype, not served here)
  - GET /api/aeds — returns the AED GeoJSON
  - GET /api/boundary — returns the Hamburg boundary GeoJSON
  - GET /api/isochrones — returns precomputed walk isochrones GeoJSON
  - POST /api/route — receives origin coordinates and mode,
    runs A* routing, returns serialized results as JSON

**Note on frontend variants (added 2026-08-14, verified against the
current code):** `static/` contains two complete HTML+JS pairs.
`index_original.html` + `app_original.js` is the **live** one — it is what
`GET /` actually serves, and it is fully connected to the backend described
above (mode selector, click-to-route via `POST /api/route`, AED/boundary/
isochrone layers loaded via the `/api/*` endpoints through a base-path-aware
`apiUrl()` helper). `index.html` + `app.js` is an **older, unlinked
prototype**: no backend calls at all, a hardcoded demo response, and
Hamburg-Mitte-only GeoJSON loaded from `static/data/`. It is not served at
any route in `app/app.py` and is only reachable by navigating directly to
`/static/index.html`. What to do with this unlinked pair (keep, archive, or
remove) is a pending product decision, not yet made.

**Frontend (Leaflet.js):**
- Full-screen map with CartoDB Positron basemap
- Hamburg boundary rendered as a blue polyline (weight 2)
- White SVG mask (fill-opacity 0.45, fill-rule evenodd)
  applied outside the Hamburg boundary to focus attention
  on the study area. The mask is recomputed on map move
  and zoom using Leaflet layer point projection.
- Left floating panel (300px) with:
  - Transport mode selector (Walk / Bike / Car)
  - Best route card (green) with time, distance and
    AED metadata
  - Compare routes toggle showing up to 4 alternative
    routes with time penalty labels (+Xm Ys longer)
- Routes drawn as polylines:
  - Best route: solid green, weight 5
  - Alternatives: dashed grey, weight 3
- Origin: blue circle marker at click position
- Nearest AED: green circle marker at AED position

**Startup command:**
.venv/bin/uvicorn app.app:app --host 0.0.0.0 --port <port>

(Corrected 2026-08-14 — there is no `app/flask_app.py` in this repo; the
entry point is `app/app.py`, run via uvicorn, not a direct `python
app/flask_app.py` invocation. The exact `<port>` value is currently
inconsistent across this repo's own files — see `docs/decisions.md` — and
is pending unification in a later remediation phase. Do not assume 5050 or
5000 without checking `app/app.py`'s current default and your reverse
proxy configuration.)

---

## Edge Cases and Observed Anomalies

This section documents specific cases investigated during 
validation that produced unexpected behaviour, along with 
their root cause and conclusion.

### Clausewitz-Kaserne — No routing or isochrones in military zone

**How this was identified:**
During visual validation of the walk isochrones, an area in 
western Hamburg (Blankenese) showed AEDs with no visible 
isochrone or unusually small isochrones that did not follow 
any street. This was unexpected — in normal urban areas, 
isochrones always follow the street network. This anomaly 
raised the question: why are there no walk edges or nodes 
in that area?

**What we found:**
Clicking at coordinates 53.5624°N, 9.8327°E returned no 
routing results. Inspecting OSM directly revealed that the 
area corresponds to the Clausewitz-Kaserne — an active 
military base in Blankenese, Hamburg.

OSM reference: https://www.openstreetmap.org/#map=18/53.563450/9.832506

The internal streets of the kaserne exist in OSM but are 
tagged with access=military or access=private. Our custom 
filter explicitly excludes all ways tagged access=no or 
access=private across all three transport modes. As a result, 
the nodes and edges of that area are not part of the giant 
weakly connected component of the walk graph. Without giant 
component nodes within the snap radius, the router cannot 
calculate a route and isochrones cannot be generated for 
AEDs located in that zone.

**Conclusion:**
This is expected and correct behaviour. The model should not 
route through military installations or restricted-access 
zones regardless of the emergency context. The absence of 
isochrones in this area is a direct consequence of the 
access=private exclusion rule, which is intentional.

---

## Open Questions and Pending Decisions

The following decisions require validation with domain experts or colleagues 
before implementation:

**Private access in emergency context (walk):** Should 
  access=private be ignored for the walking profile? In an 
  emergency context, a person running to an AED may cross 
  private premises. To be discussed in next team meeting.

- **Isochrone time thresholds:** The 2-minute and 4-minute thresholds
  are based on general knowledge of cardiac arrest survival rates.
  These should be validated against clinical literature before
  use in operational planning.

- **AED access-edge speed for bike mode (added 2026-08-14):** the access
  edge connecting an AED to the road network uses `WALK_SPEED_M_S` for its
  `bike_cost_s` value too (`add_aed_nodes_to_graph`,
  `src/aed_route/graph_builder_osm.py`), not `BIKE_SPEED_M_S`. This is
  **not classified as a bug** — it may intentionally model dismounting and
  covering the last few metres to the AED on foot, which is a reasonable
  real-world behaviour for a cyclist reaching a defibrillator. It is
  recorded here as an open methodology question because the intent was not
  documented anywhere at the time this was found: confirm with the team
  whether this is deliberate, and if so, document it explicitly as a
  modelling choice rather than leaving it implicit in the code.