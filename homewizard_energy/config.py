"""
Configuration management for the Home Wizard Energy P1 integration.
"""

import configparser
import logging
import os
from typing import Any, Dict, Optional

# Constants
DEFAULT_SIGN_OF_LIFE_INTERVAL_MIN = 5
ALLOWED_ROLES = ['pvinverter', 'grid']
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "config.ini")


class ConfigManager:
    """
    Configuration manager for the Home Wizard Energy P1 integration.

    This class handles loading, validating, and accessing configuration settings.
    """

    def __init__(self, config_path: str = CONFIG_FILE_PATH, dev_mode: bool = False):
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file
            dev_mode: Whether to run in development mode (relaxed validation)
        """
        self.logger = logging.getLogger("p1meter.config")
        self.config_path = config_path
        self.dev_mode = dev_mode
        self.config = self._load_config()

        if not dev_mode:
            self._validate_config()
        else:
            # In dev mode, ensure at least basic sections exist
            self._ensure_basic_config()

    def _load_config(self) -> configparser.ConfigParser:
        """
        Load and parse the configuration file.

        Returns:
            ConfigParser: Parsed configuration object
        """
        config = configparser.ConfigParser()
        if not os.path.exists(self.config_path):
            self.logger.warning(f"Configuration file not found at {self.config_path}, using defaults")
            # Create default sections to avoid KeyError
            config['DEFAULT'] = {}
            config['ONPREMISE'] = {}
            return config

        config.read(self.config_path)
        return config

    def _ensure_basic_config(self) -> None:
        """
        Ensure basic configuration sections exist (for development mode).
        """
        if 'DEFAULT' not in self.config:
            self.config['DEFAULT'] = {}
            self.logger.warning("Created DEFAULT section for development mode")

        if 'ONPREMISE' not in self.config:
            self.config['ONPREMISE'] = {}
            self.logger.warning("Created ONPREMISE section for development mode")

        # Set some reasonable defaults for development mode
        if 'DeviceInstance' not in self.config['DEFAULT']:
            self.config['DEFAULT']['DeviceInstance'] = '42'
            self.logger.warning("Using default DeviceInstance=42 for development mode")

        if 'Role' not in self.config['DEFAULT']:
            self.config['DEFAULT']['Role'] = 'grid'
            self.logger.warning("Using default Role=grid for development mode")

        if 'Host' not in self.config['ONPREMISE']:
            self.config['ONPREMISE']['Host'] = '127.0.0.1'
            self.logger.warning("Using default Host=127.0.0.1 for development mode")

        if 'AccessType' not in self.config['DEFAULT']:
            self.config['DEFAULT']['AccessType'] = 'OnPremise'
            self.logger.warning("Using default AccessType=OnPremise for development mode")

    def _validate_config(self) -> None:
        """
        Validate configuration settings.

        Raises:
            ValueError: If configuration is invalid
        """
        required_keys = {
            'DEFAULT': ['AccessType', 'DeviceInstance', 'Role'],
            'ONPREMISE': ['Host']
        }

        for section, keys in required_keys.items():
            if section not in self.config:
                raise ValueError(f"Missing section '{section}' in config")
            for key in keys:
                if key not in self.config[section]:
                    raise ValueError(f"Missing key '{key}' in section '{section}'")

        # Additional validation
        if self.config['DEFAULT']['Role'] not in ALLOWED_ROLES:
            raise ValueError(f"Invalid Role: {self.config['DEFAULT']['Role']}")

    def get(self, section: str, key: str, default: Any = None) -> str:
        """
        Get a configuration value.

        Args:
            section: Configuration section name
            key: Configuration key
            default: Default value if key is not found

        Returns:
            str: Configuration value or default
        """
        try:
            return self.config[section][key]
        except (KeyError, ValueError):
            return default

    def get_int(self, section: str, key: str, default: Optional[int] = None) -> Optional[int]:
        """
        Get a configuration value as an integer.

        Args:
            section: Configuration section name
            key: Configuration key
            default: Default value if key is not found or not convertible to int

        Returns:
            int: Configuration value as int, or default
        """
        value = self.get(section, key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Cannot convert {section}.{key}='{value}' to int, using default {default}")
            return default

    def get_device_instance(self) -> int:
        """Get the device instance number."""
        return self.get_int('DEFAULT', 'DeviceInstance', 40)

    def get_custom_name(self) -> str:
        """Get the custom device name."""
        return self.get('DEFAULT', 'CustomName', 'Home Wizard Energy P1')

    def get_role(self) -> str:
        """Get the configured role."""
        role = self.get('DEFAULT', 'Role')
        return role if role in ALLOWED_ROLES else 'grid'

    def get_position(self) -> int:
        """Get the configured position value."""
        return self.get_int('DEFAULT', 'Position', 0)

    def get_sign_of_life_interval(self) -> int:
        """Get the sign-of-life interval in minutes."""
        return self.get_int('DEFAULT', 'SignOfLifeLog', DEFAULT_SIGN_OF_LIFE_INTERVAL_MIN)

    def get_log_level(self) -> int:
        """Get the configured log level."""
        level_name = self.get('DEFAULT', 'LogLevel', 'INFO')
        return logging.getLevelName(level_name)

    def get_host(self) -> str:
        """Get the meter host/IP address."""
        return self.get('ONPREMISE', 'Host', '127.0.0.1')

    def get_api_url(self) -> str:
        """Get the full API URL for the meter."""
        access_type = self.get('DEFAULT', 'AccessType', 'OnPremise')
        if access_type == 'OnPremise':
            return f"http://{self.get_host()}/api/v1/data"
        else:
            raise ValueError(f"AccessType {access_type} is not supported")


def get_config(config_path: str = CONFIG_FILE_PATH, dev_mode: bool = False) -> ConfigManager:
    """
    Factory function to get a ConfigManager instance.

    Args:
        config_path: Path to the configuration file
        dev_mode: Whether to run in development mode (relaxed validation)

    Returns:
        ConfigManager: Configuration manager instance
    """
    return ConfigManager(config_path, dev_mode)