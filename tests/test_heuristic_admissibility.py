"""
Test de admisibilidad de la heurística de A* usada en routing.py.

`routing.py` define `heuristic()` como una función interna (closure) dentro
de `find_nearest_aeds` — no es importable de forma aislada sin tocar ese
archivo, lo cual está prohibido en la Fase 5 (arnés de verificación, sin
correcciones — ver docs/superpowers/plans/2026-08-14-audit-remediation.md).

Por eso este test REPLICA la fórmula exacta de la heurística actual
(routing.py, hoy: `math.hypot(vx - ux, vy - uy)`, leyendo `G.nodes[u]['x'/'y']`
directamente) sobre un mini-grafo sintético propio, no sobre el grafo de
producción. Cuando la Fase 6 corrija esa heurística, este test debe
actualizarse para importar/ejercer la función real en vez de esta copia —
ver `docs/decisions.md`, entrada de la Fase 6.

Nota de alcance: esta réplica aísla específicamente el problema
metros-vs-segundos (distancia en metros comparada directamente con un coste
en segundos). NO reproduce el otro bug ya documentado (C2: nodos de
carretera en grados WGS84 frente a nodos AED en metros EPSG:25832) — ese es
un problema de qué CRS usa cada nodo, no de qué unidad usa la propia fórmula
de la heurística, y no es necesario mezclarlos para demostrar que la fórmula
en sí, incluso con coordenadas ya proyectadas de forma consistente, sigue
siendo inadmisible frente a un peso en segundos.
"""
import math

import networkx as nx

from aed_route.config import WALK_SPEED_M_S


def current_heuristic(G, u, v):
    """Réplica exacta de la heurística de `routing.py:find_nearest_aeds` (hoy)."""
    ux, uy = G.nodes[u]["x"], G.nodes[u]["y"]
    vx, vy = G.nodes[v]["x"], G.nodes[v]["y"]
    return math.hypot(vx - ux, vy - uy)


def true_min_cost(G, source, target, weight="cost_s"):
    """Coste real mínimo (Dijkstra puro, sin heurística) — referencia de verdad."""
    return nx.shortest_path_length(G, source, target, weight=weight)


def _degree1_aed_like_graph():
    """
    Grafo sintético: nodos con coordenadas en METROS (no en grados WGS84 —
    ese es el bug C2/CRS, ya documentado por separado; este test aísla
    específicamente metros-vs-segundos), coste de arista en SEGUNDOS
    (distancia_m / WALK_SPEED_M_S, igual que las aristas de acceso reales de
    `graph_builder_osm.py`), y un nodo destino de grado de entrada 1 (una
    sola arista de acceso), imitando la topología real de un nodo AED.
    """
    G = nx.DiGraph()
    G.add_node("origin", x=0.0, y=0.0)
    G.add_node("mid", x=100.0, y=0.0)
    G.add_node("dest", x=100.0, y=100.0)  # "AED": grado de entrada 1

    def cost(a, b):
        ax, ay = G.nodes[a]["x"], G.nodes[a]["y"]
        bx, by = G.nodes[b]["x"], G.nodes[b]["y"]
        return math.hypot(bx - ax, by - ay) / WALK_SPEED_M_S

    G.add_edge("origin", "mid", cost_s=cost("origin", "mid"))
    G.add_edge("mid", "dest", cost_s=cost("mid", "dest"))
    assert G.in_degree("dest") == 1
    return G


def test_current_heuristic_is_not_admissible_for_degree1_destination():
    """
    RED esperado contra la implementación actual. La heurística devuelve la
    distancia en metros en bruto, pero el peso de A* (`cost_s`) está en
    SEGUNDOS. Con `WALK_SPEED_M_S` > 1 m/s, la distancia en metros siempre
    supera al coste real mínimo en segundos para cualquier arista de
    longitud > 0 — la heurística sobreestima, es decir, es inadmisible
    (viola h(n) <= h*(n)).
    """
    G = _degree1_aed_like_graph()
    for node in G.nodes:
        if node == "dest":
            continue
        h = current_heuristic(G, node, "dest")
        real = true_min_cost(G, node, "dest")
        assert h <= real, (
            f"Heurística inadmisible en nodo '{node}': h={h:.2f} > "
            f"coste_real_mínimo={real:.2f} (viola h(n) <= h*(n))"
        )


