# Helpers needed by more than one module.

# =========================================
# Imports
# =========================================

import math

from lib.support.defines import AXES, LIGHT_SPEED, MM

# =========================================
# Classes and functions
# =========================================

def calculate_sweep_frequencies(frequency):
    """List the sweep points: points evenly spaced from start to stop, both included (like np.linspace)."""
    if frequency["points"] == 1:
        return [frequency["start"]]
    step = (frequency["stop"] - frequency["start"]) / (frequency["points"] - 1)
    sweep_frequencies = []
    for index in range(frequency["points"]):
        sweep_frequencies.append(frequency["start"] + index * step)
    return sweep_frequencies

def create_points(low, high, resolution):
    """List points from low in resolution steps up to high; if the range does not divide, the last partial step is dropped.
    Points are rounded to 12 decimals so a 0.1 step gives 0.3 and not 0.30000000000000004."""
    points = []
    for index in range(count_points(low, high, resolution)):
        points.append(round(low + index * resolution, 12))
    return points

def count_points(low, high, resolution):
    """Count the points create_points would make, without building the list (so a huge grid is cheap to check)."""
    return math.floor((high - low) / resolution + 1e-9) + 1

def calculate_bounding_box(boxes):
    """Find the smallest x / y / z ranges holding all boxes."""
    bounding_box = {}
    for axis in AXES:
        low = min(box[axis][0] for box in boxes)
        high = max(box[axis][1] for box in boxes)
        bounding_box[axis] = [low, high]
    return bounding_box

def calculate_air_region(boxes, air_margin, lowest_frequency):
    """Grow the bounding box by air_margin wavelengths at the lowest frequency, where the wavelength is longest."""
    bounding_box = calculate_bounding_box(boxes)
    longest_wavelength = LIGHT_SPEED / lowest_frequency / MM
    margin = air_margin * longest_wavelength
    air_region = {}
    for axis in AXES:
        low, high = bounding_box[axis]
        air_region[axis] = [low - margin, high + margin]
    return air_region

def print_title(title):
    """Print a framed section title in the same style as the code banners, so the run log is easy to scan.
    Flushed right away, so it is not printed after openEMS output when the output goes to a file."""
    banner = "# " + "=" * 41
    print(f"\n{banner}\n# {title}\n{banner}", flush = True)
