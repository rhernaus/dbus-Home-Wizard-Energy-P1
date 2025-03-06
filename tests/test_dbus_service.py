#!/usr/bin/env python
"""
Integration tests for Home Wizard Energy P1 meter integration.
"""

import os
import sys
import unittest

# Add the parent directory to Python path
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the refactored code
from homewizard_energy.meter_client import HomeWizardP1Client


class TestHomeWizardP1Client(unittest.TestCase):
    """Tests for the Home Wizard P1 client."""

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

        # Use the static method from the client class
        self.assertFalse(HomeWizardP1Client.is_three_phase_meter(meter_data))

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

        # Use the static method from the client class
        self.assertTrue(HomeWizardP1Client.is_three_phase_meter(meter_data))


if __name__ == '__main__':
    unittest.main()

