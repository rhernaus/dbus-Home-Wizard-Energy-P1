#!/usr/bin/env python
"""
Integration tests for DbusHomeWizzardEnergyP1Service.
These tests subclass the service to override _getP1Data.
"""

import unittest
import time
import logging
import os
import sys

# Add the parent directory to Python path 
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import the main module
from dbus_home_wizard_energy_p1 import DbusHomeWizzardEnergyP1Service

class TestDbusHomeWizzardEnergyP1Service(unittest.TestCase):
    """Tests for the DBus Home Wizzard Energy P1 Service."""
    
    def test_detect_single_phase(self):
        """Test that single-phase meters are correctly detected based on JSON data."""
        # Single-phase meter data (no keys for L2 and L3 voltage)
        meter_data = {
            'active_power_w': 1000,
            'active_voltage_l1_v': 230,
            'active_current_l1_a': 4.35,
            'active_power_l1_w': 1000,
            'total_power_import_kwh': 5000,
            'total_power_export_kwh': 100
        }
        
        # Use the static method from the service class
        self.assertFalse(DbusHomeWizzardEnergyP1Service.is_three_phase_meter(meter_data))

    def test_detect_three_phase(self):
        """Test that three-phase meters are correctly detected based on JSON data."""
        # Three-phase meter data with L2 and L3 keys
        meter_data = {
            'active_power_w': 3000,
            'active_voltage_l1_v': 230,
            'active_voltage_l2_v': 230,
            'active_voltage_l3_v': 230,
            'active_current_l1_a': 4.35,
            'active_current_l2_a': 4.35,
            'active_current_l3_a': 4.35,
            'active_power_l1_w': 1000,
            'active_power_l2_w': 1000,
            'active_power_l3_w': 1000,
            'total_power_import_kwh': 15000,
            'total_power_export_kwh': 300
        }
        
        # Use the static method from the service class
        self.assertTrue(DbusHomeWizzardEnergyP1Service.is_three_phase_meter(meter_data))


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
