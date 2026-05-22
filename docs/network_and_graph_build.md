# Network and Graph Build Process

## Purpose

This document describes the operational workflow used to build the multimodal routing network and the mode-specific graphs used in the AED Route Hamburg project.

It complements `routing_methodology.md` by documenting how the methodological rules were implemented and validated.

---

## 1. Data Extraction

The routing network is derived from OpenStreetMap (OSM) data
using OSMnx.

Three separate networks are downloaded for Hamburg:
- Walk network: all pedestrian-accessible infrastructure
- Bike network: all cycling-accessible infrastructure
- Drive network: all motor vehicle infrastructure, including
  service and track roads via a custom filter

The Hamburg administrative boundary is used to define the
download area. OSMnx resolves this automatically from the
cached boundary GeoJSON.

All three networks are downloaded with simplify=False and
retain_all=True to preserve all geometry vertices as nodes.
This ensures node consistency across the three modal networks,
which is required for the merge step in graph construction.

The resulting raw networks are cached locally as a unified
graph bundle (hamburg_graph.pkl) and reused for all subsequent
routing queries.

---

## 2. Base Network Construction

The three modal networks downloaded by OSMnx are merged into
a single unified directed graph (MultiDiGraph).

For each unique directed edge pair (u→v) across the three
networks, a single edge is created in the unified graph with
the following attributes:

- can_walk, can_bike, can_drive: boolean flags indicating
  which modes can traverse this edge
- walk_cost_s, bike_cost_s, drive_cost_s: travel time in
  seconds for each mode
- walk_time_s, bike_time_s, drive_time_s: physical travel
  time estimates
- length_m: edge length in metres
- highway, name, geometry: OSM attributes

Travel times are taken from OSMnx (add_edge_speeds +
add_edge_travel_times) when available. If not available,
they are computed from edge length and mode speed.

**Directionality:**
- Walk: 100% bidirectional (OSMnx default)
- Bike: 100% bidirectional by design — in an emergency
  context cyclists ignore oneway restrictions. Missing
  reverse edges are added explicitly after download.
- Car: respects oneway restrictions (OSMnx default)

---

## 3. Base Accessibility Logic

Accessibility per mode is determined by the OSMnx network
download rather than by manual tag evaluation.

- An edge has can_walk=True if it appears in the walk network
- An edge has can_bike=True if it appears in the bike network
- An edge has can_drive=True if it appears in the drive network

OSMnx applies the standard OSM access rules for each mode
internally, including foot, bicycle, vehicle, motor_vehicle,
access and oneway tags.

The result is a set of mode-specific attributes per edge:
- can_walk, can_bike, can_drive
- walk_forward, walk_backward (all True for walk and bike)
- drive_forward, drive_backward (respects oneway for car)

---

## 4. Network Output

The merged unified graph is the final network. No enrichment
step is applied.

The graph is cached locally as hamburg_graph.pkl and used
directly for all routing queries.

---

## 5. Graph Topology Validation

Topology validation is performed on the unified graph to
confirm that the network is sufficiently connected for
emergency routing.

The key metric is the giant weakly connected component —
the largest subgraph where any node can reach any other
node ignoring edge direction. For emergency routing, we
require that the vast majority of active nodes belong to
this component.

**Results — unified OSMnx graph:**

| Metric                              | Value     |
|-------------------------------------|-----------|
| Total nodes                         | 658,009   |
| Total edges                         | 1,472,241 |
| can_walk edges                      | 94.5%     |
| can_bike edges                      | 98.2%     |
| can_drive edges                     | 43.9%     |
| AED nodes integrated                | 139       |

Topology validation confirms that the unified graph is
well-connected and suitable for emergency routing across
Hamburg.

---

## 6. AED Nodes in the Graph

AED locations are integrated as permanent nodes in the unified
graph. Each AED is added as a node with
node_key = "aed_{osm_id}" and connected to its nearest
graph node via a bidirectional access edge.

**Access edge properties:**
- Length: Euclidean distance between AED and nearest node (metres)
- Travel time: length / WALK_SPEED_M_S (seconds)
- can_walk = True, can_bike = True, can_drive = False
- Geometry: straight line between AED and nearest node,
  oriented in direction of travel (forward and backward)

**Result:**
- AED nodes added: 139
- AED nodes skipped (beyond MAX_SNAP_DISTANCE_M or 
  outside giant component): 2
- Graph nodes after integration: 658,009
- Graph edges after integration: 1,472,241

**Advantage over runtime snapping:**
Integrating AEDs permanently into the graph means:
- Access edge cost is included in the total route cost
- Access edge geometry is drawn as part of the route
- No special-case logic needed at query time

**Giant component constraint:**
AED nodes are snapped only to nodes within the giant weakly
connected component of the unified graph. This ensures that
every AED node is reachable from any origin point in the main
network. Nodes in small isolated components are excluded from
the snap candidates even if they are within MAX_SNAP_DISTANCE_M.

---

## 7. Caching Strategy

The project uses local caching to avoid unnecessary recomputation.

The following layers are stored locally:

- AED locations (data/processed/hamburg_aeds.geojson)
- Hamburg administrative boundary (data/processed/hamburg_boundary.geojson)
- Unified graph bundle (data/interim/hamburg_graph.pkl)
- Walk isochrones (data/processed/hamburg_isochrones_walk.geojson)

The graph bundle is built once from OSMnx and reused for
all subsequent routing queries. If the bundle is not found,
it is downloaded and built automatically at startup.

---

## 8. Current Status

At this stage, the following components are already defined
and validated:

- OSMnx-based multimodal network download (walk, bike, drive)
- Emergency-context custom filters for all three modes
- Unified multimodal graph construction (single graph, all modes)
- AED nodes integrated as permanent graph nodes with access edges
- AED snap restricted to giant weakly connected component
- Graph topology validated empirically (94.5% walk, 98.2% bike,
  43.9% drive coverage)
- AED and origin snapping (nearest-node, giant component only)
- Candidate selection (K=5 Euclidean prefilter + A* per candidate)
- Route visualisation (green solid + grey dashed alternatives)
- Flask + Leaflet.js web application

The application is served via a Flask development server on
port 5050. The graph bundle is loaded once at startup and
reused for all routing queries.