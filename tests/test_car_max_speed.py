"""
Tests para `_car_max_speed_m_s` (src/aed_route/routing.py).

Añadidos tras la revisión de código de la Fase 6 (2026-08-14, ver
docs/decisions.md): a diferencia de walk/bike, que usan constantes de
config.py ya verificadas, la velocidad máxima de car se MIDE del grafo
cargado con una lógica propia (filtrar can_drive=True, calcular
length_m/drive_cost_s, tomar el máximo) que no tenía ninguna cobertura de
test — solo se había verificado manualmente contra el pickle real de
producción. A diferencia de la heurística en sí, `_car_max_speed_m_s` SÍ es
una función de módulo importable directamente (no una closure), así que
estos tests importan la función real, no una réplica.
"""
import networkx as nx
import pytest

from aed_route.routing import _car_max_speed_m_s, _car_max_speed_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    """Cada test parte de una caché limpia — la caché real está keyed por
    id(G), y cada test construye su propio grafo nuevo, pero por si algún
    id() se reciclara entre tests (posible en CPython), se limpia también
    explícitamente antes y después de cada test."""
    _car_max_speed_cache.clear()
    yield
    _car_max_speed_cache.clear()


def test_measures_max_among_heterogeneous_drivable_speeds():
    """Debe devolver el máximo real, no la media ni el mínimo."""
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", key=0, can_drive=True, length_m=100.0, drive_cost_s=10.0)  # 10 m/s
    G.add_edge("b", "c", key=0, can_drive=True, length_m=300.0, drive_cost_s=10.0)  # 30 m/s
    G.add_edge("c", "d", key=0, can_drive=True, length_m=50.0, drive_cost_s=25.0)   # 2 m/s

    assert _car_max_speed_m_s(G) == pytest.approx(30.0)


def test_ignores_edges_where_can_drive_is_not_true():
    """
    Una arista con una velocidad enorme pero can_drive=False (p. ej. una
    arista de acceso a AED, o una vía peatonal) no debe contaminar el
    máximo — solo cuentan las aristas realmente drivables.
    """
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", key=0, can_drive=True, length_m=100.0, drive_cost_s=10.0)  # 10 m/s
    G.add_edge("x", "y", key=0, can_drive=False, length_m=1000.0, drive_cost_s=1.0)  # 1000 m/s, pero no cuenta
    # can_drive ausente por completo (p. ej. arista sin ese atributo)
    G.add_edge("p", "q", key=0, length_m=500.0, drive_cost_s=0.1)  # 5000 m/s, pero no cuenta

    assert _car_max_speed_m_s(G) == pytest.approx(10.0)


def test_ignores_edges_with_zero_or_missing_cost_or_length():
    """
    Aristas con length_m o drive_cost_s nulos, ausentes o <= 0 no deben
    provocar una división por cero ni contaminar el máximo con infinito.
    """
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", key=0, can_drive=True, length_m=100.0, drive_cost_s=10.0)  # 10 m/s, único válido
    G.add_edge("b", "c", key=0, can_drive=True, length_m=0.0, drive_cost_s=5.0)      # length_m=0
    G.add_edge("c", "d", key=0, can_drive=True, length_m=100.0, drive_cost_s=0.0)    # drive_cost_s=0
    G.add_edge("d", "e", key=0, can_drive=True, length_m=None, drive_cost_s=5.0)     # length_m None
    G.add_edge("e", "f", key=0, can_drive=True, length_m=100.0, drive_cost_s=None)   # drive_cost_s None

    assert _car_max_speed_m_s(G) == pytest.approx(10.0)


def test_raises_value_error_when_no_drivable_edges_exist():
    """
    Grafo sin ninguna arista can_drive=True válida: debe fallar de forma
    ruidosa (ValueError), no devolver 0 ni None en silencio, que rompería
    la heurística (división por cero) de forma mucho más confusa aguas
    abajo. Cubre explícitamente el escenario que la revisión de código de
    la Fase 6 señaló como no probado.
    """
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", key=0, can_drive=False, length_m=100.0, drive_cost_s=10.0)
    G.add_edge("b", "c", key=0, can_walk=True, length_m=50.0, walk_cost_s=30.0)

    with pytest.raises(ValueError, match="velocidad máxima válida"):
        _car_max_speed_m_s(G)


def test_caches_per_graph_object_not_globally():
    """
    La caché está keyed por id(G) (corregido tras la revisión de código de
    la Fase 6 — antes era una única variable global sin keying, lo que
    habría devuelto silenciosamente la velocidad de OTRO grafo si alguna
    vez se cargara más de un bundle en el mismo proceso). Dos grafos
    distintos con velocidades máximas distintas deben devolver cada uno la
    suya, no la del primero calculado.
    """
    G1 = nx.MultiDiGraph()
    G1.add_edge("a", "b", key=0, can_drive=True, length_m=100.0, drive_cost_s=10.0)  # 10 m/s

    G2 = nx.MultiDiGraph()
    G2.add_edge("x", "y", key=0, can_drive=True, length_m=500.0, drive_cost_s=10.0)  # 50 m/s

    speed1 = _car_max_speed_m_s(G1)
    speed2 = _car_max_speed_m_s(G2)

    assert speed1 == pytest.approx(10.0)
    assert speed2 == pytest.approx(50.0)
    # Repetir la consulta al primer grafo debe seguir dando su propio valor,
    # no el del segundo (confirma que la caché no se pisó entre ambos).
    assert _car_max_speed_m_s(G1) == pytest.approx(10.0)
