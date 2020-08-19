#!/usr/bin/env python3
import datetime as dt
import runpy
from pathlib import Path
import sys
import warnings

proj_root = Path(__file__).resolve().parent
version_path = proj_root / "catpy" / "version.py"

old_str = runpy.run_path(version_path)["__version__"]

new_str = dt.date.today().strftime("%Y.%m.%d")

if not old_str.startswith(new_str):
    print(new_str)
    sys.exit()

trailing = old_str.split(".")[3:]
if trailing:
    suffix = int(trailing[0]) + 1
    if suffix > 9:
        warnings.warn(
            f"Sub-day release ('{suffix}') has >1 digit, which will break version ordering."
        )
else:
    suffix = 1

print(f"{new_str}.{suffix}")
