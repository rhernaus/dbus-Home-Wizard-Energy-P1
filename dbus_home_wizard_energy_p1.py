#!/usr/bin/env python
# vim: ts=2 sw=2 et

import os
import sys
import time
import logging
import logging.handlers
import platform
import configparser
import requests

try:
    from gi.repository import GLib as gobject
except ImportError:
    import gobject

"""
Enterprise Production code for DBus Home Wizzard Energy P1 Service.
Handles service initialization, configuration loading, and data updating.
"""

# Add the velib_python directory from the submodule to the Python path
velib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                          'dbus-systemcalc-py', 'ext', 'velib_python')
sys.path.insert(1, velib_path)
try:
    from vedbus import VeDbusService
except ImportError:
    # For testing purposes without the dbus module
    class VeDbusService:
        def __init__(self, *args, **kwargs):
            pass


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
    def is_three_phase_meter(meter_data):
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

    def __init__(self, paths, productname='Home Wizard Energy P1', connection='Home Wizard Energy P1 HTTP JSON service'):
        """
        Initialize the DBus service for the Home Wizard Energy P1 meter.
        
        Args:
            paths: Dictionary of DBus paths to register
            productname: Name of the product to display
            connection: Description of the connection type
        """
        self.config = self._getConfig()
        deviceinstance = int(self.config['DEFAULT']['DeviceInstance'])
        customname = self.config['DEFAULT']['CustomName']
        role = self.config['DEFAULT']['Role']

        allowed_roles = ['pvinverter', 'grid']
        if role in allowed_roles:
            servicename = f"com.victronenergy.{role}"
        else:
            logging.error(f"Configured Role: {role} is not in the allowed list")
            sys.exit(1)

        productid = 0xA144 if role == 'pvinverter' else 45069

        self._dbusservice = VeDbusService(f"{servicename}.http_{deviceinstance:02d}")

        self._paths = paths

        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', f"Unkown version, and running on Python {platform.python_version()}")
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/DeviceType', 345)  # Found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Energy Meter
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.2)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', role)
        self._dbusservice.add_path('/Position', self._getP1Position())
        self._dbusservice.add_path('/Serial', self._getP1Serial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

        self._lastUpdate = 0

        gobject.timeout_add(500, self._update)
        gobject.timeout_add(self._getSignOfLifeInterval() * 60 * 1000, self._signOfLife)

    def _getP1Serial(self):
        """
        Retrieve the unique identifier from the meter.
        
        Returns:
            str: The unique identifier of the meter
        
        Raises:
            ValueError: If the response doesn't contain a unique_id
        """
        meter_data = self._getP1Data()
        if not meter_data.get('unique_id'):
            raise ValueError("Response does not contain 'unique_id'")
        return meter_data['unique_id']

    def _getConfig(self):
        """
        Read and parse the configuration file.
        
        Returns:
            ConfigParser: Parsed configuration object
        """
        config = configparser.ConfigParser()
        config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.ini"))
        return config

    def _getSignOfLifeInterval(self):
        """
        Get the interval for periodic log messages.
        
        Returns:
            int: Interval in minutes between sign-of-life log messages
        """
        value = self.config['DEFAULT'].get('SignOfLifeLog')
        return int(value) if value else 0

    def _getP1Position(self):
        """
        Get the configured position value for the meter.
        
        Returns:
            int: Position number or 0 if not configured
        """
        value = self.config['DEFAULT'].get('Position')
        return int(value) if value else 0

    def _getP1StatusUrl(self):
        """
        Construct the API URL based on configuration.
        
        Returns:
            str: Fully qualified URL for the meter API
            
        Raises:
            ValueError: If the configured access type is not supported
        """
        accessType = self.config['DEFAULT']['AccessType']
        if accessType == 'OnPremise':
            URL = f"http://{self.config['ONPREMISE']['Host']}/api/v1/data"
        else:
            raise ValueError(f"AccessType {accessType} is not supported")
        return URL

    def _getP1Data(self):
        """
        Fetch current meter data from the API.
        
        Returns:
            dict: JSON response from the meter API
            
        Raises:
            ConnectionError: If the meter doesn't respond
            ValueError: If the response cannot be parsed as JSON
        """
        URL = self._getP1StatusUrl()
        meter_r = requests.get(url=URL, timeout=5)
        if not meter_r:
            raise ConnectionError(f"No response from Home Wizard Energy - {URL}")
        meter_data = meter_r.json()
        if not meter_data:
            raise ValueError("Converting response to JSON failed")
        return meter_data

    def _signOfLife(self):
        """
        Periodically log the service status to confirm it's still running.
        
        Returns:
            bool: Always True to keep the timer active
        """
        logging.info("--- Start: sign of life ---")
        logging.info(f"Last _update() call: {self._lastUpdate}")
        logging.info(f"Last '/Ac/Power': {self._dbusservice['/Ac/Power']}")
        logging.info("--- End: sign of life ---")
        return True

    def _update(self):
        """
        Update the DBus service with current meter data.
        
        This method is called periodically by the GLib main loop.
        It fetches the latest data from the meter and updates all
        relevant DBus paths with the new values.
        
        Returns:
            bool: Always True to keep the timer active
        """
        try:
            meter_data = self._getP1Data()

            # Auto-detect meter type based on presence of three-phase keys
            if self.is_three_phase_meter(meter_data):
                # Three-phase meter detected
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
                forward_energy = meter_data['total_power_import_kwh'] / 1000
                reverse_energy = meter_data['total_power_export_kwh'] / 1000
                self._dbusservice['/Ac/Energy/Forward'] = forward_energy
                self._dbusservice['/Ac/Energy/Reverse'] = reverse_energy
            else:
                # Assume single-phase meter if three-phase keys are not present
                self._dbusservice['/Ac/Power'] = meter_data['active_power_w']
                self._dbusservice['/Ac/L1/Voltage'] = meter_data['active_voltage_l1_v']
                self._dbusservice['/Ac/L1/Current'] = meter_data['active_current_l1_a']
                self._dbusservice['/Ac/L1/Power'] = meter_data['active_power_l1_w']
                forward_energy = meter_data['total_power_import_kwh'] / 1000
                reverse_energy = meter_data['total_power_export_kwh'] / 1000
                self._dbusservice['/Ac/Energy/Forward'] = forward_energy
                self._dbusservice['/Ac/Energy/Reverse'] = reverse_energy
                self._dbusservice['/Ac/L1/Energy/Forward'] = forward_energy
                self._dbusservice['/Ac/L1/Energy/Reverse'] = reverse_energy
            self._lastUpdate = time.time()
        except Exception as e:
            logging.error(f"Error updating DBus service: {e}")
        return True

    def _handlechangedvalue(self, path, value):
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
        logging.debug(f"someone else updated {path} to {value}")
        return True


def getLogLevel():
    """
    Get the configured log level from config.ini.
    
    Returns:
        int: The Python logging level (e.g., logging.INFO)
    """
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.ini"))
    logLevelString = config['DEFAULT'].get('LogLevel')
    level = logging.getLevelName(logLevelString) if logLevelString else logging.INFO
    return level


def main():
    """
    Main entry point for the application.
    
    Initializes logging, sets up the DBus service, and starts the main event loop.
    This function will run indefinitely until interrupted.
    """
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=getLogLevel(),
                        handlers=[
                            logging.FileHandler(os.path.join(os.path.dirname(os.path.realpath(__file__)), "current.log")),
                            logging.StreamHandler()
                        ])

    try:
        logging.info("Start")

        from dbus.mainloop.glib import DBusGMainLoop
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        _kwh = lambda p, v: f"{v:.2f} kWh"
        _a = lambda p, v: f"{v:.1f} A"
        _w = lambda p, v: f"{v:.1f} W"
        _v = lambda p, v: f"{v:.1f} V"

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

        logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as e:
        logging.critical(f"Error in main: {e}")


if __name__ == "__main__":
    main()
