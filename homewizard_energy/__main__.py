"""
Main entry point for the Home Wizard Energy P1 integration.
"""

import argparse
import logging
import os
import signal
import sys
from typing import Any, Dict

# Add the parent directory to the path to allow importing from the package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Add the velib_python directory to the path for vedbus
velib_path = os.path.join(parent_dir, 'dbus-systemcalc-py', 'ext', 'velib_python')
if velib_path not in sys.path:
    sys.path.insert(1, velib_path)

# Try to import gi.repository.GLib
try:
    from gi.repository import GLib as gobject
except ImportError:
    try:
        import gobject
    except ImportError:
        sys.stderr.write("Error: gobject module not found. Please install PyGObject.\n")
        sys.exit(1)

# Check for dbus module
DBUS_AVAILABLE = False
try:
    # For DBus main loop
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    DBUS_AVAILABLE = True
except ImportError:
    pass

# Import package modules
from homewizard_energy.config import CONFIG_FILE_PATH, get_config
from homewizard_energy.logging_setup import setup_logging
from homewizard_energy.meter_client import HomeWizardP1Client

# Only import DBus service if dbus is available
if DBUS_AVAILABLE:
    from homewizard_energy.dbus_service import DbusHomeWizardP1Service


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Home Wizard Energy P1 meter integration for Victron Energy Venus OS'
    )
    parser.add_argument(
        '-c', '--config',
        default=CONFIG_FILE_PATH,
        help='Path to the configuration file'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '-d', '--dev',
        action='store_true',
        help='Development mode (doesn\'t require dbus)'
    )
    parser.add_argument(
        '-m', '--mock',
        action='store_true',
        help='Use mock data instead of connecting to a real meter'
    )
    return parser.parse_args()


def create_dbus_paths() -> Dict[str, Dict[str, Any]]:
    """
    Create the DBus paths configuration.

    Returns:
        Dict: Paths and their formatters
    """
    # Define formatters for different units
    _kwh = lambda p, v: f"{v:.2f} kWh"
    _a = lambda p, v: f"{v:.1f} A"
    _w = lambda p, v: f"{v:.1f} W"
    _v = lambda p, v: f"{v:.1f} V"

    return {
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
        '/Ac/L1/Energy/Forward': {'initial': 0, 'textformat': _kwh},
        '/Ac/L1/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
        '/Ac/L2/Energy/Forward': {'initial': 0, 'textformat': _kwh},
        '/Ac/L2/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
        '/Ac/L3/Energy/Forward': {'initial': 0, 'textformat': _kwh},
        '/Ac/L3/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
    }


def development_mode(config, logger, api_url, mock_mode=False):
    """
    Run in development mode without DBus integration.

    Args:
        config: Configuration manager
        logger: Logger instance
        api_url: API URL for the meter
        mock_mode: Whether to use mock data
    """
    logger.info("Starting in development mode (no DBus integration)")

    try:
        meter_client = HomeWizardP1Client(api_url, mock_mode=mock_mode)
        meter_data = meter_client.get_data()

        if meter_data:
            logger.info("Successfully retrieved meter data:")
            logger.info(f"Serial: {meter_client.get_meter_serial()}")
            logger.info(f"Three-phase meter: {meter_client.is_three_phase_meter(meter_data)}")
            logger.info(f"Power: {meter_data.get('active_power_w', 'N/A')} W")
            logger.info(f"Total import: {meter_data.get('total_power_import_kwh', 'N/A')} kWh")
            logger.info(f"Total export: {meter_data.get('total_power_export_kwh', 'N/A')} kWh")
            return 0
        else:
            logger.error("Failed to retrieve meter data")
            return 1
    except Exception as e:
        logger.error(f"Error in development mode: {e}", exc_info=True)
        return 1


def main():
    """Main entry point for the application."""
    # Parse command line arguments
    args = parse_args()

    try:
        # Initialize configuration
        config = get_config(args.config, dev_mode=args.dev)

        # Set up logging
        log_level = logging.DEBUG if args.verbose else config.get_log_level()
        log_file = os.path.join(os.path.dirname(args.config), "current.log")
        setup_logging(log_level, log_file)
        logger = logging.getLogger('p1meter')

        # Get API URL from configuration
        api_url = config.get_api_url()

        # Run in development mode if requested or if DBus is not available
        if args.dev or not DBUS_AVAILABLE:
            if not DBUS_AVAILABLE and not args.dev:
                logger.warning("DBus not available, falling back to development mode")
            return development_mode(config, logger, api_url, args.mock)

        logger.info("Starting Home Wizard Energy P1 DBus service")

        # Initialize DBus main loop
        DBusGMainLoop(set_as_default=True)
        mainloop = gobject.MainLoop()

        # Set up signal handling for graceful shutdown
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down")
            mainloop.quit()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Create API client
        meter_client = HomeWizardP1Client(api_url, mock_mode=args.mock)

        # Create DBus service
        dbus_paths = create_dbus_paths()
        dbus_service = DbusHomeWizardP1Service(
            meter_client=meter_client,
            config_manager=config,
            gobject_mainloop=gobject,
            paths=dbus_paths
        )

        logger.info('Connected to dbus, starting main loop')
        mainloop.run()
        return 0

    except Exception as e:
        logging.critical(f"Error in main: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())