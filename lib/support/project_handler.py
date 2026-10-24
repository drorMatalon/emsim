# Checks the user's project folder, creates its working folders, and uses History to decide what must run again.

# =========================================
# Imports
# =========================================

import json
import shutil
from pathlib import Path

from lib.support.defines import AXES, HISTORY_DIR_NAME, HISTORY_FILE_NAME, MODEL_FILE_NAME, OUTPUTS_DIR_NAME, SIM_DIR_NAME

# =========================================
# Project folder
# =========================================

class ProjectError(Exception):
    """Raised when the project folder or its model.xml is missing."""

def project_handler(root):
    """Check the user's project folder and create its missing working folders; returns every path the run needs."""
    root = Path(root).resolve()
    validate_project_root(root)
    paths = create_project_paths(root)
    create_missing_dirs(paths)
    return paths

def validate_project_root(root):
    """The project folder must exist and hold the user's model.xml."""
    if not root.is_dir():
        raise ProjectError(f"project folder {root} does not exist")
    if not (root / MODEL_FILE_NAME).is_file():
        raise ProjectError(f"project folder {root} has no {MODEL_FILE_NAME}")

def create_project_paths(root):
    """Build every path of the project in one place, so no other module builds paths by hand."""
    paths = {
        "root": root,
        "model": root / MODEL_FILE_NAME,
        "history": root / HISTORY_DIR_NAME,
        "sim": root / SIM_DIR_NAME,
        "outputs": root / OUTPUTS_DIR_NAME,
        "history_file": root / HISTORY_DIR_NAME / HISTORY_FILE_NAME,
    }
    return paths

def create_missing_dirs(paths):
    """Create the History, Sim and Outputs folders if they are not there yet."""
    for key in ["history", "sim", "outputs"]:
        paths[key].mkdir(exist_ok = True)

def clear_generated_dirs(paths):
    """Empty the History, Sim and Outputs folders before a forced run, so only what the current model makes is left.
    Only emsim writes in these folders; model.xml and any other file in the project folder are never touched."""
    for key in ["history", "sim", "outputs"]:
        try:
            shutil.rmtree(paths[key])
        except PermissionError as error:
            raise ProjectError(f"cannot clear {paths[key]}, a file is open in another program: {error.filename}")
        paths[key].mkdir()

# =========================================
# History
# =========================================

def find_rerun_level(paths, params):
    """Compare params with the last successful run: returns "simulate", "post_process" or "up_to_date",
    plus a short reason for the user. A missing or broken history file means we know nothing, so everything runs."""
    last_params = load_history(paths)
    if last_params is None:
        return "simulate", "no usable history"
    current_params = convert_to_json_types(params)
    current_inputs = get_simulation_inputs(current_params)
    last_inputs = get_simulation_inputs(last_params)
    changed_inputs = [key for key in current_inputs if current_inputs[key] != last_inputs[key]]
    if changed_inputs:
        return "simulate", f"{', '.join(changed_inputs)} changed"
    if current_params["monitors"] != last_params["monitors"]:
        return "post_process", "monitors changed"
    return "up_to_date", "nothing changed"

def load_history(paths):
    """Read the params of the last successful run, or None when there is no usable history."""
    if not paths["history_file"].is_file():
        return None
    try:
        return json.loads(paths["history_file"].read_text(encoding = "utf-8"))
    except json.JSONDecodeError:
        return None

def convert_to_json_types(params):
    """Pass params through JSON once, so it compares equal to what was loaded back (tuples become lists etc.)."""
    return json.loads(json.dumps(params))

def get_simulation_inputs(params):
    """Pick what the FDTD run itself depends on; any change here means a new simulation.
    The near field plane extent counts, since openEMS records the field only on that plane during the run."""
    near_field_planes = []
    for near_field in params["monitors"]["near_field"]:
        plane = {}
        for axis in AXES:
            plane[axis] = [near_field[axis][0], near_field[axis][-1]]
        near_field_planes.append(plane)
    simulation_inputs = {
        "boxes": params["boxes"],
        "ports": params["ports"],
        "frequencies": params["frequencies"],
        "mesh": params["mesh"],
        "near_field_planes": near_field_planes,
    }
    return simulation_inputs

def save_history(paths, params):
    """Save the params of a run that finished successfully; materials are left out since they are assumed constant."""
    history = {}
    for key, value in params.items():
        if key != "materials":
            history[key] = value
    paths["history_file"].write_text(json.dumps(history, indent = 4), encoding = "utf-8")
