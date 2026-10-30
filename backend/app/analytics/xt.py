from pathlib import Path
import numpy as np
GRID_PATH = Path(__file__).resolve().parents[2] / 'models' / 'xt_grid_16x12.npy'

def calculate_xt_gain(x, y, end_x, end_y):
    if not GRID_PATH.exists():
        return None  # xT is optional until the existing trained grid is copied
    grid = np.load(GRID_PATH)
    if grid.shape != (16,12):
        raise ValueError(f'Expected (16,12) xT grid; got {grid.shape}')
    def value(px, py):
        return float(grid[min(int(px/100*16),15), min(int(py/100*12),11)])
    return round(value(end_x,end_y)-value(x,y),5)
