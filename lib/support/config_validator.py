# Checks a parsed model and the material library against every rule, and returns the list of errors.

# =========================================
# Imports
# =========================================

from lib.common_functions import calculate_air_region, calculate_bounding_box, calculate_sweep_frequencies, count_points
from lib.support.defines import AXES, GHZ, LIGHT_SPEED, MM
from lib.support.defines import MAX_FAR_FIELD_POINTS, MAX_MODEL_SIZE_WAVELENGTHS, MAX_NEAR_FIELD_POINTS
from lib.support.defines import MIN_CELLS_PER_WAVELENGTH

# =========================================
# Classes and functions
# =========================================

def config_validator(model, materials):
    """Check the material library and the model; returns all errors at once so the user can fix them together."""
    errors = validate_materials(materials)
    errors += validate_model(model, materials)
    return errors

def validate_materials(materials):
    """Check every material has a known type and what that type needs: sigma for a metal, epsilon_r and mu_r for a dielectric."""
    errors = []
    for material in materials.values():
        where = f"material '{material['name']}'"
        if material["type"] not in ["pec", "metal", "dielectric"]:
            errors.append(f"{where}: type '{material['type']}' must be pec, metal or dielectric")
        if material["type"] == "metal" and material.get("sigma", 0) <= 0:
            errors.append(f"{where}: a metal needs sigma > 0")
        if material["type"] == "dielectric" and ("epsilon_r" not in material or "mu_r" not in material):
            errors.append(f"{where}: a dielectric needs epsilon_r and mu_r")
        if material.get("epsilon_r", 1) < 1:
            errors.append(f"{where}: epsilon_r must be >= 1")
        if material.get("mu_r", 1) <= 0:
            errors.append(f"{where}: mu_r must be > 0")
    return errors

def validate_model(model, materials):
    """Check every model rule; size and monitor checks need valid boxes and a valid band, so they run last."""
    errors = validate_boxes(model["boxes"], materials)
    errors += validate_ports(model["ports"])
    errors += validate_frequency(model["frequency"])
    errors += validate_mesh(model["mesh"])
    if errors:
        return errors
    errors += validate_box_overlaps(model["boxes"], materials)
    errors += validate_model_size(model["boxes"], model["frequency"])
    errors += validate_monitors(model["monitors"], model)
    return errors

def validate_boxes(boxes, materials):
    """Check box names, ranges and that each box's material exists and fits its shape."""
    if not boxes:
        return ["model: needs at least one <box>"]
    errors = validate_unique_names(boxes, "box")
    for box in boxes:
        where = f"box '{box['name']}'"
        errors += validate_range_order(box, where)
        errors += validate_box_material(box, materials, where)
    return errors

def validate_box_material(box, materials, where):
    """A dielectric needs volume, and a lossy metal is a conducting sheet model so its box must be flat."""
    if box["material"] not in materials:
        return [f"{where}: material '{box['material']}' is not in materials.xml"]
    material_type = materials[box["material"]]["type"]
    if material_type == "dielectric" and count_constant_axes(box) > 0:
        return [f"{where}: a dielectric box needs a non-zero size on x, y and z"]
    if material_type == "metal" and count_constant_axes(box) == 0:
        return [f"{where}: '{box['material']}' is a conducting sheet, so the box must be flat (use PEC for a thick metal)"]
    return []

def validate_box_overlaps(boxes, materials):
    """Reject overlapping boxes, except boxes of the same material (the overlap is that material either way) and a
    conductor inside or on a dielectric (the conductor wins there). Boxes that only touch, sharing a face or an edge,
    do not overlap."""
    errors = []
    for first_index in range(len(boxes)):
        for second_index in range(first_index + 1, len(boxes)):
            first = boxes[first_index]
            second = boxes[second_index]
            first_is_dielectric = materials[first["material"]]["type"] == "dielectric"
            second_is_dielectric = materials[second["material"]]["type"] == "dielectric"
            is_same_material = first["material"] == second["material"]
            is_conductor_on_dielectric = ((not first_is_dielectric and second_is_dielectric)
                                          or (first_is_dielectric and not second_is_dielectric))
            if is_same_material or is_conductor_on_dielectric:
                continue
            if are_boxes_overlapping(first, second):
                errors.append(f"box '{first['name']}' overlaps box '{second['name']}'")
    return errors

