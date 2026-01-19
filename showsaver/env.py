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
# User info vars
#

URL = os.getenv("SHOW_URL", "")

#
# Configuration
#

DO_CLEANUP = os.getenv("AUTO_CLEANUP_TMP", "true")
