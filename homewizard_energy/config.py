"""
Configuration management for the Home Wizard Energy P1 integration.
"""

import logging
import os
from typing import Any, Dict, Optional

import yaml

# Constants
DEFAULT_SIGN_OF_LIFE_INTERVAL_MIN = 5
ALLOWED_ROLES = ['pvinverter', 'grid']
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "config.yaml")


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

    def _load_config(self) -> Dict[str, Any]:
        """
        Load and parse the configuration file.

        Returns:
            Dict: Parsed configuration object
        """
        config = {
            'default': {},
            'onPremise': {}
        }

        if not os.path.exists(self.config_path):
            self.logger.warning(f"Configuration file not found at {self.config_path}, using defaults")
            return config

        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)
                if config is None:
                    self.logger.warning(f"Empty configuration file at {self.config_path}, using defaults")
                    return {'default': {}, 'onPremise': {}}
                return config
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML configuration file: {e}")
            return config
        except Exception as e:
            self.logger.error(f"Error loading configuration file: {e}")
            return config

    def _ensure_basic_config(self) -> None:
        """
        Ensure basic configuration sections exist (for development mode).
        """
        if 'default' not in self.config:
            self.config['default'] = {}
            self.logger.warning("Created default section for development mode")

        if 'onPremise' not in self.config:
            self.config['onPremise'] = {}
            self.logger.warning("Created onPremise section for development mode")

        # Set some reasonable defaults for development mode
        if 'deviceInstance' not in self.config['default']:
            self.config['default']['deviceInstance'] = 42
            self.logger.warning("Using default deviceInstance=42 for development mode")

        if 'role' not in self.config['default']:
            self.config['default']['role'] = 'grid'
            self.logger.warning("Using default role=grid for development mode")

        if 'host' not in self.config['onPremise']:
            self.config['onPremise']['host'] = '127.0.0.1'
            self.logger.warning("Using default host=127.0.0.1 for development mode")

        if 'accessType' not in self.config['default']:
            self.config['default']['accessType'] = 'OnPremise'
            self.logger.warning("Using default accessType=OnPremise for development mode")

    def _validate_config(self) -> None:
        """
        Validate configuration settings.

        Raises:
            ValueError: If configuration is invalid
        """
        required_keys = {
            'default': ['accessType', 'deviceInstance', 'role'],
            'onPremise': ['host']
        }

        for section, keys in required_keys.items():
            if section not in self.config:
                raise ValueError(f"Missing section '{section}' in config")
            for key in keys:
                if key not in self.config[section]:
                    raise ValueError(f"Missing key '{key}' in section '{section}'")

        # Additional validation
        if self.config['default']['role'] not in ALLOWED_ROLES:
            raise ValueError(f"Invalid role: {self.config['default']['role']}")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            section: Configuration section name
            key: Configuration key
            default: Default value if key is not found

        Returns:
            Any: Configuration value or default
        """
        try:
            return self.config[section][key]
        except (KeyError, TypeError):
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
        return self.get_int('default', 'deviceInstance', 40)

    def get_custom_name(self) -> str:
        """Get the custom device name."""
        return self.get('default', 'customName', 'Home Wizard Energy P1')

    def get_role(self) -> str:
        """Get the configured role."""
        role = self.get('default', 'role')
        return role if role in ALLOWED_ROLES else 'grid'

    def get_position(self) -> int:
        """Get the configured position value."""
        return self.get_int('default', 'position', 0)

    def get_sign_of_life_interval(self) -> int:
        """Get the sign-of-life interval in minutes."""
        return self.get_int('default', 'signOfLifeLog', DEFAULT_SIGN_OF_LIFE_INTERVAL_MIN)

    def get_log_level(self) -> int:
        """Get the configured log level."""
        level_name = self.get('default', 'logLevel', 'INFO')
        return logging.getLevelName(level_name)

    def get_host(self) -> str:
        """Get the meter host/IP address."""
        return self.get('onPremise', 'host', '127.0.0.1')

    def get_api_url(self) -> str:
        """Get the full API URL for the meter."""
        access_type = self.get('default', 'accessType', 'OnPremise')
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