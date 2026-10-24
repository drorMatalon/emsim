# Saves the post-processing results into Outputs/: the S matrix as Touchstone, the far and near field monitors as CSV.

# =========================================
# Imports
# =========================================

import csv

import numpy as np

from lib.support.defines import GHZ

# =========================================
# Touchstone
# =========================================

def write_touchstone(s_matrix, params, paths):
    """Write the S matrix as a Touchstone v1 file <project>.sNp, in GHz with real / imaginary pairs,
    which CST, ADS and scikit-rf can read."""
    port_count = len(params["ports"])
    file_path = paths["outputs"] / f"{paths['root'].name}.s{port_count}p"
    lines = ["! emsim S-parameters", f"# GHz S RI R {params['ports'][0]['resistance']:g}"]
    for index, frequency in enumerate(params["frequencies"]):
        rows = get_touchstone_rows(s_matrix[:, :, index])
        lines.append(f"{frequency / GHZ:.9g} " + rows[0])
        lines += rows[1:]
    file_path.write_text("\n".join(lines) + "\n", encoding = "utf-8")
    return file_path

def get_touchstone_rows(s_at_frequency):
    """Order one frequency's S values the Touchstone v1 way: a 2-port is written S11 S21 S12 S22 on one line,
    other sizes row by row with at most 4 pairs per line."""
    port_count = s_at_frequency.shape[0]
    if port_count == 2:
        order = [(0, 0), (1, 0), (0, 1), (1, 1)]
        return [" ".join(format_pair(s_at_frequency[row, column]) for row, column in order)]
    rows = []
    for row in range(port_count):
        for start in range(0, port_count, 4):
            pairs = [format_pair(s_at_frequency[row, column]) for column in range(start, min(start + 4, port_count))]
            rows.append(" ".join(pairs))
    return rows

def format_pair(value):
    """Write one complex S value as its real and imaginary parts."""
    return f"{value.real:.9g} {value.imag:.9g}"

# =========================================
# CSV
# =========================================

def write_far_field_csv(far_field_result, far_field_monitor, paths):
    """Write one far field monitor as CSV: a row per (theta, phi) with E_theta, E_phi (complex peak values in V,
    at 1 m, for INCIDENT_POWER entering the port) and directivity."""
    file_path = paths["outputs"] / f"{far_field_monitor['name']}.csv"
    with open(file_path, "w", newline = "") as file:
        writer = csv.writer(file)
        writer.writerow(["theta_deg", "phi_deg", "e_theta_real", "e_theta_imag", "e_phi_real", "e_phi_imag", "directivity_dbi"])
        for theta_index, theta in enumerate(far_field_result["theta"]):
            for phi_index, phi in enumerate(far_field_result["phi"]):
                e_theta = far_field_result["e_theta"][theta_index, phi_index]
                e_phi = far_field_result["e_phi"][theta_index, phi_index]
                directivity = far_field_result["directivity_dbi"][theta_index, phi_index]
                writer.writerow([theta, phi, e_theta.real, e_theta.imag, e_phi.real, e_phi.imag, directivity])
    return file_path

def write_near_field_csv(near_field_result, near_field_monitor, paths):
    """Write one near field monitor as CSV: a row per grid point with Ex, Ey, Ez along the model axes
    (complex peak values in V/m, for INCIDENT_POWER entering the port) and |E|."""
    file_path = paths["outputs"] / f"{near_field_monitor['name']}.csv"
    e_field = near_field_result["e_field"]
    with open(file_path, "w", newline = "") as file:
        writer = csv.writer(file)
        writer.writerow(["x_mm", "y_mm", "z_mm", "ex_real", "ex_imag", "ey_real", "ey_imag", "ez_real", "ez_imag", "e_abs"])
        for x_index, x in enumerate(near_field_result["x"]):
            for y_index, y in enumerate(near_field_result["y"]):
                for z_index, z in enumerate(near_field_result["z"]):
                    point = e_field[:, x_index, y_index, z_index]
                    e_abs = np.sqrt(np.sum(np.abs(point) ** 2))
                    writer.writerow([x, y, z, point[0].real, point[0].imag, point[1].real, point[1].imag,
                                     point[2].real, point[2].imag, e_abs])
    return file_path
