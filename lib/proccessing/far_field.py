# Calculates one far field monitor: transforms the recorded NF2FF box fields to the far field on the theta / phi grid.

# =========================================
# Imports
# =========================================

import numpy as np

from lib.common_functions import calculate_bounding_box
from lib.support.defines import AXES, MM

# =========================================
# Classes and functions
# =========================================

def far_field(nf2ff, params, far_field_monitor, field_scale, paths):
    """Calculate E_theta, E_phi (at 1 m, scaled to the normalized incident power) and the directivity of one
    far field monitor, from the run where its port is excited."""
    sim_path = paths["sim"] / far_field_monitor["port"]
    center = calculate_phase_center(params)
    result = nf2ff.CalcNF2FF(str(sim_path), far_field_monitor["frequency"], far_field_monitor["theta"],
                             far_field_monitor["phi"], center = center, outfile = f"{far_field_monitor['name']}.h5")
    far_field_result = {
        "theta": far_field_monitor["theta"],
        "phi": far_field_monitor["phi"],
        "e_theta": result.E_theta[0] * field_scale,
        "e_phi": result.E_phi[0] * field_scale,
        "directivity_dbi": calculate_directivity(result),
    }
    return far_field_result

def calculate_phase_center(params):
    """Use the model's center as the phase center, in meters; it only changes the phase of E, not its magnitude."""
    bounding_box = calculate_bounding_box(params["boxes"])
    center = []
    for axis in AXES:
        center.append((bounding_box[axis][0] + bounding_box[axis][1]) / 2 * MM)
    return center

def calculate_directivity(result):
    """Directivity in dBi on the grid: the normalized |E| pattern in dB, lifted so its peak equals the max directivity Dmax."""
    e_norm = result.E_norm[0]
    return 20 * np.log10(e_norm / np.max(e_norm)) + 10 * np.log10(result.Dmax[0])
