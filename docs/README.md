# emsim - REV_1

Antenna simulation environment based on openEMS.
You describe the antenna in `model.xml`; emsim builds it, simulates it, and saves the
S-parameters, far field and near field into the project folder.

## 1. Install

Follow [INSTALL.md](INSTALL.md): Python, openEMS, the Python packages, and a check run.

## 2. Use

Make a project folder holding a `model.xml` (start from [config_example/model.xml](config_example/model.xml))

Then run from the emsim folder:
```powershell
python emsin.py --root C:\path\to\project --view     # build the model and open viewer
python emsin.py --root C:\path\to\project            # Run whats needed
python emsin.py --root C:\path\to\project --force    # Force run everything
```

emsim remembers the last successful run abd performs only the requiered (Full sim, pre-proccessing, none) 

The project folder after a run:
```
project/
├── model.xml        your model
├── Outputs/         results: <project>.sNp, plots (.png), monitor data (.csv)
├── Sim/             raw openEMS data, one folder per port
└── History/         model_history.json (what ran last) and openems_<port>.log
```

## 3. model.xml rules

**Units:** length in mm, frequency in GHz, resistance in Ohm.
**Numbers** may be expressions: `1.6 + 20`, `-29.4/2 + 8.0`, `3.11/2` (only `+ - * / **`).
**Ranges** are `[low, high]`; a single value `v` means `[v, v]` (a flat side).
Unknown tags are errors, so a typo like `<mash>` is caught.

| Tag | Holds | Rules |
|---|---|---|
| `<box>` (1 or more) | `name`, `material`, `x`, `y`, `z` | material from `materials\materials.xml`; a dielectric needs size on all axes; `copper` must be flat; boxes may not overlap, except a conductor in / on a dielectric |
| `<port>` (1 or more) | `name`, `resistance`, `direction`, `x`, `y`, `z` | lumped port; `direction` is `x` / `y` / `z` and needs length along it; all ports share one resistance |
| `<frequency>` | `start`, `stop`, `points` | sweep start to stop, both included |
| `<mesh>` (optional) | `cells_per_wavelength` (20), `air_margin` (0.25) | at least 10 cells per wavelength; air margin in wavelengths at `start` |
| `<monitors>` (optional) | the monitors below | |

| Monitor | Holds | Gives |
|---|---|---|
| `<s_params>` | `port` | S_ii over frequency plot (the S matrix of all ports is always saved) |
| `<far_field>` | `name`, `port`, `frequency`, `resolution` [deg] | directivity polar cuts + CSV of E_theta, E_phi |
| `<near_field>` | `name`, `port`, `frequency`, `x`, `y`, `z`, `resolution` [mm] | \|E\| heatmaps + CSV of Ex, Ey, Ez |

Monitor rules: the port must exist, the frequency must be a sweep point, a near field is a plane
(exactly one constant axis) inside the air region, and the grid sizes are limited.
Fields are normalized to 1 W incident power at the excited port.

**Materials** (`materials\materials.xml`, shared by all projects): `PEC` (perfect conductor),
`copper` (lossy sheet, flat boxes only), `air`, `FR4` (er 4.4), `RO4350B` (er 3.66).
Add your own there; dielectrics are lossless for now.