# Calculates the summary numbers of the monitors: S_ii resonance and bandwidth, far field peak direction and beamwidths.

# =========================================
# Imports
# =========================================

import numpy as np

from lib.proccessing.far_field import get_far_field_cut
from lib.support.defines import BEAMWIDTH_LEVEL_DB, REFLECTION_BANDWIDTH_LEVEL_DB

# =========================================
# Classes and functions
# =========================================

def calculate_reflection_band(reflection_db, frequencies):
    """Find the resonance (the S_ii notch) and the band around it where S_ii stays under REFLECTION_BANDWIDTH_LEVEL_DB.
    An edge is None when S_ii is still under the level at the sweep end; both are None when the notch never gets under it."""
    notch_index = int(np.argmin(reflection_db))
    band = {
        "frequency": frequencies[notch_index],
        "reflection_db": reflection_db[notch_index],
        "low": None,
        "high": None,
    }
    if reflection_db[notch_index] < REFLECTION_BANDWIDTH_LEVEL_DB:
        band["low"] = find_level_crossing(frequencies, reflection_db, notch_index, -1, REFLECTION_BANDWIDTH_LEVEL_DB)
        band["high"] = find_level_crossing(frequencies, reflection_db, notch_index, 1, REFLECTION_BANDWIDTH_LEVEL_DB)
    return band

def find_far_field_peak(far_field_result):
    """Find the direction (theta, phi in deg) of the max directivity on the grid. At theta = 0 or 180 every phi is
    the same direction, so phi is reported as 0 instead of whichever phi numerical noise picked."""
    directivity = far_field_result["directivity_dbi"]
    theta_index, phi_index = np.unravel_index(np.argmax(directivity), directivity.shape)
    theta = far_field_result["theta"][theta_index]
    phi = far_field_result["phi"][phi_index]
    if theta in (0, 180):
        phi = 0
    peak = {
        "theta": theta,
        "phi": phi,
        "directivity_dbi": directivity[theta_index, phi_index],
    }
    return peak

def calculate_beamwidth(far_field_result, cut_phi):
    """The beamwidth of the main beam in one cut: the angle between the two points where the directivity drops
    BEAMWIDTH_LEVEL_DB under the cut's peak. None when the pattern never drops that far, e.g. a nearly omni cut."""
    angles, cut = get_far_field_cut(far_field_result, cut_phi)
    peak_index = int(np.argmax(cut))
    level = cut[peak_index] + BEAMWIDTH_LEVEL_DB
    low = find_level_crossing(angles, cut, peak_index, -1, level)
    high = find_level_crossing(angles, cut, peak_index, 1, level)
    if low is None or high is None:
        return None
    return high - low

def find_level_crossing(x, y, start_index, step, level):
    """Walk from start_index one point at a time (step -1 goes left, 1 right) until y crosses level, and return
    the x of the crossing, linearly interpolated between the two points around it. None when the end comes first."""
    start_is_below = y[start_index] < level
    index = start_index
    while 0 <= index + step < len(y):
        next_index = index + step
        if (y[next_index] < level) != start_is_below:
            fraction = (level - y[index]) / (y[next_index] - y[index])
            return x[index] + fraction * (x[next_index] - x[index])
        index = next_index
    return None
