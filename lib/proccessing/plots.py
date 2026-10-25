# Plots the post-processing results into Outputs/ as PNG files: S_ii (dB + Smith chart), far field cuts, near field heatmaps.

# =========================================
# Imports
# =========================================

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lib.proccessing.far_field import get_far_field_cut
from lib.proccessing.s_parameters import calculate_reflection_db
from lib.support.defines import AXES, FAR_FIELD_CUT_PHIS, GHZ

# =========================================
# Classes and functions
# =========================================

def plot_reflection(s_matrix, params, port_name, paths):
    """Plot S_ii of one port twice: |S_ii| in dB over frequency, and on a Smith chart (shows which way to match).
    The minimum, the resonance notch, is marked on both, with its impedance on the Smith chart."""
    port_index = [port["name"] for port in params["ports"]].index(port_name)
    frequencies_ghz = np.array(params["frequencies"]) / GHZ
    reflection = s_matrix[port_index, port_index]
    reflection_db = calculate_reflection_db(s_matrix, params, port_name)
    notch_index = np.argmin(reflection_db)
    figure, (db_axes, smith_axes) = plt.subplots(1, 2, figsize = (12, 5))
    db_axes.plot(frequencies_ghz, reflection_db, marker = ".")
    db_axes.plot(frequencies_ghz[notch_index], reflection_db[notch_index], "rv")
    db_axes.annotate(f"{frequencies_ghz[notch_index]:.3g} GHz, {reflection_db[notch_index]:.1f} dB",
                     (frequencies_ghz[notch_index], reflection_db[notch_index]), textcoords = "offset points", xytext = (8, -4))
    db_axes.set_xlabel("Frequency [GHz]")
    db_axes.set_ylabel(f"|S{port_index + 1}{port_index + 1}| [dB]")
    db_axes.grid(True)
    draw_smith_grid(smith_axes)
    smith_axes.plot(reflection.real, reflection.imag)
    smith_axes.plot(reflection.real[0], reflection.imag[0], "ko", markersize = 4)
    smith_axes.annotate(f"{frequencies_ghz[0]:g} GHz", (reflection.real[0], reflection.imag[0]),
                        textcoords = "offset points", xytext = (6, 4))
    notch_impedance = params["ports"][port_index]["resistance"] * (1 + reflection[notch_index]) / (1 - reflection[notch_index])
    smith_axes.plot(reflection.real[notch_index], reflection.imag[notch_index], "rv")
    smith_axes.annotate(f"{frequencies_ghz[notch_index]:.3g} GHz\nZ = {notch_impedance.real:.1f} {notch_impedance.imag:+.1f}j Ohm",
                        (reflection.real[notch_index], reflection.imag[notch_index]), textcoords = "offset points", xytext = (8, -4))
    figure.suptitle(f"Reflection at port {port_name}")
    return save_figure(figure, paths["outputs"] / f"s_params_{port_name}.png")

def draw_smith_grid(axes):
    """Draw a Smith chart grid: lines of constant normalized resistance r and reactance x, each mapped to the
    reflection plane by gamma = (z - 1) / (z + 1). Upper half is inductive, lower half capacitive, center is matched."""
    sweep = np.tan(np.linspace(-np.pi / 2 + 1e-3, np.pi / 2 - 1e-3, 400))
    positive_sweep = sweep[sweep >= 0]
    for resistance in [0, 0.2, 0.5, 1, 2, 5]:
        gamma = (resistance + 1j * sweep - 1) / (resistance + 1j * sweep + 1)
        axes.plot(gamma.real, gamma.imag, color = "lightgray", linewidth = 0.8)
    for reactance in [-5, -2, -1, -0.5, -0.2, 0.2, 0.5, 1, 2, 5]:
        gamma = (positive_sweep + 1j * reactance - 1) / (positive_sweep + 1j * reactance + 1)
        axes.plot(gamma.real, gamma.imag, color = "lightgray", linewidth = 0.8)
    axes.plot([-1, 1], [0, 0], color = "lightgray", linewidth = 0.8)
    axes.set_aspect("equal")
    axes.set_xlim(-1.05, 1.05)
    axes.set_ylim(-1.05, 1.05)
    axes.axis("off")

def plot_far_field(far_field_result, far_field_monitor, paths):
    """Plot the directivity in dBi as two polar cuts, phi = 0 (xz plane) and phi = 90 (yz plane), with theta = 0
    (the +z axis) on top; the radius spans 40 dB under the peak, lower values sit at the center."""
    peak = np.max(far_field_result["directivity_dbi"])
    figure, axes_pair = plt.subplots(1, 2, subplot_kw = {"projection": "polar"}, figsize = (11, 5))
    for axes, cut_phi in zip(axes_pair, FAR_FIELD_CUT_PHIS):
        angles, cut = get_far_field_cut(far_field_result, cut_phi)
        axes.plot(np.deg2rad(angles), np.maximum(cut, peak - 40))
        axes.set_theta_zero_location("N")
        axes.set_theta_direction(-1)
        axes.set_rlim(peak - 40, peak + 1)
        axes.set_title(f"phi = {cut_phi} deg", pad = 15)
    figure.suptitle(f"{far_field_monitor['name']}: directivity [dBi] at {far_field_monitor['frequency'] / GHZ:g} GHz, "
                    f"max {peak:.1f} dBi", y = 1.04)
    return save_figure(figure, paths["outputs"] / f"{far_field_monitor['name']}.png")

def plot_near_field(near_field_result, near_field_monitor, paths):
    """Plot the magnitude of the two E components lying in the plane (Ex and Ey for a z plane) as two heatmaps
    in dBV/m, on one color scale 40 dB deep, so their strengths compare directly."""
    plane_axes = [axis for axis in AXES if len(near_field_result[axis]) > 1]
    magnitudes_db = []
    for axis in plane_axes:
        component = np.squeeze(near_field_result["e_field"][AXES.index(axis)])
        magnitudes_db.append(20 * np.log10(np.abs(component)))
    color_max = max(np.max(magnitude_db) for magnitude_db in magnitudes_db)
    figure, axes_pair = plt.subplots(1, 2, figsize = (11, 4.5))
    for axes, axis, magnitude_db in zip(axes_pair, plane_axes, magnitudes_db):
        image = axes.pcolormesh(near_field_result[plane_axes[0]], near_field_result[plane_axes[1]], magnitude_db.T,
                                shading = "auto", vmin = color_max - 40, vmax = color_max)
        axes.set_xlabel(f"{plane_axes[0]} [mm]")
        axes.set_ylabel(f"{plane_axes[1]} [mm]")
        axes.set_aspect("equal")
        axes.set_title(f"|E{axis}|")
    figure.colorbar(image, ax = axes_pair, label = "[dBV/m]")
    figure.suptitle(f"{near_field_monitor['name']}: {near_field_monitor['frequency'] / GHZ:g} GHz")
    return save_figure(figure, paths["outputs"] / f"{near_field_monitor['name']}.png")

def save_figure(figure, file_path):
    """Save a figure as PNG and close it, so many monitors do not keep figures open; returns the file path."""
    figure.savefig(file_path, dpi = 150, bbox_inches = "tight")
    plt.close(figure)
    return file_path
