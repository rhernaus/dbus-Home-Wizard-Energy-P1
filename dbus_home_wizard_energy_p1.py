#!/usr/bin/env python
# vim: ts=2 sw=2 et

"""
Enterprise Production code for DBus Home Wizard Energy P1 Service.

This module integrates the Home Wizard Energy P1 meter with Victron Energy's Venus OS
and GX devices. It provides automatic detection of single-phase and three-phase meters,
ensuring proper integration with the Victron system.

The service runs as a background process, connects to the Venus OS DBus, and
continuously updates meter data fetched from the meter's REST API.
"""

import configparser
import logging
import logging.handlers
import os
import platform
import signal
import sys
import time
from typing import Any, Callable, Dict, Optional

import requests

# Constants
DEFAULT_POLLING_INTERVAL_MS = 500
DEFAULT_SIGN_OF_LIFE_INTERVAL_MIN = 5
DEFAULT_REQUEST_TIMEOUT_SEC = 5
PRODUCT_ID_PVINVERTER = 0xA144
PRODUCT_ID_GRID = 45069
DEVICE_TYPE = 345  # ET340 Energy Meter
ALLOWED_ROLES = ['pvinverter', 'grid']
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.ini")
LOG_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "current.log")

try:
    from gi.repository import GLib as gobject
except ImportError:
    import gobject

# Add the velib_python directory from the submodule to the Python path
velib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'dbus-systemcalc-py', 'ext', 'velib_python')
sys.path.insert(1, velib_path)
try:
    from vedbus import VeDbusService
except ImportError:
    # Exit with error if vedbus is not available
    sys.stderr.write("Error: vedbus module not found. Please make sure the git submodule is initialized.\n")
    sys.stderr.write("Try running: git submodule update --init --recursive\n")
    sys.exit(1)


class DbusHomeWizzardEnergyP1Service:
    """
    DBus service for the Home Wizard Energy P1 meter.

    This class handles the integration between the Home Wizard Energy P1 meter
    and the Victron Energy system through DBus. It automatically detects whether
    the meter is single-phase or three-phase based on the meter's response data.

    The service retrieves data from the meter via HTTP and publishes it to the
    appropriate DBus paths, making it available to other components in the
    Victron Energy system.
    """

    # Static method to check if meter data indicates a three-phase meter
    @staticmethod
    def is_three_phase_meter(meter_data: Dict[str, Any]) -> bool:
        """
        Determines if the meter data is from a three-phase meter.

        This method analyzes the meter data to detect the presence of
        phase-specific voltage readings for L2 and L3, which indicates
        a three-phase meter.

        Args:
            meter_data: Dictionary containing meter data from the API

        Returns:
            bool: True if three-phase meter is detected, False for single-phase
        """
        return 'active_voltage_l2_v' in meter_data and 'active_voltage_l3_v' in meter_data

    def __init__(self, paths: Dict[str, Dict[str, Any]],
                 productname: str = 'Home Wizard Energy P1',
                 connection: str = 'Home Wizard Energy P1 HTTP JSON service'):
        """
        Initialize the DBus service for the Home Wizard Energy P1 meter.

        Args:
            paths: Dictionary of DBus paths to register
            productname: Name of the product to display
            connection: Description of the connection type
        """
        self.logger = self._setup_logging()
        self.config = self._get_config()
        self._validate_config(self.config)

        deviceinstance = int(self.config['DEFAULT']['DeviceInstance'])
        customname = self.config['DEFAULT']['CustomName']
        role = self.config['DEFAULT']['Role']

        if role in ALLOWED_ROLES:
            servicename = f"com.victronenergy.{role}"
        else:
            self.logger.error(f"Configured Role: {role} is not in the allowed list: {ALLOWED_ROLES}")
            sys.exit(1)

        productid = PRODUCT_ID_PVINVERTER if role == 'pvinverter' else PRODUCT_ID_GRID

        self._dbusservice = VeDbusService(f"{servicename}.http_{deviceinstance:02d}")
        self._paths = paths
        self._last_valid_data = {}  # Cache for last valid data
        self._lastUpdate = 0

        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', f"Unknown version, running on Python {platform.python_version()}")
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/DeviceType', DEVICE_TYPE)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.2)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', role)
        self._dbusservice.add_path('/Position', self._get_p1_position())
        self._dbusservice.add_path('/Serial', self._get_p1_serial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'],
                writeable=True, onchangecallback=self._handle_changed_value)

        # Set up periodic updates
        gobject.timeout_add(DEFAULT_POLLING_INTERVAL_MS, self._update)
        sign_of_life_interval = self._get_sign_of_life_interval()
        if sign_of_life_interval > 0:
            gobject.timeout_add(sign_of_life_interval * 60 * 1000, self._sign_of_life)

    def _setup_logging(self) -> logging.Logger:
        """
        Setup structured logging with context.

        Returns:
            logging.Logger: Configured logger instance
        """
        logger_name = "p1meter"
        return logging.getLogger(logger_name)

    def _get_p1_serial(self) -> str:
        """
        Retrieve the unique identifier from the meter.

        Returns:
            str: The unique identifier of the meter

        Raises:
            ValueError: If the response doesn't contain a unique_id
        """
        try:
            meter_data = self._get_p1_data()
            if not meter_data.get('unique_id'):
                self.logger.warning("Response does not contain 'unique_id', using default")
                return "Unknown_P1_Meter"
            return meter_data['unique_id']
        except Exception as e:
            self.logger.error(f"Error getting meter serial: {e}")
            return "Unknown_P1_Meter"

    def _get_config(self) -> configparser.ConfigParser:
        """
        Read and parse the configuration file.

        Returns:
            ConfigParser: Parsed configuration object
        """
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE_PATH)
        return config

    def _validate_config(self, config: configparser.ConfigParser) -> None:
        """
        Validate configuration settings.

        Args:
            config: Configuration object to validate

        Raises:
            ValueError: If configuration is invalid
        """
        required_keys = {
            'DEFAULT': ['AccessType', 'DeviceInstance', 'Role'],
            'ONPREMISE': ['Host']
        }

        for section, keys in required_keys.items():
            if section not in config:
                raise ValueError(f"Missing section '{section}' in config")
            for key in keys:
                if key not in config[section]:
                    raise ValueError(f"Missing key '{key}' in section '{section}'")

        # Additional validation
        if config['DEFAULT']['Role'] not in ALLOWED_ROLES:
            raise ValueError(f"Invalid Role: {config['DEFAULT']['Role']}")

    def _get_sign_of_life_interval(self) -> int:
        """
        Get the interval for periodic log messages.

        Returns:
            int: Interval in minutes between sign-of-life log messages
        """
        value = self.config['DEFAULT'].get('SignOfLifeLog')
        return int(value) if value else DEFAULT_SIGN_OF_LIFE_INTERVAL_MIN

    def _get_p1_position(self) -> int:
        """
        Get the configured position value for the meter.

        Returns:
            int: Position number or 0 if not configured
        """
        value = self.config['DEFAULT'].get('Position')
        return int(value) if value else 0

    def _get_p1_status_url(self) -> str:
        """
        Construct the API URL based on configuration.

        Returns:
            str: Fully qualified URL for the meter API

        Raises:
            ValueError: If the configured access type is not supported
        """
        accessType = self.config['DEFAULT']['AccessType']
        if accessType == 'OnPremise':
            return f"http://{self.config['ONPREMISE']['Host']}/api/v1/data"
        else:
            raise ValueError(f"AccessType {accessType} is not supported")

    def _get_p1_data(self) -> Dict[str, Any]:
        """
        Fetch current meter data from the API.

        Returns:
            dict: JSON response from the meter API or cached data if request fails

        Raises:
            ConnectionError: If the meter doesn't respond
            ValueError: If the response cannot be parsed as JSON
        """
        try:
            URL = self._get_p1_status_url()
            meter_r = requests.get(url=URL, timeout=DEFAULT_REQUEST_TIMEOUT_SEC)
            if not meter_r:
                raise ConnectionError(f"No response from Home Wizard Energy - {URL}")
            meter_data = meter_r.json()
            if not meter_data:
                raise ValueError("Converting response to JSON failed")

            # Cache the valid data
            self._last_valid_data = meter_data.copy()
            return meter_data
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error when connecting to meter: {e}")
            # Return cached data if available
            if self._last_valid_data:
                self.logger.warning("Using cached data due to connection error")
                return self._last_valid_data
            raise

    def _sign_of_life(self) -> bool:
        """
        Periodically log the service status to confirm it's still running.

        Returns:
            bool: Always True to keep the timer active
        """
        self.logger.info("--- Start: sign of life ---")
        self.logger.info(f"Last _update() call: {self._lastUpdate}")
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
            meter_data = self._get_p1_data()

            # Skip update if no valid data
            if not meter_data:
                self.logger.warning("No valid meter data available for update")
                return True

            # Update the DBus service with the meter data
            self._update_dbus_paths(meter_data)
            self._lastUpdate = time.time()

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
        if self.is_three_phase_meter(meter_data):
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


