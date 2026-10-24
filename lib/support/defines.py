# Important defines shared by all modules: paths, constants, units, limits, geometry and mesh settings.

# =========================================
# Imports
# =========================================

from pathlib import Path

# =========================================
# Paths
# =========================================

MATERIALS_PATH = Path(__file__).resolve().parents[2] / "materials" / "materials.xml"
OPENEMS_DIR = Path(r"C:\opt\openEMS")
VIEWER_PATH = OPENEMS_DIR / "AppCSXCAD.exe"

MODEL_FILE_NAME = "model.xml"
HISTORY_DIR_NAME = "History"
SIM_DIR_NAME = "Sim"
OUTPUTS_DIR_NAME = "Outputs"
HISTORY_FILE_NAME = "model_history.json"
VIEW_FILE_NAME = "view.xml"
OPENEMS_LOG_NAME = "openems"
NEAR_FIELD_DUMP_NAME = "near_field_plane"

# =========================================
# Physical constants
# =========================================

LIGHT_SPEED = 299792458.0

# =========================================
# Units
# =========================================

GHZ = 1e9
MM = 1e-3
AXES = ("x", "y", "z")

# =========================================
# Model limits
# =========================================

MAX_MODEL_SIZE_WAVELENGTHS = 10
MIN_CELLS_PER_WAVELENGTH = 10
MAX_FAR_FIELD_POINTS = 100000
MAX_NEAR_FIELD_POINTS = 100000

# =========================================
# Mesh defaults
# =========================================

DEFAULT_CELLS_PER_WAVELENGTH = 20
DEFAULT_AIR_MARGIN = 0.25

# =========================================
# Geometry
# =========================================

METAL_SHEET_THICKNESS = 35e-6
CONDUCTOR_PRIORITY = 10
DIELECTRIC_PRIORITY = 0

# =========================================
# Mesh
# =========================================

MIN_CELLS_PER_DIELECTRIC = 4
MESH_GRADING_RATIO = 1.4
PML_CELLS = 8
MESH_SNAP_TOLERANCE = 1e-6

# =========================================
# Simulation
# =========================================

MAX_TIMESTEPS = 200000
END_CRITERIA = 1e-4

# =========================================
# Post-processing
# =========================================

INCIDENT_POWER = 1.0
