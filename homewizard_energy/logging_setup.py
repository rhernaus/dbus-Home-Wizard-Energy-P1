"""
Logging setup for Home Wizard Energy P1 integration.
"""

import logging
import os


def setup_logging(log_level: int, log_file_path: str = None) -> None:
    """
    Set up application logging.

    Args:
        log_level: The logging level to use
        log_file_path: Path to the log file (if None, only console logging is used)
    """
    # Create handlers list
    handlers = [logging.StreamHandler()]

    # Add file handler if a path is provided
    if log_file_path:
        if not os.path.exists(os.path.dirname(log_file_path)):
            os.makedirs(os.path.dirname(log_file_path))
        handlers.append(logging.FileHandler(log_file_path))

    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )

    # Set up individual loggers
    loggers = {
        'p1meter': logging.getLogger('p1meter'),
        'p1meter.config': logging.getLogger('p1meter.config'),
        'p1meter.client': logging.getLogger('p1meter.client'),
        'p1meter.dbus': logging.getLogger('p1meter.dbus'),
    }

    # Configure each logger
    for name, logger in loggers.items():
        logger.setLevel(log_level)

    logging.info(f"Logging initialized at level: {logging.getLevelName(log_level)}")