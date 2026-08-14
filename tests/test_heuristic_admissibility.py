"""
Test de admisibilidad de la heurística de A* usada en routing.py.

`routing.py` define `heuristic()` como una función interna (closure) dentro
de `find_nearest_aeds` — no es importable de forma aislada sin duplicar
también `_coord_lookup`/`_max_speed_for_mode` y el resto del contexto de la
función. Por eso este test REPLICA la fórmula de la heurística (no la
importa) sobre un mini-grafo sintético propio, no sobre el grafo de
producción.

**Historial (ver docs/decisions.md, Fase 5 y Fase 6, 2026-08-14):**
- Antes de la Fase 6: la heurística real usaba `math.hypot(vx-ux, vy-uy)`
  sin dividir por ninguna velocidad, leyendo además `G.nodes[u]['x'/'y']`
  directamente (grados WGS84 para nodos de carretera, metros EPSG:25832
  para nodos AED — bug de CRS ya documentado como C2). El test original
  demostraba que esa heurística NO era admisible, usando una réplica
  aislada del problema metros-vs-segundos (sin mezclar el bug de CRS).
- Tras la Fase 6: la heurística real divide la distancia (leída de
  `nodes_df`, nunca de `G.nodes[...]`) por la velocidad MÁXIMA del modo.
  Este archivo se actualizó para replicar la fórmula corregida — si se
  vuelve a tocar `routing.py:heuristic`, sincronizar esta réplica también.

Nota de alcance: esta réplica aísla específicamente el problema
metros-vs-segundos. NO reproduce el bug de CRS (C2, ya corregido en la
Fase 6 leyendo de `nodes_df`) porque no hace falta mezclar ambos para
probar que la fórmula division-por-velocidad-máxima es, en sí misma,
admisible.
"""
import math

import networkx as nx

from aed_route.config import WALK_SPEED_M_S


def fixed_heuristic(G, u, v, speed_m_s=WALK_SPEED_M_S):
    """
    Réplica de la heurística de `routing.py:find_nearest_aeds` TRAS el fix
    de la Fase 6: distancia en metros dividida por la velocidad MÁXIMA del
    modo (no la media), para que quede en la misma unidad que el peso de
    A* (segundos) sin perder admisibilidad — ver `routing.py`,
    `_MAX_SPEED_M_S` y el comentario que lo acompaña, para la
    justificación completa.
    """
    ux, uy = G.nodes[u]["x"], G.nodes[u]["y"]
    vx, vy = G.nodes[v]["x"], G.nodes[v]["y"]
    return math.hypot(vx - ux, vy - uy) / speed_m_s


def true_min_cost(G, source, target, weight="cost_s"):
    """Coste real mínimo (Dijkstra puro, sin heurística) — referencia de verdad."""
    return nx.shortest_path_length(G, source, target, weight=weight)


def _degree1_aed_like_graph():
    """
    Grafo sintético: nodos con coordenadas en METROS (el bug de CRS, C2, ya
    está corregido en `routing.py` desde la Fase 6 — no hace falta
    reproducirlo aquí), coste de arista en SEGUNDOS (distancia_m /
    WALK_SPEED_M_S, igual que las aristas de acceso reales de
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


def test_fixed_heuristic_is_admissible_for_degree1_destination():
    """
    Verde esperado tras la Fase 6. La heurística corregida divide la
    distancia por `WALK_SPEED_M_S`, igual que el coste real de cada arista
    — por la desigualdad triangular, la distancia en línea recta hasta el
    destino nunca supera la distancia acumulada del camino real, así que
    h(n) = distancia_recta/v <= distancia_camino/v = coste_real(n) para
    todo nodo. Antes de la Fase 6 esta misma comprobación fallaba (ver
    `docs/decisions.md`, Fase 5): la heurística devolvía la distancia en
    metros sin dividir por velocidad, y por tanto sobreestimaba.
    """
    G = _degree1_aed_like_graph()
    for node in G.nodes:
        if node == "dest":
            continue
        h = fixed_heuristic(G, node, "dest")
        real = true_min_cost(G, node, "dest")
        assert h <= real, (
            f"Heurística inadmisible en nodo '{node}': h={h:.2f} > "
            f"coste_real_mínimo={real:.2f} (viola h(n) <= h*(n))"
        )


def test_degree2_destination_now_returns_true_optimum_after_fase6_fix():
    """
    Antes de la Fase 6 (ver historial de commits y `docs/decisions.md`),
    este mismo escenario — un nodo destino con grado de entrada 2, algo que
    no ocurre hoy con los AEDs reales pero que sí podría pasar si se
    implementara mal la opción (iv) del modo car — hacía que
    `nx.astar_path` devolviera una ruta SUBÓPTIMA: coste 1050 (vía P1) en
    vez del óptimo real, 1010 (vía P2), sin ningún error ni aviso. Ese
    comportamiento estaba documentado como un bug conocido, no como algo
    correcto.

    Tras el fix de la Fase 6 (heurística dividida por velocidad máxima),
    verificado empíricamente antes de aplicar el fix a `routing.py`: este
    mismo escenario pasa a devolver el óptimo real, 1010. Este test ahora
    exige ese óptimo — si en el futuro alguien reintroduce una heurística
    no admisible y este test empieza a fallar devolviendo de nuevo un coste
    mayor que 1010, es la señal de una regresión real, no una mejora.
    """
    G = nx.DiGraph()
    G.add_node("origin", x=500.0, y=500.0)
    G.add_node("P1", x=999.0, y=1000.0)  # cerca del destino -> h pequeño
    G.add_node("P2", x=0.0, y=0.0)  # lejos del destino -> h grande
    G.add_node("dest", x=1000.0, y=1000.0)  # grado de entrada 2

    G.add_edge("origin", "P1", cost_s=1000.0)  # llegada lenta a P1
    G.add_edge("P1", "dest", cost_s=50.0)  # antes de la Fase 6: P1 ganaba (1050)
    G.add_edge("origin", "P2", cost_s=10.0)  # llegada rápida a P2
    G.add_edge("P2", "dest", cost_s=1000.0)  # tras la Fase 6: P2 gana (1010, el óptimo real)
    assert G.in_degree("dest") == 2

    def true_cost(path):
        return sum(G[u][v]["cost_s"] for u, v in zip(path[:-1], path[1:]))

    cost_via_p1 = true_cost(["origin", "P1", "dest"])
    cost_via_p2 = true_cost(["origin", "P2", "dest"])
    true_optimum = min(cost_via_p1, cost_via_p2)
    assert true_optimum == 1010.0  # vía P2 — sigue siendo el óptimo real del grafo

    def h(u, v):
        return fixed_heuristic(G, u, v)

    returned_path = nx.astar_path(G, "origin", "dest", heuristic=h, weight="cost_s")
    returned_cost = true_cost(returned_path)

    assert returned_cost == true_optimum, (
        "Se esperaba que, tras el fix de la Fase 6, este escenario devolviera "
        f"el óptimo real ({true_optimum}); devolvió {returned_cost}. Antes de "
        "la Fase 6 devolvía 1050 (subóptimo) — si esto vuelve a fallar con un "
        "coste mayor que el óptimo, es una regresión real, investígala antes "
        "de tocar nada más."
    )