def test_degree2_destination_CURRENTLY_returns_suboptimal_path_BUG_DOCUMENTED():
    """
    ⚠️ ESTE TEST PASA HOY PORQUE DOCUMENTA UN BUG, NO PORQUE EL COMPORTAMIENTO
    SEA CORRECTO. No leerlo al revés.

    Demuestra, de forma concreta y reproducible (no un caso hipotético), que
    si un nodo destino tuviera grado de entrada 2 en vez del grado 1 real de
    los AEDs de hoy, la heurística actual haría que `nx.astar_path` devuelva
    una ruta SUBÓPTIMA (coste 1050) en vez del óptimo real (coste 1010), sin
    ningún error ni aviso.

    **Cuando la Fase 6 corrija la heurística, este mismo escenario debería
    empezar a devolver 1010 (el óptimo) — y por tanto este test DEBE EMPEZAR
    A FALLAR.** Esa es la señal correcta de que el fix funciona: una MEJORA,
    no una regresión.

    Si esto pasa: NO "arregles" el test bajando la expectativa para que
    siga aceptando 1050 — eso congelaría el bug. En su lugar, actualiza la
    aserción para exigir el óptimo (1010) y deja en el docstring constancia
    de que antes de la Fase 6 devolvía 1050. Ver docs/decisions.md, entrada
    de la Fase 6, para el registro de este cambio de comportamiento.

    Sirve además de guardarraíl de regresión permanente: si en el futuro se
    conecta un AED a más de un nodo de acceso (p. ej. la opción (iv) del
    modo car — ver docs/decisions.md), este es exactamente el escenario que
    podría romper la garantía de optimalidad en silencio si la heurística
    volviera a quedar mal calibrada.
    """
    G = nx.DiGraph()
    G.add_node("origin", x=500.0, y=500.0)
    G.add_node("P1", x=999.0, y=1000.0)  # cerca del destino -> h pequeño
    G.add_node("P2", x=0.0, y=0.0)  # lejos del destino -> h grande
    G.add_node("dest", x=1000.0, y=1000.0)  # grado de entrada 2

    G.add_edge("origin", "P1", cost_s=1000.0)  # llegada lenta a P1
    G.add_edge("P1", "dest", cost_s=50.0)
    G.add_edge("origin", "P2", cost_s=10.0)  # llegada rápida a P2
    G.add_edge("P2", "dest", cost_s=1000.0)
    assert G.in_degree("dest") == 2

    def true_cost(path):
        return sum(G[u][v]["cost_s"] for u, v in zip(path[:-1], path[1:]))

    cost_via_p1 = true_cost(["origin", "P1", "dest"])
    cost_via_p2 = true_cost(["origin", "P2", "dest"])
    true_optimum = min(cost_via_p1, cost_via_p2)

    def h(u, v):
        return current_heuristic(G, u, v)

    returned_path = nx.astar_path(G, "origin", "dest", heuristic=h, weight="cost_s")
    returned_cost = true_cost(returned_path)

    # Referencia: Dijkstra puro (sin heurística) SÍ encuentra el óptimo real.
    dijkstra_path = nx.astar_path(G, "origin", "dest", weight="cost_s")
    assert true_cost(dijkstra_path) == true_optimum

    # La demostración: la heurística actual devuelve una ruta más cara que
    # el óptimo real, en un grafo donde Dijkstra sí acierta.
    assert returned_cost > true_optimum, (
        "Se esperaba reproducir la subóptimalidad silenciosa del grado 2; "
        f"si esto falla, el escenario ya no reproduce el riesgo documentado "
        f"(devolvió coste {returned_cost}, óptimo real {true_optimum})"
    )
