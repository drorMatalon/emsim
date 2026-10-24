# Builds the full openEMS setup (geometry, mesh, ports, excitation, far field box, near field dumps) and runs it.

# =========================================
# Imports
# =========================================

import os
import subprocess
import sys
import time

from lib.common_functions import calculate_air_region, calculate_bounding_box
from lib.sim.geometry_builder import geometry_builder
from lib.sim.mesh_builder import mesh_builder
from lib.support.defines import AXES, END_CRITERIA, MAX_TIMESTEPS, NEAR_FIELD_DUMP_NAME, OPENEMS_DIR, OPENEMS_LOG_NAME, PML_CELLS
from lib.support.defines import VIEW_FILE_NAME, VIEWER_PATH

# The openEMS module loads its DLLs from the install folder, which Windows does not search by itself.
os.add_dll_directory(str(OPENEMS_DIR))
from openEMS import openEMS

# =========================================
# Simulation
# =========================================

def sim_engine(params, paths, port_name):
    """Build and run the FDTD simulation with one excited port; openEMS writes its results into Sim/<port_name>."""
    setup = create_simulation(params, port_name)
    log_path = paths["history"] / f"{OPENEMS_LOG_NAME}_{port_name}.log"
    print(f"{'Running':<9}: openEMS log in {log_path}", flush = True)
    start_time = time.time()
    run_with_log(setup["fdtd"], paths["sim"] / port_name, log_path)
    print(f"{'Finished':<9}: {time.time() - start_time:.0f} s", flush = True)

def run_with_log(fdtd, sim_path, log_path):
    """Run openEMS with its output sent to log_path instead of the terminal. openEMS prints from C++ straight to
    the process's file descriptors 1 and 2, which sys.stdout does not catch, so those descriptors are pointed at
    the log for the run and restored afterwards, even when the run fails."""
    sys.stdout.flush()
    sys.stderr.flush()
    terminal_stdout = os.dup(1)
    terminal_stderr = os.dup(2)
    with open(log_path, "w") as log:
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
        try:
            fdtd.Run(str(sim_path))
        finally:
            os.dup2(terminal_stdout, 1)
            os.dup2(terminal_stderr, 2)
            os.close(terminal_stdout)
            os.close(terminal_stderr)

def view_model(params, paths):
    """Build the full setup without running it and open it in AppCSXCAD, to check geometry, ports and mesh."""
    setup = create_simulation(params, params["ports"][0]["name"])
    view_path = paths["sim"] / VIEW_FILE_NAME
    setup["csx"].Write2XML(str(view_path))
    print(f"Opening {view_path} in AppCSXCAD", flush = True)
    subprocess.Popen([str(VIEWER_PATH), str(view_path)])

def create_simulation(params, port_name):
    """Create the CSX (geometry + mesh) and the FDTD around it; the order matters, since ports
    and the far field box are snapped to mesh lines, so the mesh must be finished before them.
    The port and nf2ff objects are returned too, since post-processing reads the result files through them."""
    csx = geometry_builder(params)
    mesh_builder(csx, params)
    fdtd = create_fdtd(params)
    fdtd.SetCSX(csx)
    setup = {
        "fdtd": fdtd,
        "csx": csx,
        "ports": add_ports(fdtd, params, port_name),
        "nf2ff": add_far_field_box(fdtd, params),
    }
    add_near_field_dumps(csx, params)
    return setup

def create_fdtd(params):
    """Create the FDTD engine with a Gaussian pulse covering the sweep band and PML on all six faces.
    The run stops when the energy drops by END_CRITERIA, or after MAX_TIMESTEPS as a safety limit."""
    fdtd = openEMS(NrTS = MAX_TIMESTEPS, EndCriteria = END_CRITERIA)
    center_frequency = (params["frequencies"][0] + params["frequencies"][-1]) / 2
    half_bandwidth = (params["frequencies"][-1] - params["frequencies"][0]) / 2
    fdtd.SetGaussExcite(center_frequency, half_bandwidth)
    fdtd.SetBoundaryCond([f"PML_{PML_CELLS}"] * 6)
    return fdtd

def add_ports(fdtd, params, port_name):
    """Add every port as a lumped port; only port_name is excited, the others just terminate and record,
    so one run gives a full column of the S matrix."""
    ports = []
    for index, port in enumerate(params["ports"]):
        if port["name"] == port_name:
            excite = 1
        else:
            excite = 0
        start = [port["x"][0], port["y"][0], port["z"][0]]
        stop = [port["x"][1], port["y"][1], port["z"][1]]
        ports.append(fdtd.AddLumpedPort(index + 1, port["resistance"], start, stop, port["direction"], excite = excite))
    return ports

def add_far_field_box(fdtd, params):
    """Add the NF2FF box halfway between the model and the air region edge, away from both the geometry and the PML.
    It is always added and records in the time domain, so any far field monitor can be calculated later without a new run."""
    bounding_box = calculate_bounding_box(params["boxes"])
    air_region = calculate_air_region(params["boxes"], params["mesh"]["air_margin"], params["frequencies"][0])
    start = []
    stop = []
    for axis in AXES:
        start.append((bounding_box[axis][0] + air_region[axis][0]) / 2)
        stop.append((bounding_box[axis][1] + air_region[axis][1]) / 2)
    return fdtd.CreateNF2FFBox(start = start, stop = stop)

def add_near_field_dumps(csx, params):
    """Record the E field on every near field plane at all sweep frequencies (dump_type 10 = E field in frequency domain,
    file_type 1 = HDF5). All planes go into every port's run, so changing a monitor's port or frequency needs no new run.
    Files are named by plane position, not monitor name, so renaming a monitor needs no new run either."""
    for index, near_field in enumerate(params["monitors"]["near_field"]):
        dump_name = f"{NEAR_FIELD_DUMP_NAME}_{index}"
        dump = csx.AddDump(dump_name, dump_type = 10, frequency = params["frequencies"], file_type = 1)
        start = [near_field["x"][0], near_field["y"][0], near_field["z"][0]]
        stop = [near_field["x"][-1], near_field["y"][-1], near_field["z"][-1]]
        dump.AddBox(start, stop)
