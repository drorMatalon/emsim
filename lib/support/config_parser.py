# Reads a user model.xml and the shared materials library, validates both, and returns one params dict.
# The rules themselves live in config_validator.py.

# =========================================
# Imports
# =========================================

import ast
import math
import operator
import re
import xml.etree.ElementTree as ET

from lib.common_functions import calculate_sweep_frequencies, create_points
from lib.support.config_validator import config_validator
from lib.support.defines import AXES, DEFAULT_AIR_MARGIN, DEFAULT_CELLS_PER_WAVELENGTH, GHZ, MATERIALS_PATH

# =========================================
# Entry
# =========================================

class ConfigError(Exception):
    """Raised when model.xml or materials.xml is malformed or breaks a rule."""

def config_parser(model_path):
    """Read and validate a user model.xml together with the shared materials library."""
    materials = read_materials(MATERIALS_PATH)
    model = read_model(model_path)
    errors = config_validator(model, materials)
    if errors:
        raise ConfigError(f"{model_path} has {len(errors)} errors:\n  " + "\n  ".join(errors))
    model["materials"] = select_used_materials(model["boxes"], materials)
    return create_sample_points(model)

# =========================================
# Reading
# =========================================

def read_materials(path):
    """Read the shared material library into a dict keyed by material name."""
    root = load_xml_root(path, "materials")
    check_tags(root, ["material"], "materials")
    materials = {}
    for element in root.findall("material"):
        material = read_material(element)
        if material["name"] in materials:
            raise ConfigError(f"materials.xml: material '{material['name']}' is defined twice")
        materials[material["name"]] = material
    return materials

def read_material(element):
    """Read one material; the values are optional here, the validator checks each type has what it needs."""
    name = get_text(element, "name", "material")
    where = f"material '{name}'"
    check_tags(element, ["name", "type", "sigma", "epsilon_r", "mu_r"], where)
    material = {"name": name, "type": get_text(element, "type", where)}
    for tag in ["sigma", "epsilon_r", "mu_r"]:
        if element.find(tag) is not None:
            material[tag] = get_value(element, tag, where)
    return material

def read_model(path):
    """Read model.xml into a dict of boxes, ports, frequency, mesh and monitors."""
    root = load_xml_root(path, "model")
    check_tags(root, ["parameter", "box", "port", "frequency", "mesh", "monitors"], "model")
    for tag in ("frequency", "mesh", "monitors"):
        if len(root.findall(tag)) > 1:
            raise ConfigError(f"model: <{tag}> appears more than once")
    apply_parameters(root)
    model = {
        "boxes": [read_box(element) for element in root.findall("box")],
        "ports": [read_port(element) for element in root.findall("port")],
        "frequency": read_frequency(root.find("frequency")),
        "mesh": read_mesh(root.find("mesh")),
        "monitors": read_monitors(root.find("monitors")),
    }
    return model

def apply_parameters(root):
    """Replace every parameter symbol by its value, as text, in all the other tags, so the rest reads plain expressions.
    The value goes in brackets, so -L/2 stays right when L is an expression; only whole words are replaced."""
    parameters = root.findall("parameter")
    symbols = [get_text(parameter, "symbol", "parameter") for parameter in parameters]
    for parameter, symbol in zip(parameters, symbols):
        check_tags(parameter, ["symbol", "value"], f"parameter '{symbol}'")
        if not re.fullmatch(r"[A-Za-z_]+", symbol):
            raise ConfigError(f"parameter '{symbol}': a symbol may contain only letters and _, no numbers")
        if symbols.count(symbol) > 1:
            raise ConfigError(f"parameter '{symbol}': is defined more than once")
        value = get_text(parameter, "value", f"parameter '{symbol}'")
        for element in root.iter():
            if element.text and element.tag != "symbol":
                element.text = re.sub(rf"\b{symbol}\b", f"({value})", element.text)

def read_box(element):
    """Read one box: a material filling an axis aligned x / y / z range."""
    name = get_text(element, "name", "box")
    where = f"box '{name}'"
    check_tags(element, ["name", "material", "x", "y", "z"], where)
    box = {"name": name, "material": get_text(element, "material", where)}
    for axis in AXES:
        box[axis] = get_range(element, axis, where)
    return box

