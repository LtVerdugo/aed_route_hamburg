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

Both algorithms guarantee the optimal shortest path, **provided the
heuristic is admissible** (see correction below — this was not always the
case in this project).

The evaluation function is:

  f(n) = g(n) + h(n)

where g(n) is the accumulated cost from the origin and h(n) is an estimate
of the remaining cost to the destination node.

**Correction (2026-08-14, Fase 6 of the audit remediation — see
`docs/decisions.md` for the full history):** before this date, h(n) was
the straight-line distance **in metres**, read directly from the graph's
own node attributes (`G.nodes[u]['x'/'y']`), while the A* weight (`cost_s`)
is in **seconds**. This had two compounding problems, both now fixed:

1. **Units mismatch.** A distance in metres is not comparable to a cost in
   seconds. Since every mode travels at more than 1 m/s, distance in
   metres numerically exceeds the true minimum time cost for any edge of
   positive length — the heuristic overestimated, i.e. it was **not
   admissible**, and A* could no longer guarantee the optimal path.
2. **Inconsistent coordinate reference system.** Regular road nodes keep
   OSMnx's original WGS84 degrees in their `x`/`y` attributes (the graph is
   never reprojected — see `graph_builder_osm.py`); only AED nodes, added
   later, get `x`/`y` in EPSG:25832 metres. Reading `G.nodes[...]` directly
   therefore mixed degrees and metres depending on which node was involved,
   which for every real query (always evaluating distance *to* an AED
   node) produced a heuristic value dominated by an enormous, essentially
   constant offset (~5.97 million in this graph) — see the `Fase 1` entry
   in `docs/decisions.md` for the precise mechanism.

**Why this did not, in practice, return wrong routes before the fix:**
every AED node has exactly one incoming edge (its single access edge — see
"AED and Origin Snapping" below), and `nx.astar_path` returns as soon as
it pops the target node from its priority queue. Because the mixed-CRS
heuristic was near-constant across all *regular* nodes, the search still
explored them in true cost order (as Dijkstra would); the AED node was
then relaxed exactly once, via its one real predecessor, at that
predecessor's true optimal cost, and immediately returned. **This
guarantee depends entirely on AED nodes having exactly one access edge.**
If an AED were ever connected to more than one access node (e.g. a
mode-dependent snap for `car`, see the open `docs/decisions.md` entry on
that mode), the same inadmissible heuristic could make A* return via a
more expensive predecessor discovered first, silently skipping a cheaper
one discovered later — this exact scenario is now a permanent regression
test, see `tests/test_heuristic_admissibility.py`.

**The fix:** `h(n)` now reads coordinates from `nodes_df` (via a
`node_key -> (x, y)` lookup built once and cached), never from
`G.nodes[...]` — `nodes_df` projects every node, road and AED alike,
consistently to EPSG:25832 metres (verified against the actual loaded
graph before writing this fix: 100% of 657,870 road nodes and 139 AED
nodes fall within a plausible metric range for this CRS in northern
Europe; zero degree-scale values). The distance is then divided by the
**maximum** speed achievable by the mode in the network (not the average):
dividing by the maximum keeps h(n) an underestimate of the true minimum
time cost for every edge, which is what admissibility requires — dividing
by the average would overestimate the cost of any edge faster than
average and reintroduce the same problem. For walk and bike this is the
existing `WALK_SPEED_M_S`/`BIKE_SPEED_M_S` constants, each verified
against the loaded graph to be the true network maximum for that mode
(walk: exactly 1.7 m/s on 100% of measured edges; bike: 4.5 m/s maximum,
with the AED access edges' known 1.7 m/s quirk — see the open
methodology question above — still safely below that maximum). Car has no
single constant; its maximum (33.33 m/s / 120 km/h) is **measured directly
from the loaded graph's edges** rather than assumed, and cached at the
module level to avoid rescanning ~646,000 edges per request.

**Measured effect:** after the fix, A* explores visibly fewer nodes for
the same query — e.g. 2,560 → 259 nodes for a representative walk query
in the city centre (≈90% fewer), 43,229 → 9,377 for a query near the
administrative boundary (≈78% fewer). This is the first time this
project's A* has actually benefited from heuristic guidance rather than
behaving close to plain Dijkstra — the "60-80% fewer nodes than Dijkstra"
claim below was aspirational before this fix, not measured.

