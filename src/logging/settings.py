"""Logging configuration values: level and output destination.

This holds the *value* of the dial; ``src/logging/setup.py`` reads
these and applies them.
"""

import logging

LEVEL = logging.INFO
LOG_DIR = "logs"        # top-level, git-ignored
LOG_FILE = "algo.log"
