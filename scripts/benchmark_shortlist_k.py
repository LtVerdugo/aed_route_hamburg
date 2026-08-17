"""
Benchmark de coste de SHORTLIST_EUCLIDEAN_K en find_nearest_aeds (Ítem 8A(6)).

Uso:
    .venv/bin/python3 scripts/benchmark_shortlist_k.py
    .venv/bin/python3 scripts/benchmark_shortlist_k.py --k-values 3 5 --repeat 2
    .venv/bin/python3 scripts/benchmark_shortlist_k.py --modes walk bike --repeat 5

Mide el coste real llamando DIRECTAMENTE a find_nearest_aeds (no vía HTTP),
pasando k explícitamente por parámetro — así el resultado nunca depende de
SHORTLIST_EUCLIDEAN_K en config.py ni de si un servidor vivo llegó a cargar
esa constante. Esto evita a propósito el falso negativo de proceso
documentado en docs/decisions.md (Ítem 8A(2)): un servidor uvicorn sin
--reload sigue sirviendo con la config vieja tras editar config.py, y una
medición contra un servidor así da números con apariencia de válidos que en
realidad no corresponden al k pedido.

Usa los mismos 9 orígenes que scripts/generate_golden_routes.py (import
directo de CASES desde ese módulo, no una copia — evita que ambos listados
de orígenes diverjan con el tiempo).

Aviso de coste: con car (y con algunos orígenes aislados en cualquier modo),
cada candidato euclídeo-cercano-pero-inalcanzable exige que A* explore buena
parte del componente conexo antes de descartarlo por NetworkXNoPath — ver el
hallazgo abierto correspondiente en docs/decisions.md (Ítem 8A(2)). Con los
valores por defecto (k=3,5 · 3 modos · 9 orígenes · repeat=2) el benchmark
completo puede tardar más de un minuto por los orígenes aislados en car.

Nace de un hallazgo Minor de requesting-code-review sobre el Ítem 8A(2): las
cifras de latencia que sustentan el hallazgo abierto de candidatos
inalcanzables no eran reproducibles sin repetir el experimento a mano. Este
script las hace reproducibles.
"""
from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_golden_routes import CASES  # noqa: E402

from aed_route.config import AEDS_CACHE_REL_PATH, GRAPH_CACHE_REL_PATH  # noqa: E402
from aed_route.io import read_json  # noqa: E402
from aed_route.nearest import (  # noqa: E402
    build_aed_index,
    build_node_index,
    compute_giant_component_node_keys,
    filter_node_index_to_keys,
)
from aed_route.routing import find_nearest_aeds  # noqa: E402

MODES = ("walk", "bike", "car")


def load_bundle_and_indexes():
    """Carga el pickle del grafo (solo lectura) y construye los índices
    igual que app.py al arrancar: node_index filtrado al componente gigante
    (Fase 7) y aed_index. No muta nada del bundle."""
    with open(PROJECT_ROOT / GRAPH_CACHE_REL_PATH, "rb") as f:
        bundle = pickle.load(f)
    nodes_df = bundle["nodes_df"]
    node_index_unfiltered = build_node_index(nodes_df)
    giant = compute_giant_component_node_keys(bundle["graph"])
    node_index = filter_node_index_to_keys(node_index_unfiltered, giant)
    aeds_fc = read_json(PROJECT_ROOT / AEDS_CACHE_REL_PATH)
    aed_index = build_aed_index(aeds_fc, nodes_df)
    return bundle, node_index, aed_index


def run(k_values: list[int], modes: list[str], repeat: int) -> dict:
    bundle, node_index, aed_index = load_bundle_and_indexes()

    per_case: dict[tuple[str, int, str], float] = {}
    for mode in modes:
        for k in k_values:
            for case in CASES:
                total = 0.0
                for _ in range(repeat):
                    t0 = time.perf_counter()
                    find_nearest_aeds(
                        case["lon"], case["lat"], mode, bundle, aed_index,
                        k=k, node_index=node_index,
                    )
                    total += time.perf_counter() - t0
                avg_s = total / repeat
                per_case[(mode, k, case["id"])] = avg_s
                print(f"  {mode:5s} k={k}  {case['id']:24s} avg={avg_s * 1000:8.1f} ms")

    print()
    print(f"{'modo':5s} {'k':>3s} {'promedio (ms)':>15s}")
    for mode in modes:
        for k in k_values:
            vals = [per_case[(mode, k, c["id"])] for c in CASES]
            avg_ms = sum(vals) / len(vals) * 1000
            print(f"{mode:5s} {k:3d} {avg_ms:15.2f}")

    if len(k_values) >= 2:
        print()
        k_lo, k_hi = min(k_values), max(k_values)
        for mode in modes:
            avg_lo = sum(per_case[(mode, k_lo, c["id"])] for c in CASES) / len(CASES) * 1000
            avg_hi = sum(per_case[(mode, k_hi, c["id"])] for c in CASES) / len(CASES) * 1000
            delta = avg_hi - avg_lo
            pct = (delta / avg_lo * 100) if avg_lo > 0 else float("nan")
            print(
                f"{mode:5s}  K{k_lo}={avg_lo:.2f}ms  K{k_hi}={avg_hi:.2f}ms  "
                f"delta={delta:+.2f}ms ({pct:+.1f}%)"
            )

    return per_case


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k-values", type=int, nargs="+", default=[3, 5])
    ap.add_argument("--modes", nargs="+", default=list(MODES), choices=MODES)
    ap.add_argument("--repeat", type=int, default=2)
    args = ap.parse_args()
    run(args.k_values, args.modes, args.repeat)


if __name__ == "__main__":
    main()
