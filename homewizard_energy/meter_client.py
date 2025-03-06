"""
Home Wizard Energy P1 meter API client.
"""

import logging
import random
from typing import Any, Dict, Optional

import requests

# Constants
DEFAULT_REQUEST_TIMEOUT_SEC = 5


class HomeWizardP1Client:
    """
    Client for communicating with the Home Wizard Energy P1 meter API.

    This class handles the HTTP communication with the meter's API
    and provides methods to retrieve meter data.
    """

    def __init__(self, api_url: str, mock_mode: bool = False):
        """
        Initialize the meter client.

        Args:
            api_url: The URL of the meter's API endpoint
            mock_mode: Whether to use mock data instead of making real API calls
        """
        self.logger = logging.getLogger("p1meter.client")
        self.api_url = api_url
        self.mock_mode = mock_mode
        self._last_valid_data: Dict[str, Any] = {}

    def get_data(self) -> Dict[str, Any]:
        """
        Retrieve meter data from the API.

        Returns:
            Dict[str, Any]: Meter data as a dictionary

        Raises:
            ConnectionError: If the meter doesn't respond
            ValueError: If the response cannot be parsed as JSON
        """
        if self.mock_mode:
            return self._get_mock_data()

        try:
            self.logger.debug(f"Requesting data from {self.api_url}")
            response = requests.get(url=self.api_url, timeout=DEFAULT_REQUEST_TIMEOUT_SEC)
            if not response:
                raise ConnectionError(f"No response from Home Wizard Energy - {self.api_url}")

            data = response.json()
            if not data:
                raise ValueError("Converting response to JSON failed")

            # Cache the valid data
            self._last_valid_data = data.copy()
            self.logger.debug("Successfully retrieved meter data")
            return data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error when connecting to meter: {e}")
            # Return cached data if available
            if self._last_valid_data:
                self.logger.warning("Using cached data due to connection error")
                return self._last_valid_data
            raise

    def _get_mock_data(self) -> Dict[str, Any]:
        """
        Generate mock meter data for testing and development.

        Returns:
            Dict[str, Any]: Mock meter data
        """
        # Generate some random values that vary slightly each time
        power = random.randint(800, 1200)
        voltage_l1 = random.uniform(225.0, 235.0)
        current_l1 = power / voltage_l1

        # Decide randomly if we're simulating a single or three-phase meter
        three_phase = random.choice([True, False])

        data = {
            'unique_id': 'MOCK_P1_METER_123',
            'active_power_w': power,
            'active_voltage_l1_v': round(voltage_l1, 1),
            'active_current_l1_a': round(current_l1, 2),
            'active_power_l1_w': power,
            'total_power_import_kwh': 5000 + (random.random() * 10),
            'total_power_export_kwh': 100 + (random.random() * 5),
        }

        # Add three-phase data if simulating a three-phase meter
        if three_phase:
            voltage_l2 = random.uniform(225.0, 235.0)
            voltage_l3 = random.uniform(225.0, 235.0)
            power_l2 = random.randint(800, 1200)
            power_l3 = random.randint(800, 1200)
            current_l2 = power_l2 / voltage_l2
            current_l3 = power_l3 / voltage_l3

            data.update({
                'active_power_w': power + power_l2 + power_l3,
                'active_voltage_l2_v': round(voltage_l2, 1),
                'active_voltage_l3_v': round(voltage_l3, 1),
                'active_current_l2_a': round(current_l2, 2),
                'active_current_l3_a': round(current_l3, 2),
                'active_power_l2_w': power_l2,
                'active_power_l3_w': power_l3,
            })

        self.logger.debug(f"Generated mock data (three-phase: {three_phase})")
        return data

    def get_cached_data(self) -> Dict[str, Any]:
        """
        Get the last successfully retrieved data.

        Returns:
            Dict[str, Any]: Last valid meter data, or empty dict if none
        """
        return self._last_valid_data

    def get_meter_serial(self) -> str:
        """
        Get the unique identifier from the meter.

        Returns:
            str: The meter's unique identifier or a default if not available
        """
        if self.mock_mode:
            return "MOCK_P1_METER_123"

        try:
            data = self.get_data()
            if not data.get('unique_id'):
                self.logger.warning("Response does not contain 'unique_id', using default")
                return "Unknown_P1_Meter"
            return data['unique_id']
        except Exception as e:
            self.logger.error(f"Error getting meter serial: {e}")
            return "Unknown_P1_Meter"

    @staticmethod
    def is_three_phase_meter(meter_data: Dict[str, Any]) -> bool:
        """
        Determine if the meter data is from a three-phase meter.

        This method analyzes the meter data to detect the presence of
        phase-specific voltage readings for L2 and L3, which indicates
        a three-phase meter.

        Args:
            meter_data: Dictionary containing meter data from the API

        Returns:
            bool: True if a three-phase meter is detected, False for single-phase
        """
        return 'active_voltage_l2_v' in meter_data and 'active_voltage_l3_v' in meter_data