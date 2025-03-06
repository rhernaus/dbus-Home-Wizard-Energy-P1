"""
DBus service integration for Home Wizard Energy P1 meter.
"""

import logging
import os
import platform
import sys
import time
from typing import Any, Callable, Dict, Optional

# Add the velib_python directory from the submodule to the Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
velib_path = os.path.join(parent_dir, 'dbus-systemcalc-py', 'ext', 'velib_python')
if velib_path not in sys.path:
    sys.path.insert(1, velib_path)

# Check for vedbus
try:
    from vedbus import VeDbusService
except ImportError:
    sys.stderr.write("Error: vedbus module not found. Please make sure the git submodule is initialized.\n")
    sys.stderr.write("Try running: git submodule update --init --recursive\n")
    sys.exit(1)

# Constants
DEFAULT_POLLING_INTERVAL_MS = 500
PRODUCT_ID_PVINVERTER = 0xA144
PRODUCT_ID_GRID = 45069
DEVICE_TYPE = 345  # ET340 Energy Meter


class DbusHomeWizardP1Service:
    """
    DBus service for the Home Wizard Energy P1 meter.

    This class handles the integration between the Home Wizard Energy P1 meter
    and the Victron Energy system through DBus. It automatically detects whether
    the meter is single-phase or three-phase based on the meter's response data.

    The service retrieves data from the meter via an API client and publishes it to the
    appropriate DBus paths, making it available to other components in the
    Victron Energy system.
    """

    def __init__(self,
                 meter_client,
                 config_manager,
                 gobject_mainloop,
                 paths: Dict[str, Dict[str, Any]],
                 productname: str = 'Home Wizard Energy P1',
                 connection: str = 'Home Wizard Energy P1 HTTP JSON service'):
        """
        Initialize the DBus service for the Home Wizard Energy P1 meter.

        Args:
            meter_client: Client for communicating with the meter
            config_manager: Configuration manager
            gobject_mainloop: GObject main loop for event handling
            paths: Dictionary of DBus paths to register
            productname: Name of the product to display
            connection: Description of the connection type
        """
        self.logger = logging.getLogger("p1meter.dbus")
        self.meter_client = meter_client
        self.config = config_manager
        self.gobject = gobject_mainloop

        self._paths = paths
        self._last_update = 0

        # Get configuration values
        deviceinstance = self.config.get_device_instance()
        customname = self.config.get_custom_name()
        role = self.config.get_role()
        productid = PRODUCT_ID_PVINVERTER if role == 'pvinverter' else PRODUCT_ID_GRID

        # Create the DBus service
        servicename = f"com.victronenergy.{role}"
        self._dbusservice = VeDbusService(f"{servicename}.http_{deviceinstance:02d}")

        # Set up DBus paths
        self._setup_dbus_paths(productname, connection, customname, role, productid)

        # Set up periodic updates
        self.gobject.timeout_add(DEFAULT_POLLING_INTERVAL_MS, self._update)
        sign_of_life_interval = self.config.get_sign_of_life_interval()
        if sign_of_life_interval > 0:
            self.gobject.timeout_add(sign_of_life_interval * 60 * 1000, self._sign_of_life)

    def _setup_dbus_paths(self, productname: str, connection: str,
                          customname: str, role: str, productid: int) -> None:
        """
        Set up the DBus paths for the service.

        Args:
            productname: Name of the product
            connection: Connection description
            customname: Custom name for the device
            role: Role (grid or pvinverter)
            productid: Product ID
        """
        # Management paths
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion',
                                   f"Version {platform.python_version()}")
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Mandatory paths
        self._dbusservice.add_path('/DeviceInstance', self.config.get_device_instance())
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/DeviceType', DEVICE_TYPE)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.2)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', role)
        self._dbusservice.add_path('/Position', self.config.get_position())
        self._dbusservice.add_path('/Serial', self.meter_client.get_meter_serial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        # Add the paths from the provided dictionary
        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'],
                writeable=True, onchangecallback=self._handle_changed_value)

    def _sign_of_life(self) -> bool:
        """
        Periodically log the service status to confirm it's still running.

        Returns:
            bool: Always True to keep the timer active
        """
        self.logger.info("--- Start: sign of life ---")
        self.logger.info(f"Last _update() call: {self._last_update}")
        self.logger.info(f"Last '/Ac/Power': {self._dbusservice['/Ac/Power']}")
        self.logger.info("--- End: sign of life ---")
        return True

    def _update(self) -> bool:
        """
        Update the DBus service with current meter data.

        This method is called periodically by the GLib main loop.
        It fetches the latest data from the meter and updates all
        relevant DBus paths with the new values.

        Returns:
            bool: Always True to keep the timer active
        """
        try:
            meter_data = self.meter_client.get_data()

            # Skip update if no valid data
            if not meter_data:
                self.logger.warning("No valid meter data available for update")
                return True

            # Update the DBus service with the meter data
            self._update_dbus_paths(meter_data)
            self._last_update = time.time()

        except Exception as e:
            self.logger.error(f"Error updating DBus service: {e}", exc_info=True)
        return True

    def _update_dbus_paths(self, meter_data: Dict[str, Any]) -> None:
        """
        Update all DBus paths with current meter data.

        Args:
            meter_data: Dictionary containing meter data from the API
        """
        # Auto-detect meter type based on presence of three-phase keys
        if self.meter_client.is_three_phase_meter(meter_data):
            # Three-phase meter detected
            self._update_three_phase_values(meter_data)
        else:
            # Single-phase meter
            self._update_single_phase_values(meter_data)

    def _update_three_phase_values(self, meter_data: Dict[str, Any]) -> None:
        """
        Update DBus paths for three-phase meter.

        Args:
            meter_data: Dictionary containing meter data from the API
        """
        self._dbusservice['/Ac/Power'] = meter_data['active_power_w']
        self._dbusservice['/Ac/L1/Voltage'] = meter_data['active_voltage_l1_v']
        self._dbusservice['/Ac/L2/Voltage'] = meter_data['active_voltage_l2_v']
        self._dbusservice['/Ac/L3/Voltage'] = meter_data['active_voltage_l3_v']
        self._dbusservice['/Ac/L1/Current'] = meter_data['active_current_l1_a']
        self._dbusservice['/Ac/L2/Current'] = meter_data['active_current_l2_a']
        self._dbusservice['/Ac/L3/Current'] = meter_data['active_current_l3_a']
        self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_l1_w']
        self._dbusservice['/Ac/L2/Power'] = meter_data['active_power_l2_w']
        self._dbusservice['/Ac/L3/Power'] = meter_data['active_power_l3_w']

        # Convert kWh to MWh
        forward_energy = meter_data['total_power_import_kwh'] / 1000
        reverse_energy = meter_data['total_power_export_kwh'] / 1000
        self._dbusservice['/Ac/Energy/Forward'] = forward_energy
        self._dbusservice['/Ac/Energy/Reverse'] = reverse_energy

    def _update_single_phase_values(self, meter_data: Dict[str, Any]) -> None:
        """
        Update DBus paths for single-phase meter.

        Args:
            meter_data: Dictionary containing meter data from the API
        """
        self._dbusservice['/Ac/Power'] = meter_data['active_power_w']
        self._dbusservice['/Ac/L1/Voltage'] = meter_data['active_voltage_l1_v']
        self._dbusservice['/Ac/L1/Current'] = meter_data['active_current_l1_a']
        self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_l1_w']

        # Convert kWh to MWh
        forward_energy = meter_data['total_power_import_kwh'] / 1000
        reverse_energy = meter_data['total_power_export_kwh'] / 1000
        self._dbusservice['/Ac/Energy/Forward'] = forward_energy
        self._dbusservice['/Ac/Energy/Reverse'] = reverse_energy
        self._dbusservice['/Ac/L1/Energy/Forward'] = forward_energy
        self._dbusservice['/Ac/L1/Energy/Reverse'] = reverse_energy

    def _handle_changed_value(self, path: str, value: Any) -> bool:
        """
        Handle external updates to DBus service values.

        This callback is triggered when another DBus client updates
        one of our values.

        Args:
            path: The DBus path that was changed
            value: The new value

        Returns:
            bool: True to accept the change
        """
        self.logger.debug(f"someone else updated {path} to {value}")
        return True