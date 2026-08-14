from __future__ import annotations

import hashlib
import logging
from pathlib import Path


def sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """
    Compute the SHA-256 hex digest of a file, reading it in fixed-size
    chunks so the whole file never needs to be held in memory at once.

    Used (Fase 7, 2026-08-14) to tie derived-artifact caches (e.g. the
    giant weakly connected component cache) to the exact graph pickle they
    were computed from, so a future rebuild of the graph (out of scope
    today — the graph is immutable, see Restricción Global 1 — but
    plausible later, e.g. for the car-mode fix) can't silently leave a
    stale cache in place. Measured against the real 364 MB graph pickle
    before writing this: ~0.7s — comparable to the giant-component
    computation itself.
    """
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def setup_logging(level: int = logging.INFO) -> None:
    """
    Set up basic logging without duplicating handlers on repeated calls.
    """
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)