# Builds the FDTD mesh inside the CSX grid: lines on every edge, a few forced lines in thin dielectrics, then smoothing.

# =========================================
# Imports
# =========================================

import math

from lib.common_functions import calculate_air_region
from lib.support.defines import AXES, LIGHT_SPEED, MESH_GRADING_RATIO, MESH_SNAP_TOLERANCE, MIN_CELLS_PER_DIELECTRIC, MM, PML_CELLS

# =========================================
# Classes and functions
# =========================================

def mesh_builder(csx, params):
    """Fill the CSX grid with mesh lines in mm: lines on every edge, then smoothed so no cell exceeds the max size."""
    max_cell_size = calculate_max_cell_size(params)
    air_region = calculate_air_region(params["boxes"], params["mesh"]["air_margin"], params["frequencies"][0])
    grid = csx.GetGrid()
    grid.SetDeltaUnit(MM)
    for axis in AXES:
        lines = get_edge_lines(params, axis)
        lines += create_dielectric_lines(params, axis, max_cell_size)
        lines += create_boundary_lines(air_region, axis, max_cell_size)
        lines = sorted(set(lines))
        grid.AddLine(axis, lines)
        grid.SmoothMeshLines(axis, max_cell_size, MESH_GRADING_RATIO)
        snap_to_required_lines(grid, axis, lines)
    return csx

def calculate_max_cell_size(params):
    """The largest allowed cell in mm: the shortest wavelength (highest frequency, densest material) over cells_per_wavelength."""
    highest_refractive_index = 1.0
    for material in params["materials"].values():
        if material["type"] == "dielectric":
            refractive_index = math.sqrt(material["epsilon_r"] * material["mu_r"])
            highest_refractive_index = max(highest_refractive_index, refractive_index)
    shortest_wavelength = LIGHT_SPEED / params["frequencies"][-1] / highest_refractive_index / MM
    return shortest_wavelength / params["mesh"]["cells_per_wavelength"]

def get_edge_lines(params, axis):
    """Put a mesh line on both edges of every box, port and near field plane, so FDTD sees each object's exact size.
    openEMS records a near field on the nearest mesh lines, so without them the plane would move (21.6 mm became 22.0)."""
    lines = []
    for item in params["boxes"] + params["ports"]:
        lines += item[axis]
    for near_field in params["monitors"]["near_field"]:
        lines += [near_field[axis][0], near_field[axis][-1]]
    return lines

def create_dielectric_lines(params, axis, max_cell_size):
    """Force at least MIN_CELLS_PER_DIELECTRIC cells across a thin dielectric (like a substrate thickness),
    since smoothing alone would put just one cell there and miss the field inside it."""
    lines = []
    for box in params["boxes"]:
        if params["materials"][box["material"]]["type"] != "dielectric":
            continue
        low, high = box[axis]
        if high - low < MIN_CELLS_PER_DIELECTRIC * max_cell_size:
            cell_size = (high - low) / MIN_CELLS_PER_DIELECTRIC
            for index in range(MIN_CELLS_PER_DIELECTRIC + 1):
                lines.append(low + index * cell_size)
    return lines

def create_boundary_lines(air_region, axis, max_cell_size):
    """Place the outer mesh lines PML_CELLS cells beyond the air region, since openEMS builds the PML in the outermost cells."""
    low, high = air_region[axis]
    pml_size = PML_CELLS * max_cell_size
    return [low - pml_size, high + pml_size]

def snap_to_required_lines(grid, axis, required_lines):
    """SmoothMeshLines rebuilds all lines with float errors (1.6 comes back as 1.6000000000000085), and openEMS drops
    a zero thickness sheet that is off its line by even that much; so every line near a required one is put back on it."""
    snapped_lines = []
    for line in grid.GetLines(axis):
        for required_line in required_lines:
            if abs(line - required_line) < MESH_SNAP_TOLERANCE:
                line = required_line
                break
        snapped_lines.append(line)
    grid.SetLines(axis, snapped_lines)
