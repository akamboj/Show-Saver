import os
from pathlib import Path

def string_to_bool(s):
    return s.lower() in ["true", "yes", "1", "y"]

#
# Directories
#

CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/config"))
SHOW_DIR = Path(os.getenv("SHOW_DIR", "/tvshows"))
TMP_DIR = Path(os.getenv("TMP_DIR", "/tmp"))

#
# Debug
#

DEBUG = string_to_bool(os.getenv("FLASK_DEBUG", "false"))
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

#
# User info vars
#

URL = os.getenv("SHOW_URL", "")

#
# Configuration
#

DO_CLEANUP = string_to_bool(os.getenv("AUTO_CLEANUP_TMP", "true"))