**Correction after code review (2026-08-14, same day — see
`docs/decisions.md` for the full review):** the first version of this fix
claimed unqualified admissibility ("h(n) never overestimates the true
cost"), which an independent code review found to be very slightly false
in practice, and which was then independently reproduced: the straight-
line distance computed from EPSG:25832-projected coordinates can exceed
the `length_m` OSMnx recorded for the same edge (computed geodetically on
the WGS84 ellipsoid), because the UTM-based projection has a scale
distortion that is not exactly 1 away from its central meridian. Measured
directly against the loaded graph (20,000 sampled edges, plus the edges
around the Neuwerk exclave specifically, as the area furthest from the
projection's central meridian): the projected straight-line distance
exceeds the recorded `length_m` on effectively 100% of edges, by a mean of
~0.18% and a measured maximum of ~0.298%. `heuristic()` now applies a 1%
safety margin (`_ADMISSIBILITY_SAFETY_MARGIN` in `routing.py`, more than
3× the measured worst case) to restore a real, not just nominal,
admissibility guarantee. This margin barely blunts the heuristic's
guidance (node counts above already include it) and does not change any
route selection (golden files unchanged both before and after adding the
margin).

A* is preferred over plain Dijkstra because an admissible heuristic
prioritises nodes in the direction of the destination, typically exploring
60-80% fewer nodes than Dijkstra for the same result on geographic
networks — this is now actually true of this implementation, not just of
A* in general.

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

**AED snap NOT restricted to giant component — origin side fixed in Fase
7, AED side remains known, quantified technical debt (updated
2026-08-14):**
This section previously claimed that AED nodes are snapped only to nodes
within the giant weakly connected component of the unified graph. That was
never what `add_aed_nodes_to_graph` (`src/aed_route/graph_builder_osm.py`)
does — its snapping `cKDTree` is built over *all* road nodes, with no
connectivity filter, and this is unchanged by Fase 7 (the graph pickle is
immutable for this remediation effort — `graph_builder_osm.py` was not
touched).

**Origin snapping was fixed in Fase 7 (2026-08-14)**: `snap_origin_to_graph`
now receives a `node_index` already restricted to the giant weakly
connected component (computed once at startup in `app/app.py`, cached as
`data/processed/graph_giant_component_excluded_nodes.json` — a derived
artifact, not a graph modification). A click near a small disconnected
fragment now snaps to a real, reachable node instead of an isolated one
that could never yield a route to any AED.

**The AED side remains exactly as before, and its scale is now known**: 9
of the 139 AED nodes in the graph are outside the giant component (logged
as a WARNING with their node_keys at every startup — see
`app/app.py`). These 9 are practically unreachable from almost any origin,
in any mode, and `find_nearest_aeds` silently drops them as A* candidates
whenever `nx.astar_path` raises `NetworkXNoPath` for them — that specific
discard is no longer silent either: it is now logged (`INFO` level, see
`src/aed_route/routing.py`), though the underlying unreachability is still
not fixed. Fixing it requires rebuilding the graph's AED access edges,
which is out of scope while the graph is immutable — accepted as known
technical debt, with the count now quantified rather than unknown. See
`docs/decisions.md` for the mechanism this uncovered (a previously
invisible false-positive route, discussed under "Edge Cases and Observed
Anomalies" below) and the argument it provides for a future rebuild
discussion.

**This "9" is a different metric from elsewhere in this document (e.g.
"AED nodes skipped: 2" in the AED-snapping section above) — they are not
the same count and should not be conflated or "reconciled" into one
number.** The skipped-2 count is about AEDs that never became graph nodes
at graph-build time (no road node within `MAX_SNAP_DISTANCE_M`). The
9 discussed here ARE graph nodes, connected to the network — just to a
small disconnected fragment of it. 141 AEDs sourced → 139 become graph
nodes (2 skipped) → of those 139, 9 are practically unreachable (this
section) and 130 sit in the giant component and route normally.

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
.venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 5000

(Corrected 2026-08-14 — there is no `app/flask_app.py` in this repo; the
entry point is `app/app.py`, run via uvicorn, not a direct `python
app/flask_app.py` invocation. Port unified to **5000** across every
deployment artifact in this repo on this same date — this document
previously described an inconsistency between 5000 and 5050, now fixed.
This choice was made for internal consistency between this repo's own
files; it has NOT been verified against the actual reverse proxy
configuration running in production — see `docs/decisions.md`.)

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

### Origin trapped in an isolated fragment — a route that looked excellent
was a false positive (found while building the Fase 7 regression golden
files, 2026-08-14)

**How this was identified:** while selecting golden test cases for a
fragment of the network known to sit outside the giant weakly connected
component, one origin returned a suspiciously good result — 1 route, in
walk mode, to an AED only 45.2 seconds away. On the surface this looked
like a routing success story, not an edge case.

**What we found:** both the origin's snapped node and the target AED were
inside the *same* small disconnected fragment of the graph (a component of
just a few dozen nodes, isolated from the main network). The 45.2-second
route was entirely real *within that fragment* — but the fragment itself
has no connection to the rest of Hamburg's usable network. Confirmed
directly against the loaded graph: the AED in question (`aed_5880920245`)
is one of the 9 AED nodes now known to sit outside the giant component
(see "Giant component constraint" above). Before Fase 7, the origin
snapped to whichever node was nearest in absolute terms, with no
connectivity check — so it landed inside that same isolated fragment,
and from there the short internal route to the equally-isolated AED
looked, from the API response alone, like an ordinary successful query.

**Why this matters more than an empty result would:** an origin that
returns *zero* routes is at least visibly a failure — a user, or an
automated test, can tell something is wrong. An origin that returns a
short, plausible-looking route to a real AED, when that AED is in fact
unreachable from anywhere a real person could actually be standing, is a
**silent false positive** — worse than no answer, because it looks like a
correct one. This was invisible before Fase 7 specifically because
nothing checked whether the origin's own snap was inside the giant
component in the first place.

**What Fase 7 changed:** origin snapping is now restricted to the giant
component (see above), so this exact origin now snaps to a real,
reachable node instead, and correctly no longer returns a route to
`aed_5880920245` — it returns routes to genuinely reachable AEDs instead,
at a realistic (much longer) travel time. The false-positive AED simply
disappears from the candidate list, as it should.

**Why this is a real argument for eventually rebuilding the graph, not
just a curiosity:** this failure mode is not limited to origins — any AED
among the 9 outside the giant component could, in principle, produce the
same kind of false positive for an origin that happens to share its
isolated fragment. The origin-side fix in Fase 7 does not, and cannot,
close this on the AED side (fixing it means re-snapping AED access edges,
which requires rebuilding the immutable graph bundle — out of scope
here). This case is the concrete evidence to bring to that future
rebuild discussion: it is not hypothetical, it happened, and it was
invisible until specifically investigated.

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