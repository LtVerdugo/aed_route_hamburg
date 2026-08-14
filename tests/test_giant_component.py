"""
Tests para las funciones de componente gigante (src/aed_route/nearest.py).

Añadidos tras la revisión de código de la Fase 7 (2026-08-14, ver
docs/decisions.md): ninguna de estas funciones tenía cobertura automatizada
— solo verificación manual contra el pickle real de producción y los
golden files. Ese hueco es exactamente el mismo tipo de gap que ya se
había señalado y cerrado una fase antes, para `_car_max_speed_m_s`
(tests/test_car_max_speed.py) — se cierra aquí con el mismo criterio.

Los tests de `load_or_compute_giant_component` no requieren el grafo real
de producción ni el pickle de 364 MB: usan grafos sintéticos pequeños y
`tmp_path` de pytest para la caché en disco.
"""
import json

import networkx as nx
import pytest

from aed_route.nearest import (
    compute_giant_component_node_keys,
    filter_node_index_to_keys,
    load_or_compute_giant_component,
)


# ── compute_giant_component_node_keys ──────────────────────────────────


def test_returns_largest_component_only():
    """Grafo con dos componentes de tamaños distintos: debe devolver solo la mayor."""
    G = nx.MultiDiGraph()
    # Componente gigante: a-b-c-d (4 nodos)
    G.add_edge("a", "b", key=0)
    G.add_edge("b", "c", key=0)
    G.add_edge("c", "d", key=0)
    # Componente pequeña, aislada: x-y (2 nodos)
    G.add_edge("x", "y", key=0)

    giant = compute_giant_component_node_keys(G)
    assert giant == {"a", "b", "c", "d"}


def test_weakly_connected_ignores_edge_direction():
    """
    "Weakly connected" es la nocion correcta aqui: dos nodos unidos por una
    sola arista dirigida en un sentido siguen en la misma componente.
    """
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", key=0)  # solo a->b, ninguna arista b->a
    giant = compute_giant_component_node_keys(G)
    assert giant == {"a", "b"}


def test_raises_on_graph_with_no_nodes():
    """Grafo vacio: no hay componente gigante que devolver, debe fallar
    de forma clara en vez de un IndexError/ValueError críptico de max()."""
    G = nx.MultiDiGraph()
    with pytest.raises(ValueError, match="[Nn]o components|no nodes"):
        compute_giant_component_node_keys(G)


# ── filter_node_index_to_keys ───────────────────────────────────────────


def _make_node_index():
    import numpy as np
    from scipy.spatial import cKDTree

    node_keys = np.array([101, 102, "aed_1", 103], dtype=object)
    coords = np.array([[0.0, 0.0], [10.0, 10.0], [20.0, 20.0], [30.0, 30.0]])
    return {"tree": cKDTree(coords), "node_keys": node_keys, "coords": coords}


def test_filter_keeps_only_allowed_keys():
    node_index = _make_node_index()
    allowed = {101, "aed_1"}

    filtered = filter_node_index_to_keys(node_index, allowed)

    assert set(filtered["node_keys"].tolist()) == allowed
    assert filtered["coords"].shape[0] == 2


def test_filter_preserves_key_coord_correspondence():
    """Cada key filtrada debe seguir emparejada con SU coordenada original,
    no con una desplazada por el filtrado."""
    node_index = _make_node_index()
    filtered = filter_node_index_to_keys(node_index, {102})

    assert filtered["node_keys"].tolist() == [102]
    assert filtered["coords"].tolist() == [[10.0, 10.0]]


def test_filter_does_not_mutate_input():
    node_index = _make_node_index()
    original_len = len(node_index["node_keys"])

    filter_node_index_to_keys(node_index, {101})

    assert len(node_index["node_keys"]) == original_len


def test_filter_rebuilds_tree_from_filtered_coords_not_original():
    """El cKDTree devuelto debe responder consultas SOLO sobre el
    subconjunto filtrado — si accidentalmente se devolviera el árbol
    original sin filtrar, esta consulta encontraria un punto excluido."""
    node_index = _make_node_index()
    filtered = filter_node_index_to_keys(node_index, {101})  # solo (0,0)

    # La consulta mas cercana a (30,30) deberia devolver el UNICO punto
    # disponible en el arbol filtrado -- (0,0) -- no (30,30) del original.
    dist, idx = filtered["tree"].query([30.0, 30.0], k=1)
    assert filtered["node_keys"][idx] == 101


# ── load_or_compute_giant_component ─────────────────────────────────────


def _tiny_graph():
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", key=0)
    G.add_edge("b", "c", key=0)
    G.add_edge("x", "y", key=0)  # componente pequena, aislada
    return G


