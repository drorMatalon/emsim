# Calculates the S matrix over the sweep from the port voltages and currents openEMS recorded in each Sim/<port> run.

# =========================================
# Imports
# =========================================

import numpy as np

# =========================================
# Classes and functions
# =========================================

def s_parameters(ports, params, paths):
    """Build the S matrix (row = receiving port, column = excited port, last axis = frequency).
    The run with port j excited gives column j: S_ij = b_i / a_j, the wave leaving port i over the wave entering port j."""
    frequencies = np.array(params["frequencies"])
    port_count = len(ports)
    s_matrix = np.zeros((port_count, port_count, len(frequencies)), dtype = complex)
    for column, excited_port in enumerate(params["ports"]):
        sim_path = paths["sim"] / excited_port["name"]
        calculate_port_waves(ports, sim_path, frequencies)
        incident_wave = ports[column].uf_inc
        for row, port in enumerate(ports):
            s_matrix[row, column] = port.uf_ref / incident_wave
    return s_matrix

def calculate_port_waves(ports, sim_path, frequencies):
    """Read every port's recorded voltage and current from one run and split them into incident and reflected waves.
    CalcPort does a DFT of the time signals at the sweep frequencies and fills port.uf_inc / port.uf_ref."""
    for port in ports:
        port.CalcPort(str(sim_path), frequencies)

def calculate_reflection_db(s_matrix, params, port_name):
    """|S_ii| in dB over the sweep for one port; its minimum is the resonance notch."""
    port_index = [port["name"] for port in params["ports"]].index(port_name)
    return 20 * np.log10(np.abs(s_matrix[port_index, port_index]))
