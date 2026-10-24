# Calculates one near field monitor: reads the E field openEMS dumped on the plane and samples it on the monitor grid.

# =========================================
# Imports
# =========================================

import h5py
import numpy as np
from scipy.interpolate import RegularGridInterpolator

from lib.support.defines import AXES, MM, NEAR_FIELD_DUMP_NAME

# =========================================
# Classes and functions
# =========================================

def near_field(near_field_monitor, plane_index, field_scale, paths):
    """Sample the E field (Ex, Ey, Ez along the model's x / y / z axes) of one near field monitor on its grid,
    from the run where its port is excited, scaled to the normalized incident power.
    The dump file is found by the monitor's plane position, the same name sim_engine gave it."""
    dump_path = paths["sim"] / near_field_monitor["port"] / f"{NEAR_FIELD_DUMP_NAME}_{plane_index}.h5"
    if not dump_path.is_file():
        raise FileNotFoundError(f"{dump_path} is missing, rerun with --force to simulate again")
    mesh, field = read_near_field_dump(dump_path, near_field_monitor["frequency"])
    near_field_result = {
        "x": near_field_monitor["x"],
        "y": near_field_monitor["y"],
        "z": near_field_monitor["z"],
        "e_field": interpolate_to_monitor_grid(mesh, field, near_field_monitor) * field_scale,
    }
    return near_field_result

def read_near_field_dump(dump_path, frequency):
    """Read the dumped mesh (converted from meters to mm) and the complex E field at the sweep point closest to frequency.
    openEMS stores the field as (component, z, y, x), so it is transposed to (component, x, y, z) to match AXES."""
    with h5py.File(dump_path, "r") as dump:
        mesh = {}
        for axis in AXES:
            mesh[axis] = np.array(dump["Mesh"][axis]) / MM
        dump_frequencies = np.array(dump["FieldData/FD"].attrs["frequency"])
        index = np.argmin(np.abs(dump_frequencies - frequency))
        real_part = np.array(dump[f"FieldData/FD/f{index}_real"])
        imag_part = np.array(dump[f"FieldData/FD/f{index}_imag"])
    field = np.transpose(real_part + 1j * imag_part, (0, 3, 2, 1))
    return mesh, field

def interpolate_to_monitor_grid(mesh, field, near_field_monitor):
    """Linearly interpolate each E component from the mesh lines onto the monitor points.
    The plane has one constant axis, so the interpolation runs over the two other axes only."""
    constant_index = [len(near_field_monitor[axis]) for axis in AXES].index(1)
    first_axis, second_axis = [axis for axis in AXES if len(near_field_monitor[axis]) > 1]
    first_points, second_points = np.meshgrid(near_field_monitor[first_axis], near_field_monitor[second_axis],
                                              indexing = "ij")
    plane_field = np.squeeze(field, axis = constant_index + 1)
    shape = [3] + [len(near_field_monitor[axis]) for axis in AXES]
    e_field = np.zeros(shape, dtype = complex)
    for component in range(3):
        interpolator = RegularGridInterpolator((mesh[first_axis], mesh[second_axis]), plane_field[component],
                                               bounds_error = False, fill_value = None)
        values = interpolator((first_points, second_points))
        e_field[component] = np.expand_dims(values, axis = constant_index)
    return e_field