def read_port(element):
    """Read one lumped port: its resistance, the axis the current flows along, and its x / y / z range."""
    name = get_text(element, "name", "port")
    where = f"port '{name}'"
    check_tags(element, ["name", "resistance", "direction", "x", "y", "z"], where)
    port = {
        "name": name,
        "resistance": get_value(element, "resistance", where),
        "direction": get_text(element, "direction", where),
    }
    for axis in AXES:
        port[axis] = get_range(element, axis, where)
    return port

def read_frequency(element):
    """Read the sweep band, converting GHz to Hz since openEMS works in Hz."""
    if element is None:
        raise ConfigError("model: missing <frequency>")
    check_tags(element, ["start", "stop", "points"], "frequency")
    points = get_value(element, "points", "frequency")
    if points != int(points):
        raise ConfigError(f"frequency: points must be an integer, got {points:g}")
    frequency = {
        "start": get_value(element, "start", "frequency") * GHZ,
        "stop": get_value(element, "stop", "frequency") * GHZ,
        "points": int(points),
    }
    return frequency

def read_mesh(element):
    """Read the mesh knobs; the section and each knob are optional and fall back to the defaults."""
    mesh = {
        "cells_per_wavelength": DEFAULT_CELLS_PER_WAVELENGTH,
        "air_margin": DEFAULT_AIR_MARGIN,
    }
    if element is None:
        return mesh
    check_tags(element, list(mesh), "mesh")
    for tag in mesh:
        if element.find(tag) is not None:
            mesh[tag] = get_value(element, tag, "mesh")
    return mesh

def read_monitors(element):
    """Read the far field, near field and S-parameter plot monitors; the S matrix itself is always saved, monitors or not."""
    monitors = {"far_field": [], "near_field": [], "s_params": []}
    if element is None:
        return monitors
    check_tags(element, ["far_field", "near_field", "s_params"], "monitors")
    for far_field_element in element.findall("far_field"):
        monitors["far_field"].append(read_far_field_monitor(far_field_element))
    for near_field_element in element.findall("near_field"):
        monitors["near_field"].append(read_near_field_monitor(near_field_element))
    for s_params_element in element.findall("s_params"):
        monitors["s_params"].append(read_s_params_monitor(s_params_element))
    return monitors

def read_far_field_monitor(element):
    """Read a far field monitor: excited port, one frequency, and one angle step for both theta and phi."""
    name = get_text(element, "name", "far_field")
    where = f"far_field '{name}'"
    check_tags(element, ["name", "port", "frequency", "resolution"], where)
    far_field = {
        "name": name,
        "port": get_text(element, "port", where),
        "frequency": get_value(element, "frequency", where) * GHZ,
        "resolution": get_value(element, "resolution", where),
    }
    return far_field

def read_near_field_monitor(element):
    """Read a near field monitor: excited port, one frequency, and a grid where each axis is a value or a range."""
    name = get_text(element, "name", "near_field")
    where = f"near_field '{name}'"
    check_tags(element, ["name", "port", "frequency", "x", "y", "z", "resolution"], where)
    near_field = {
        "name": name,
        "port": get_text(element, "port", where),
        "frequency": get_value(element, "frequency", where) * GHZ,
        "resolution": get_value(element, "resolution", where),
    }
    for axis in AXES:
        near_field[axis] = get_range(element, axis, where)
    return near_field

def read_s_params_monitor(element):
    """Read an S-parameter monitor: the port whose S_ii is plotted over frequency."""
    check_tags(element, ["port"], "s_params")
    return {"port": get_text(element, "port", "s_params")}

def select_used_materials(boxes, materials):
    """Keep only the materials the model's boxes actually use."""
    used_materials = {}
    for box in boxes:
        used_materials[box["material"]] = materials[box["material"]]
    return used_materials

# =========================================
# Sample points
# =========================================

