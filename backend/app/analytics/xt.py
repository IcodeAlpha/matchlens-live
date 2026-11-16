"""Expected-threat (xT) lookup on a 16x12 zone grid.

The grid is learned from simulated matches by scripts/build_xt_grid.py, so it
describes the synthetic simulator only. It is NOT derived from real-world data
and must not be presented as a measure of real football.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[2] / 'models'
GRID_PATH = MODELS_DIR / 'xt_grid_16x12.npy'
META_PATH = MODELS_DIR / 'xt_grid_16x12.meta.json'
COLS, ROWS = 16, 12


@lru_cache(maxsize=1)
def _load_grid():
    """Load once per process (the previous version re-read the file per event)."""
    if not GRID_PATH.exists():
        return None
    grid = np.load(GRID_PATH)
    if grid.shape != (COLS, ROWS):
        raise ValueError(f'Expected ({COLS},{ROWS}) xT grid; got {grid.shape}')
    return grid


def reload_grid() -> None:
    _load_grid.cache_clear()


def xt_metadata() -> dict | None:
    """Provenance of the grid (source, number of matches, seeds)."""
    return json.loads(META_PATH.read_text()) if META_PATH.exists() else None


def zone(px: float, py: float) -> tuple[int, int]:
    return (min(max(int(px / 100 * COLS), 0), COLS - 1),
            min(max(int(py / 100 * ROWS), 0), ROWS - 1))


def calculate_xt_gain(x, y, end_x, end_y):
    grid = _load_grid()
    if grid is None:
        return None  # xT unavailable until scripts/build_xt_grid.py has been run
    return round(float(grid[zone(end_x, end_y)]) - float(grid[zone(x, y)]), 5)