def test_cache_miss_computes_and_writes_cache(tmp_path):
    cache_path = tmp_path / "giant.json"
    G = _tiny_graph()
    all_keys = {"a", "b", "c", "x", "y"}

    giant, excluded, was_cached = load_or_compute_giant_component(
        cache_path=cache_path, G=G, all_node_keys=all_keys,
        graph_pkl_sha256="checksum-v1",
    )

    assert was_cached is False
    assert giant == {"a", "b", "c"}
    assert excluded == {"x", "y"}
    assert cache_path.exists()

    written = json.loads(cache_path.read_text())
    assert written["graph_pkl_sha256"] == "checksum-v1"
    assert set(written["excluded_node_keys"]) == {"x", "y"}


def test_cache_hit_with_matching_checksum_does_not_recompute(tmp_path, monkeypatch):
    cache_path = tmp_path / "giant.json"
    cache_path.write_text(json.dumps({
        "graph_pkl_sha256": "checksum-v1",
        "excluded_node_keys": ["x", "y"],
    }))

    def _boom(G):
        raise AssertionError("no deberia recomputar en un cache hit valido")

    monkeypatch.setattr(
        "aed_route.nearest.compute_giant_component_node_keys", _boom
    )

    all_keys = {"a", "b", "c", "x", "y"}
    giant, excluded, was_cached = load_or_compute_giant_component(
        cache_path=cache_path, G=_tiny_graph(), all_node_keys=all_keys,
        graph_pkl_sha256="checksum-v1",
    )

    assert was_cached is True
    assert giant == {"a", "b", "c"}
    assert excluded == {"x", "y"}


def test_stale_checksum_recomputes(tmp_path):
    cache_path = tmp_path / "giant.json"
    cache_path.write_text(json.dumps({
        "graph_pkl_sha256": "OLD-checksum",
        "excluded_node_keys": ["nonsense", "stale", "data"],
    }))

    G = _tiny_graph()
    all_keys = {"a", "b", "c", "x", "y"}
    giant, excluded, was_cached = load_or_compute_giant_component(
        cache_path=cache_path, G=G, all_node_keys=all_keys,
        graph_pkl_sha256="NEW-checksum",
    )

    assert was_cached is False
    assert giant == {"a", "b", "c"}
    assert excluded == {"x", "y"}
    # el cache en disco tambien se actualiza con el checksum nuevo
    assert json.loads(cache_path.read_text())["graph_pkl_sha256"] == "NEW-checksum"


def test_corrupt_json_does_not_crash_falls_back_to_recompute(tmp_path):
    """
    Regresion directa del hallazgo de la revision de codigo de la Fase 7:
    un archivo de cache corrupto (p. ej. de un proceso matado a mitad de
    escritura) crasheaba el arranque con un JSONDecodeError sin capturar.
    """
    cache_path = tmp_path / "giant.json"
    cache_path.write_text("{not valid json at all")

    G = _tiny_graph()
    all_keys = {"a", "b", "c", "x", "y"}
    giant, excluded, was_cached = load_or_compute_giant_component(
        cache_path=cache_path, G=G, all_node_keys=all_keys,
        graph_pkl_sha256="any-checksum",
    )

    assert was_cached is False
    assert giant == {"a", "b", "c"}
    assert excluded == {"x", "y"}


def test_schema_incomplete_cache_does_not_crash(tmp_path):
    """
    Segunda regresion de la revision de codigo: un cache con JSON valido y
    el checksum correcto, pero SIN excluded_node_keys, lanzaba un KeyError
    sin capturar al intentar usarlo.
    """
    cache_path = tmp_path / "giant.json"
    cache_path.write_text(json.dumps({"graph_pkl_sha256": "checksum-v1"}))

    G = _tiny_graph()
    all_keys = {"a", "b", "c", "x", "y"}
    giant, excluded, was_cached = load_or_compute_giant_component(
        cache_path=cache_path, G=G, all_node_keys=all_keys,
        graph_pkl_sha256="checksum-v1",  # coincide, pero el cache esta incompleto igualmente
    )

    assert was_cached is False
    assert giant == {"a", "b", "c"}
    assert excluded == {"x", "y"}


def test_non_dict_json_root_does_not_crash(tmp_path):
    cache_path = tmp_path / "giant.json"
    cache_path.write_text(json.dumps(["not", "a", "dict"]))

    G = _tiny_graph()
    all_keys = {"a", "b", "c", "x", "y"}
    giant, excluded, was_cached = load_or_compute_giant_component(
        cache_path=cache_path, G=G, all_node_keys=all_keys,
        graph_pkl_sha256="any-checksum",
    )

    assert was_cached is False
    assert giant == {"a", "b", "c"}