def get_log_level() -> int:
    """
    Get the configured log level from config.ini.

    Returns:
        int: The Python logging level (e.g., logging.INFO)
    """
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)
    logLevelString = config['DEFAULT'].get('LogLevel')
    level = logging.getLevelName(logLevelString) if logLevelString else logging.INFO
    return level


def setup_logging() -> None:
    """
    Set up application logging with file and console handlers.
    """
    logging.basicConfig(
        format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=get_log_level(),
        handlers=[
            logging.FileHandler(LOG_FILE_PATH),
            logging.StreamHandler()
        ]
    )


def main() -> None:
    """
    Main entry point for the application.

    Initializes logging, sets up the DBus service, and starts the main event loop.
    This function will run indefinitely until interrupted.
    """
    setup_logging()
    logger = logging.getLogger("p1meter")

    try:
        logger.info("Starting Home Wizard Energy P1 DBus service")

        # Set up signal handling for graceful shutdown
        mainloop = gobject.MainLoop()

        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down")
            mainloop.quit()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Set up DBus main loop
        from dbus.mainloop.glib import DBusGMainLoop

        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        # Define formatters for different units
        _kwh = lambda p, v: f"{v:.2f} kWh"
        _a = lambda p, v: f"{v:.1f} A"
        _w = lambda p, v: f"{v:.1f} W"
        _v = lambda p, v: f"{v:.1f} V"

        # Create the DBus service with all the paths we need
        pvac_output = DbusHomeWizzardEnergyP1Service(
            paths={
                '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh},
                '/Ac/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
                '/Ac/Power': {'initial': 0, 'textformat': _w},

                '/Ac/Current': {'initial': 0, 'textformat': _a},
                '/Ac/Voltage': {'initial': 0, 'textformat': _v},

                '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
                '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
            })

        logger.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop.run()
    except Exception as e:
        logger.critical(f"Error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