def are_boxes_overlapping(first, second):
    """Boxes overlap when their insides meet on every axis; a flat axis [a, a] meets a range only strictly inside it."""
    for axis in AXES:
        first_low, first_high = first[axis]
        second_low, second_high = second[axis]
        if first_low == first_high and second_low == second_high:
            meets = first_low == second_low
        elif first_low == first_high:
            meets = second_low < first_low < second_high
        elif second_low == second_high:
            meets = first_low < second_low < first_high
        else:
            meets = max(first_low, second_low) < min(first_high, second_high)
        if not meets:
            return False
    return True

def validate_ports(ports):
    """Check port names, ranges and resistance, and that the port has length along its direction."""
    if not ports:
        return ["model: needs at least one <port>"]
    errors = validate_unique_names(ports, "port")
    for port in ports:
        where = f"port '{port['name']}'"
        errors += validate_range_order(port, where)
        if port["resistance"] <= 0:
            errors.append(f"{where}: resistance must be > 0")
        if port["direction"] not in AXES:
            errors.append(f"{where}: direction '{port['direction']}' must be x, y or z")
        elif port[port["direction"]][0] == port[port["direction"]][1]:
            errors.append(f"{where}: needs a non-zero length along its direction {port['direction']}")
    resistances = set(port["resistance"] for port in ports)
    if len(resistances) > 1:
        errors.append("ports: all ports need the same resistance, since the Touchstone file has one reference impedance")
    return errors

def validate_frequency(frequency):
    """Check the sweep band is positive and ordered."""
    errors = []
    if frequency["start"] <= 0:
        errors.append("frequency: start must be > 0")
    if frequency["stop"] <= frequency["start"]:
        errors.append("frequency: stop must be bigger than start")
    if frequency["points"] < 1:
        errors.append("frequency: points must be >= 1")
    return errors

def validate_mesh(mesh):
    """Check the mesh knobs; below MIN_CELLS_PER_WAVELENGTH the FDTD dispersion error is too large."""
    errors = []
    if mesh["cells_per_wavelength"] < MIN_CELLS_PER_WAVELENGTH:
        errors.append(f"mesh: cells_per_wavelength must be >= {MIN_CELLS_PER_WAVELENGTH}")
    if mesh["air_margin"] <= 0:
        errors.append("mesh: air_margin must be > 0")
    return errors

def validate_model_size(boxes, frequency):
    """Reject models bigger than MAX_MODEL_SIZE_WAVELENGTHS at the highest frequency, usually a unit mistake."""
    bounding_box = calculate_bounding_box(boxes)
    shortest_wavelength = LIGHT_SPEED / frequency["stop"] / MM
    largest_size = max(high - low for low, high in bounding_box.values())
    size_in_wavelengths = largest_size / shortest_wavelength
    if size_in_wavelengths > MAX_MODEL_SIZE_WAVELENGTHS:
        return [f"model: largest size {largest_size:g} mm is {size_in_wavelengths:.1f} wavelengths, "
                f"limit is {MAX_MODEL_SIZE_WAVELENGTHS}"]
    return []

def validate_monitors(monitors, model):
    """Check monitor names are unique, since they name the output files, and each monitor's own rules."""
    errors = validate_unique_names(monitors["far_field"] + monitors["near_field"], "monitor")
    for far_field in monitors["far_field"]:
        errors += validate_far_field(far_field, model)
    air_region = calculate_air_region(model["boxes"], model["mesh"]["air_margin"], model["frequency"]["start"])
    for near_field in monitors["near_field"]:
        errors += validate_near_field(near_field, model, air_region)
    for s_params in monitors["s_params"]:
        errors += validate_monitor_port(s_params, model["ports"], "s_params")
    return errors

