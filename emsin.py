# emsim entry point: reads a project's model.xml, runs what changed since the last run, and saves the history.
# Usage: python emsin.py --root <project_dir> [--view] [--force]

# =========================================
# Imports
# =========================================

import argparse
import sys
from pathlib import Path

from lib.common_functions import print_title
from lib.proccessing.post_processor import post_processor
from lib.sim.sim_engine import sim_engine, view_model
from lib.support.config_parser import ConfigError, config_parser
from lib.support.defines import GHZ
from lib.support.project_handler import ProjectError, find_rerun_level, project_handler, save_history

# =========================================
# Classes and functions
# =========================================

def parse_arguments():
    """Read the command line: the project folder, and the view / force modes."""
    parser = argparse.ArgumentParser(description = "Antenna simulation with openEMS")
    parser.add_argument("--root", required = True, help = "project folder holding model.xml")
    parser.add_argument("--view", action = "store_true", help = "only build the model and open it in AppCSXCAD")
    parser.add_argument("--force", action = "store_true", help = "run everything again and rewrite the history")
    return parser.parse_args()

def print_model_summary(params, rerun_level, rerun_reason):
    """Print what was parsed and what will run, one line each."""
    frequencies = params["frequencies"]
    monitors = params["monitors"]
    print(f"{'Model':<9}: {len(params['boxes'])} boxes, {len(params['ports'])} ports, "
          f"{frequencies[0] / GHZ:g}-{frequencies[-1] / GHZ:g} GHz ({len(frequencies)} points)")
    print(f"{'Monitors':<9}: {len(monitors['s_params'])} s_params, {len(monitors['far_field'])} far field, "
          f"{len(monitors['near_field'])} near field")
    print(f"{'Rerun':<9}: {rerun_level} ({rerun_reason})", flush = True)

def select_rerun_level(paths, params, force):
    """Decide what runs and why: everything when forced (e.g. after a broken run), otherwise what History says changed."""
    if force:
        return "simulate", "forced by --force"
    return find_rerun_level(paths, params)

def run_simulations(params, paths):
    """Run one simulation per port, each under its own title."""
    port_count = len(params["ports"])
    for index, port in enumerate(params["ports"]):
        print_title(f"Simulation: port {port['name']} ({index + 1}/{port_count})")
        sim_engine(params, paths, port["name"])

def print_saved_files(saved_files):
    """List every file written by post-processing, with its full path."""
    print("Saved files:")
    for file_path in saved_files:
        print(f"  {file_path}")

def run_project(arguments):
    """Check the project, parse its model, then view it or run the simulations; history is saved only at the end."""
    print_title(f"emsim: {Path(arguments.root).resolve().name}")
    paths = project_handler(arguments.root)
    params = config_parser(paths["model"])
    if arguments.view:
        view_model(params, paths)
        return
    rerun_level, rerun_reason = select_rerun_level(paths, params, arguments.force)
    print_model_summary(params, rerun_level, rerun_reason)
    if rerun_level == "up_to_date":
        return
    if rerun_level == "simulate":
        run_simulations(params, paths)
    print_title("Post-processing")
    saved_files = post_processor(params, paths)
    save_history(paths, params)
    print_title("Done, history saved")
    print_saved_files(saved_files)

# =========================================
# Main
# =========================================

if __name__ == "__main__":
    try:
        run_project(parse_arguments())
    except (ProjectError, ConfigError) as error:
        print(f"Error: {error}")
        sys.exit(1)
