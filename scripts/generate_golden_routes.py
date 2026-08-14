"""
Genera los golden files de /api/route para el arnés de regresión (Fase 5).

Uso:
    .venv/bin/python3 scripts/generate_golden_routes.py [--port 5000]

Arranca uvicorn como subproceso, espera a /healthz, llama a POST /api/route
para cada caso x modo, y escribe un JSON por caso en tests/golden/. Escribe
también tests/golden/MANIFEST.json con el hash del commit usado para
generar el baseline (Restricción del usuario, 2026-08-14).

Cada caso incluye una EXPECTATIVA explícita para la Fase 7 (componente
gigante, snapping de origen), documentada ANTES de que esa fase se ejecute
— así el diff de la Fase 7 se lee contra una predicción escrita de
antemano, no contra una interpretación a posteriori. Los orígenes, sus
mediciones de snap/componente y el porqué de cada expectativa están
registrados en docs/decisions.md (Fase 5, 2026-08-14) — no se repiten aquí
en detalle, solo la conclusión operativa.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"
MODES = ("walk", "bike", "car")

# ── Casos ──────────────────────────────────────────────────────────────
# expectation_fase7 ∈ {"no_change", "expected_change", "expected_improvement"}
CASES = [
    {
        "id": "dense_urban",
        "description": "Centro urbano denso (Rathaus)",
        "lat": 53.5503,
        "lon": 9.9927,
        "expectation_fase7": "no_change",
        "expectation_reason": (
            "Origen en el componente gigante hoy; walk/bike ya devuelven "
            "resultado. Car=0 es el fallo estructural conocido (C_car), no "
            "relacionado con el filtro de componente gigante de la Fase 7 — "
            "no debería cambiar por esa fase."
        ),
    },
    {
        "id": "boundary_edge",
        "description": "Borde real de Hamburgo (Bergedorf, límite este)",
        "lat": 53.4890,
        "lon": 10.2100,
        "expectation_fase7": "no_change",
        "expectation_reason": (
            "Snap a 23.0 m, dentro del componente gigante — funciona hoy "
            "igual que dense_urban. Confirma que la periferia real del área "
            "de servicio no tiene el problema que ataca la Fase 7."
        ),
    },
    {
        "id": "clausewitz_kaserne",
        "description": "Zona militar Clausewitz-Kaserne (documentada en routing_methodology.md)",
        "lat": 53.5624,
        "lon": 9.8327,
        "expectation_fase7": "no_change",
        "expectation_reason": (
            "Verificado (Fase 5, 2026-08-14): NO hay ningún nodo a <=100 m de "
            "este punto exacto — el snap ya falla hoy antes de llegar a "
            "elegir ningún componente. El nodo del componente gigante más "
            "cercano está a 164.8 m, fuera de MAX_SNAP_DISTANCE_M incluso "
            "tras el filtro de la Fase 7. Seguirá vacío."
        ),
    },
    {
        "id": "water_point",
        "description": "Elba, canal sur del puerto entre Neuhof y Waltershof",
        "lat": 53.5080,
        "lon": 9.9350,
        "expectation_fase7": "no_change",
        "expectation_reason": (
            "Verificado midiendo (no asumido por geografía — el Elba tiene "
            "muelles/ferris mapeados que sí snapean): distancia real al nodo "
            "más cercano = 236.4 m, muy por encima de MAX_SNAP_DISTANCE_M. "
            "Sin snap antes ni después de la Fase 7."
        ),
    },
    {
        "id": "isolated_stays_empty_a",
        "description": "Componente aislada A (149 nodos, fuera del componente gigante)",
        "lat": 53.577362,
        "lon": 9.881057,
        "expectation_fase7": "no_change",
        "expectation_reason": (
            "Snapea hoy (dist. 0 m) a un nodo fuera del componente gigante "
            "general. El nodo gigante real más cercano está a 186.4 m — "
            "fuera de MAX_SNAP_DISTANCE_M incluso tras el filtro de la Fase 7. "
            "Seguirá vacío en los 3 modos: es un caso de aislamiento genuino, "
            "no solo un snap mal filtrado."
        ),
    },
    {
        "id": "isolated_stays_empty_b",
        "description": "Componente aislada B (130 nodos, fuera del componente gigante)",
        "lat": 53.536808,
        "lon": 9.918439,
        "expectation_fase7": "no_change",
        "expectation_reason": (
            "Igual mecanismo que isolated_stays_empty_a. Nodo gigante más "
            "cercano a 342.3 m — sigue sin snap tras la Fase 7."
        ),
    },
    {
        "id": "isolated_flip_c",
        "description": "Componente aislada C (fuera del gigante, pero con nodo gigante a 6.4 m)",
        "lat": 53.576829,
        "lon": 9.884691,
        "expectation_fase7": "expected_change",
        "expectation_reason": (
            "Hoy: 0 resultados en los 3 modos (snapea fuera del componente "
            "gigante). El nodo del componente gigante real está a solo 6.4 m "
            "— tras el filtro de origen de la Fase 7, el snap debería caer "
            "ahí en vez de en el nodo aislado, y el resultado debería pasar "
            "de vacío a con ruta (al menos en walk/bike). Si este golden NO "
            "cambia tras la Fase 7, el filtro no está funcionando."
        ),
    },
    {
        "id": "isolated_flip_d",
        "description": "Componente aislada D (fuera del gigante, pero con nodo gigante a 43.9 m)",
        "lat": 53.557148,
        "lon": 9.960321,
        "expectation_fase7": "expected_change",
        "expectation_reason": (
            "Igual mecanismo que isolated_flip_c. Nodo gigante real a 43.9 m "
            "— dentro de MAX_SNAP_DISTANCE_M, debería flipear a resultado."
        ),
    },
    {
        "id": "isolated_partial_e",
        "description": "Componente aislada E (81 nodos; YA tiene 1 resultado parcial en walk hoy)",
        "lat": 53.543155,
        "lon": 10.001129,
        "expectation_fase7": "expected_improvement",
        "expectation_reason": (
            "Caso distinto de los anteriores: hoy YA devuelve 1 resultado en "
            "walk (por conectividad interna de su propia componente aislada "
            "con al menos un AED), pero 0 en bike/car. Nodo del componente "
            "gigante real a solo 14.2 m. Tras la Fase 7 se espera que "
            "MEJORE la calidad/cantidad de candidatos evaluados en walk (no "
            "solo que deje de estar vacío, que ya no lo está), y "
            "posiblemente que bike pase a tener resultado. El golden guarda "
            "la respuesta COMPLETA (no solo el conteo) precisamente para que "
            "la Fase 7 pueda comparar si de verdad mejora la ruta devuelta, "
            "no solo si el conteo sube."
        ),
    },
]


def wait_for_healthz(base_url: str, timeout_s: float = 60.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/healthz", timeout=2)
            if r.status_code == 200 and r.json().get("ok"):
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"El servidor no respondió /healthz en {timeout_s}s")


def fetch_case(base_url: str, case: dict) -> dict:
    results = {}
    for mode in MODES:
        resp = requests.post(
            f"{base_url}/api/route",
            json={"lat": case["lat"], "lon": case["lon"], "mode": mode},
            timeout=30,
        )
        resp.raise_for_status()
        results[mode] = resp.json()
    return results


def generate(base_url: str, case_ids: list[str] | None = None) -> list[str]:
    """Genera (o regenera) los golden files indicados; None = todos. Devuelve
    la lista de ids escritos."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    cases = CASES if case_ids is None else [c for c in CASES if c["id"] in case_ids]
    for case in cases:
        results = fetch_case(base_url, case)
        payload = {
            "case_id": case["id"],
            "description": case["description"],
            "origin": {"lat": case["lat"], "lon": case["lon"]},
            "expectation_fase7": {
                "outcome": case["expectation_fase7"],
                "reason": case["expectation_reason"],
            },
            "results": results,
        }
        out_path = GOLDEN_DIR / f"{case['id']}.json"
        out_path.write_text(
            json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written.append(case["id"])
        counts = ", ".join(
            "%s=%d" % (m, len(results[m].get("results", []))) for m in MODES
        )
        print(f"  {case['id']}: escrito ({counts})")
    return written


def write_manifest():
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True
    ).stdout.strip()
    manifest = {
        "generated_with_commit": commit,
        "generator_script": "scripts/generate_golden_routes.py",
        "case_ids": [c["id"] for c in CASES],
        "note": (
            "Baseline generado ANTES de cualquier fix (Fases 6/7/8). No "
            "editar los .json de tests/golden/ a mano — regenerar con este "
            "script y revisar el diff explícitamente."
        ),
    }
    (GOLDEN_DIR / "MANIFEST.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"MANIFEST.json escrito (commit {commit[:12]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument(
        "--cases", nargs="*", default=None,
        help="IDs de caso a regenerar (por defecto, todos)",
    )
    ap.add_argument(
        "--no-server", action="store_true",
        help="No arrancar un servidor propio; asume que ya hay uno corriendo en --host:--port",
    )
    args = ap.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    proc = None
    try:
        if not args.no_server:
            proc = subprocess.Popen(
                [
                    str(PROJECT_ROOT / ".venv" / "bin" / "uvicorn"),
                    "app.app:app",
                    "--host", args.host,
                    "--port", str(args.port),
                ],
                cwd=PROJECT_ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            wait_for_healthz(base_url)

        written = generate(base_url, args.cases)
        write_manifest()
        print(f"\n{len(written)} caso(s) generado(s): {', '.join(written)}")
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
