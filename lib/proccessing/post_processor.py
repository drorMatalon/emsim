# Turns the raw openEMS results into the S matrix and the monitor results, saved and plotted into Outputs/.

# =========================================
# Imports
# =========================================

import numpy as np

from lib.proccessing.far_field import far_field
from lib.proccessing.metrics import calculate_beamwidth, calculate_reflection_band, find_far_field_peak
from lib.proccessing.near_field import near_field
from lib.proccessing.outputs_writer import write_far_field_csv, write_near_field_csv, write_touchstone
from lib.proccessing.plots import plot_far_field, plot_near_field, plot_reflection
from lib.proccessing.s_parameters import calculate_reflection_db, s_parameters
from lib.sim.sim_engine import create_simulation
from lib.support.defines import BEAMWIDTH_LEVEL_DB, FAR_FIELD_CUT_PHIS, GHZ, INCIDENT_POWER, MHZ
from lib.support.defines import REFLECTION_BANDWIDTH_LEVEL_DB

# =========================================
# Classes and functions
# =========================================

def post_processor(params, paths):
    """Save the S matrix of all ports (always), then calculate, save and plot every monitor, printing one summary
    line each; returns the saved file paths. The setup is rebuilt without running, since openEMS reads the result
    files through its port and nf2ff objects."""
    setup = create_simulation(params, params["ports"][0]["name"])
    saved_files = run_s_parameters(setup, params, paths)
    for far_field_monitor in params["monitors"]["far_field"]:
        saved_files += run_far_field_monitor(setup, params, far_field_monitor, paths)
    for plane_index, near_field_monitor in enumerate(params["monitors"]["near_field"]):
        saved_files += run_near_field_monitor(setup, params, near_field_monitor, plane_index, paths)
    return saved_files

def run_s_parameters(setup, params, paths):
    """Save the S matrix as Touchstone, then plot S_ii and print its resonance and bandwidth for every s_params monitor."""
    s_matrix = s_parameters(setup["ports"], params, paths)
    saved_files = [write_touchstone(s_matrix, params, paths)]
    print(f"{'S matrix':<9}: {saved_files[0].name}", flush = True)
    for s_params_monitor in params["monitors"]["s_params"]:
        port_name = s_params_monitor["port"]
        saved_files.append(plot_reflection(s_matrix, params, port_name, paths))
        reflection_db = calculate_reflection_db(s_matrix, params, port_name)
        band = calculate_reflection_band(reflection_db, params["frequencies"])
        print_reflection_summary(band, params, port_name)
    return saved_files

def print_reflection_summary(band, params, port_name):
    """Print the resonance of one port, then its band under REFLECTION_BANDWIDTH_LEVEL_DB, or why there is none."""
    port_number = [port["name"] for port in params["ports"]].index(port_name) + 1
    s_name = f"S{port_number}{port_number}"
    print(f"{port_name:<9}: {s_name} resonance {band['frequency'] / GHZ:.3f} GHz, {band['reflection_db']:.1f} dB")
    level_text = f"{REFLECTION_BANDWIDTH_LEVEL_DB:g} dB band"
    if band["reflection_db"] >= REFLECTION_BANDWIDTH_LEVEL_DB:
        band_text = f"none, {s_name} never gets under {REFLECTION_BANDWIDTH_LEVEL_DB:g} dB"
    elif band["low"] is None or band["high"] is None:
        band_text = "reaches the sweep edge, widen the sweep to measure it"
    else:
        band_text = (f"{band['low'] / GHZ:.3f}-{band['high'] / GHZ:.3f} GHz "
                     f"({(band['high'] - band['low']) / MHZ:.0f} MHz)")
    print(f"{'':<11}{level_text}: {band_text}", flush = True)

def run_far_field_monitor(setup, params, far_field_monitor, paths):
    """Calculate one far field monitor normalized to INCIDENT_POWER, save it as CSV and polar cuts, print its peak."""
    field_scale = calculate_field_scale(setup["ports"], params, far_field_monitor, paths)
    far_field_result = far_field(setup["nf2ff"], params, far_field_monitor, field_scale, paths)
    saved_files = [
        write_far_field_csv(far_field_result, far_field_monitor, paths),
        plot_far_field(far_field_result, far_field_monitor, paths),
    ]
    print_far_field_summary(far_field_result, far_field_monitor)
    return saved_files

def print_far_field_summary(far_field_result, far_field_monitor):
    """Print the max directivity and its direction, then the beamwidth of the same cuts the plot shows."""
    peak = find_far_field_peak(far_field_result)
    print(f"{far_field_monitor['name']:<9}: max directivity {peak['directivity_dbi']:.1f} dBi "
          f"at theta {peak['theta']:g} deg, phi {peak['phi']:g} deg")
    beamwidth_texts = []
    for cut_phi in FAR_FIELD_CUT_PHIS:
        beamwidth = calculate_beamwidth(far_field_result, cut_phi)
        if beamwidth is None:
            beamwidth_texts.append(f"none (phi = {cut_phi})")
        else:
            beamwidth_texts.append(f"{beamwidth:.0f} deg (phi = {cut_phi})")
    print(f"{'':<11}{BEAMWIDTH_LEVEL_DB:g} dB beamwidth: {', '.join(beamwidth_texts)}", flush = True)

def run_near_field_monitor(setup, params, near_field_monitor, plane_index, paths):
    """Calculate one near field monitor normalized to INCIDENT_POWER, save it as CSV and heatmaps, print its max |E|."""
    field_scale = calculate_field_scale(setup["ports"], params, near_field_monitor, paths)
    near_field_result = near_field(near_field_monitor, plane_index, field_scale, paths)
    saved_files = [
        write_near_field_csv(near_field_result, near_field_monitor, paths),
        plot_near_field(near_field_result, near_field_monitor, paths),
    ]
    e_abs = np.sqrt(np.sum(np.abs(near_field_result["e_field"]) ** 2, axis = 0))
    print(f"{near_field_monitor['name']:<9}: max |E| {20 * np.log10(np.max(e_abs)):.1f} dBV/m", flush = True)
    return saved_files

def calculate_field_scale(ports, params, monitor, paths):
    """The factor that normalizes a monitor's fields to INCIDENT_POWER entering its excited port at its frequency.
    openEMS fields follow the raw Gaussian pulse; fields grow with the square root of power, so scale = sqrt(P_wanted / P_inc)."""
    port_index = [port["name"] for port in params["ports"]].index(monitor["port"])
    port = ports[port_index]
    port.CalcPort(str(paths["sim"] / monitor["port"]), [monitor["frequency"]])
    return np.sqrt(INCIDENT_POWER / port.P_inc[0])