def create_sample_points(model):
    """Turn the sweep and the monitor resolutions into explicit point lists, so later stages never rebuild them."""
    model["frequencies"] = calculate_sweep_frequencies(model.pop("frequency"))
    far_fields = []
    for far_field in model["monitors"]["far_field"]:
        far_fields.append(create_far_field_angles(far_field))
    near_fields = []
    for near_field in model["monitors"]["near_field"]:
        near_fields.append(create_near_field_grid(near_field))
    model["monitors"] = {"far_field": far_fields, "near_field": near_fields, "s_params": model["monitors"]["s_params"]}
    return model

def create_far_field_angles(far_field):
    """Replace the angle resolution by theta 0..180 and phi 0..360; phi stops before 360, the same direction as 0."""
    phi = create_points(0, 360, far_field["resolution"])
    if math.isclose(phi[-1], 360):
        phi.pop()
    far_field_angles = {
        "name": far_field["name"],
        "port": far_field["port"],
        "frequency": far_field["frequency"],
        "theta": create_points(0, 180, far_field["resolution"]),
        "phi": phi,
    }
    return far_field_angles

def create_near_field_grid(near_field):
    """Replace the grid resolution by x / y / z point lists; the constant axis becomes a single point."""
    near_field_grid = {
        "name": near_field["name"],
        "port": near_field["port"],
        "frequency": near_field["frequency"],
    }
    for axis in AXES:
        low, high = near_field[axis]
        near_field_grid[axis] = create_points(low, high, near_field["resolution"])
    return near_field_grid

# =========================================
# XML values
# =========================================

def load_xml_root(path, root_tag):
    """Parse an XML file and check its root tag."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ConfigError(f"{path}: cannot read XML ({error})")
    if root.tag != root_tag:
        raise ConfigError(f"{path}: root tag must be <{root_tag}>, got <{root.tag}>")
    return root

def check_tags(element, allowed_tags, where):
    """Raise on any child tag that is not allowed, so typos like <mash> are not silently ignored."""
    for child in element:
        if child.tag not in allowed_tags:
            raise ConfigError(f"{where}: unknown tag <{child.tag}>, allowed: {', '.join(sorted(allowed_tags))}")

def get_text(element, tag, where):
    """Get the stripped text of a child tag that must appear exactly once."""
    children = element.findall(tag)
    if len(children) > 1:
        raise ConfigError(f"{where}: <{tag}> appears more than once")
    if not children or children[0].text is None or not children[0].text.strip():
        raise ConfigError(f"{where}: missing <{tag}>")
    return children[0].text.strip()

def get_value(element, tag, where):
    """Get a child tag as a number; the text may be an expression like 1.6 + 0.035."""
    return evaluate_expression(get_text(element, tag, where), f"{where} <{tag}>")

def get_range(element, tag, where):
    """Get a child tag as [low, high]; a single value v is read as the range [v, v]."""
    text = get_text(element, tag, where)
    where = f"{where} <{tag}>"
    if not (text.startswith("[") and text.endswith("]")):
        value = evaluate_expression(text, where)
        return [value, value]
    parts = text[1:-1].split(",")
    if len(parts) != 2:
        raise ConfigError(f"{where}: a range must be [low, high], got {text}")
    return [evaluate_expression(parts[0], where), evaluate_expression(parts[1], where)]

def evaluate_expression(text, where):
    """Evaluate plain arithmetic like '1.6 + 0.035' by walking its syntax tree; unlike eval() it cannot run code."""
    try:
        tree = ast.parse(text.strip(), mode = "eval")
        return calculate_node(tree.body, text, where)
    except SyntaxError:
        raise ConfigError(f"{where}: '{text.strip()}' is not a valid number or expression")
    except (ZeroDivisionError, OverflowError) as error:
        raise ConfigError(f"{where}: '{text.strip()}' cannot be calculated ({error})")

def calculate_node(node, text, where):
    """Calculate one node of the tree; only numbers, + - * / ** and a sign in front are allowed."""
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in operators:
        left = calculate_node(node.left, text, where)
        right = calculate_node(node.right, text, where)
        return operators[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = calculate_node(node.operand, text, where)
        return -value if isinstance(node.op, ast.USub) else value
    raise ConfigError(f"{where}: '{text.strip()}' may contain only numbers, defined parameter symbols and + - * / **")