def validate_far_field(far_field, model):
    """Check the far field port exists, its frequency is a sweep point and the angle step gives a sane number of points."""
    where = f"far_field '{far_field['name']}'"
    errors = validate_monitor_port(far_field, model["ports"], where)
    errors += validate_monitor_frequency(far_field, model["frequency"], where)
    if far_field["resolution"] <= 0:
        errors.append(f"{where}: resolution must be > 0")
        return errors
    theta_count = count_points(0, 180, far_field["resolution"])
    phi_count = count_points(0, 360, far_field["resolution"])
    if theta_count * phi_count > MAX_FAR_FIELD_POINTS:
        errors.append(f"{where}: resolution {far_field['resolution']:g} deg gives {theta_count * phi_count} points, "
                      f"limit is {MAX_FAR_FIELD_POINTS}")
    return errors

def validate_near_field(near_field, model, air_region):
    """Check port and frequency, and that the grid is a plane (one constant axis) fully inside the air region."""
    where = f"near_field '{near_field['name']}'"
    errors = validate_monitor_port(near_field, model["ports"], where)
    errors += validate_monitor_frequency(near_field, model["frequency"], where)
    errors += validate_range_order(near_field, where)
    if near_field["resolution"] <= 0:
        errors.append(f"{where}: resolution must be > 0")
    if count_constant_axes(near_field) != 1:
        errors.append(f"{where}: exactly one of x, y, z must be a single value, so it is a plane")
    for axis in AXES:
        low, high = near_field[axis]
        air_low, air_high = air_region[axis]
        if low < air_low or high > air_high:
            errors.append(f"{where}: {axis} [{low:g}, {high:g}] is outside the air region "
                          f"[{air_low:g}, {air_high:g}]")
    if near_field["resolution"] > 0:
        errors += validate_near_field_size(near_field, where)
    return errors

def validate_near_field_size(near_field, where):
    """Reject a near field grid with more than MAX_NEAR_FIELD_POINTS points, usually a too fine resolution."""
    point_count = 1
    for axis in AXES:
        low, high = near_field[axis]
        point_count *= count_points(low, high, near_field["resolution"])
    if point_count > MAX_NEAR_FIELD_POINTS:
        return [f"{where}: resolution {near_field['resolution']:g} mm gives {point_count} points, "
                f"limit is {MAX_NEAR_FIELD_POINTS}"]
    return []

def validate_monitor_port(monitor, ports, where):
    """Check the monitor's excited port is one of the model's ports."""
    port_names = [port["name"] for port in ports]
    if monitor["port"] in port_names:
        return []
    return [f"{where}: port '{monitor['port']}' is not in the model, ports are: {', '.join(port_names)}"]

def validate_monitor_frequency(monitor, frequency, where):
    """Check the monitor frequency is one of the sweep points, since only those frequencies are calculated."""
    sweep_frequencies = calculate_sweep_frequencies(frequency)
    tolerance = 1e-9 * frequency["stop"]
    for sweep_frequency in sweep_frequencies:
        if abs(monitor["frequency"] - sweep_frequency) <= tolerance:
            return []
    sweep_text = ", ".join(f"{sweep_frequency / GHZ:g}" for sweep_frequency in sweep_frequencies)
    return [f"{where}: frequency {monitor['frequency'] / GHZ:g} GHz is not a sweep point, "
            f"the sweep points are [{sweep_text}] GHz"]

def validate_unique_names(items, kind):
    """Report every name used by more than one item of the same kind."""
    errors = []
    seen = set()
    for item in items:
        if item["name"] in seen:
            errors.append(f"{kind} name '{item['name']}' is used twice")
        seen.add(item["name"])
    return errors

def validate_range_order(item, where):
    """Check low <= high on each axis of a box, port or near field."""
    errors = []
    for axis in AXES:
        low, high = item[axis]
        if low > high:
            errors.append(f"{where}: {axis} low {low:g} is bigger than high {high:g}")
    return errors

def count_constant_axes(item):
    """Count the axes where low == high, e.g. 1 for a metal sheet or a near field plane."""
    count = 0
    for axis in AXES:
        if item[axis][0] == item[axis][1]:
            count += 1
    return count
