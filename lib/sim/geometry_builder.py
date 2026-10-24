# Builds the openEMS geometry (CSX) from the parsed params: one property per material, then its boxes.

# =========================================
# Imports
# =========================================

from CSXCAD import ContinuousStructure

from lib.support.defines import CONDUCTOR_PRIORITY, DIELECTRIC_PRIORITY, METAL_SHEET_THICKNESS

# =========================================
# Classes and functions
# =========================================

def geometry_builder(params):
    """Create the CSX structure holding every material and box of the model."""
    csx = ContinuousStructure()
    properties = create_material_properties(csx, params["materials"])
    for box in params["boxes"]:
        add_box(properties, box, params["materials"])
    return csx

def create_material_properties(csx, materials):
    """Create one CSX property per used material; the property type decides how openEMS treats the material.
    A pec is a perfect conductor, a metal is a lossy sheet of fixed thickness, a dielectric has epsilon_r and mu_r."""
    properties = {}
    for name, material in materials.items():
        if material["type"] == "pec":
            properties[name] = csx.AddMetal(name)
        elif material["type"] == "metal":
            properties[name] = csx.AddConductingSheet(name, conductivity = material["sigma"],
                                                      thickness = METAL_SHEET_THICKNESS)
        else:
            properties[name] = csx.AddMaterial(name, epsilon = material["epsilon_r"], mue = material["mu_r"])
    return properties

def add_box(properties, box, materials):
    """Add one box to its material's property; conductors get the higher priority, so they win inside a dielectric."""
    if materials[box["material"]]["type"] == "dielectric":
        priority = DIELECTRIC_PRIORITY
    else:
        priority = CONDUCTOR_PRIORITY
    start = [box["x"][0], box["y"][0], box["z"][0]]
    stop = [box["x"][1], box["y"][1], box["z"][1]]
    properties[box["material"]].AddBox(start, stop, priority = priority)
