#!/usr/bin/env python3
"""
Home Wizard Energy P1 meter integration for Victron Energy's Venus OS.

This is the main entry point script that runs the integration.
"""

import os
import sys

# Ensure the parent directory is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Also ensure the vedbus module can be found
velib_path = os.path.join(script_dir, 'dbus-systemcalc-py', 'ext', 'velib_python')
if velib_path not in sys.path:
    sys.path.insert(1, velib_path)

from homewizard_energy.__main__ import main

if __name__ == "__main__":
    sys.exit(main())