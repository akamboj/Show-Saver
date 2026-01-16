import os
from pathlib import Path

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
USERNAME = os.getenv("SITE_USERNAME", "")
PASSWORD = os.getenv("SITE_PASSWORD", "")
