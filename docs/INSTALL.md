# Installing emsim (Windows)

Four steps: Python, openEMS, the Python packages, then a check run.
All commands are PowerShell.

```
 1. Python 3.10 - 3.14      -> python.org installer
 2. openEMS                 -> zip extracted to C:\opt\openEMS
 3. Python packages         -> openEMS + CSXCAD wheels (from the zip), then requirements.txt
 4. Check                   -> import test, then run the example project
```

## 1. Python

Check if Python is already there:
```powershell
python --version
```
If it prints `Python 3.10` up to `3.14`, skip to step 2 (3.14 is what emsim is tested with).
Otherwise install it from <https://www.python.org/downloads/windows/>, and in the installer
tick **"Add python.exe to PATH"**. Open a new PowerShell window and run `python --version` again.

> If you have several Pythons, use the full path everywhere below instead of `python`,
> e.g. `C:\Python314\python.exe`.

## 2. openEMS

1. Download the Windows x64 zip (`openEMS_x64_...zip`) from
   <https://github.com/thliebig/openEMS-Project/releases>.
2. Extract it so that `C:\opt\openEMS\openEMS.exe` and `C:\opt\openEMS\AppCSXCAD.exe` exist.

emsim looks for openEMS in `C:\opt\openEMS`. Another folder works too: change `OPENEMS_DIR` in
`lib\support\defines.py`.

## 3. Python packages

openEMS and CSXCAD are not on PyPI; their wheels come inside the zip, in `C:\opt\openEMS\python`.
Pick the two whose `cpXXX` matches your Python (`cp314` = Python 3.14):
```powershell
python -m pip install C:\opt\openEMS\python\csxcad-0.6.3-cp314-cp314-win_amd64.whl
python -m pip install C:\opt\openEMS\python\openems-0.0.36-cp314-cp314-win_amd64.whl
```
Then the rest, from the emsim folder:
```powershell
python -m pip install -r docs\requirements.txt
```

## 4. Check

Import test (should print `ok`):
```powershell
python -c "import os; os.add_dll_directory(r'C:\opt\openEMS'); import CSXCAD, openEMS; print('ok')"
```

Run the example project: copy `docs\config_example\model.xml` into a new empty folder, then:
```powershell
python emsin.py --root C:\path\to\that\folder --view    # opens the model in AppCSXCAD
python emsin.py --root C:\path\to\that\folder           # full run, about 2 minutes
```
A good run ends with `Done, history saved` and a list of files in the folder's `Outputs\`.