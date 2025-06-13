# swift_shared.py

import os
import csv
import datetime
import platform
import logging
from pathlib import Path

# Shared state
version                 = "2.0.1"
is_connected            = False
connection_status       = "idle"   # default at program start
latest_data             = {"data": {}, "timestamps": [], "cps_history": []}
is_recording            = False    # are we capturing rows right now?
csv_rows: list[str]     = []       # each element is already a CSV-formatted line
stop_request            = False    # set True to break BLE loop
shutdown_request        = False    # set True to kill the whole app
selected_device_address = ""
selected_device_name    = ""
scan_done               = False


## Application identity
APP_NAME    = "AtomConnect"
APP_AUTHOR  = "BeeResearch"

# ===========================
# Log directory (OS-specific)
# ===========================

if platform.system() == "Darwin":
    LOG_DIR = Path.home() / "Library/Logs" / APP_NAME

elif platform.system() == "Windows":
    LOG_DIR = Path(os.getenv("APPDATA")) / APP_NAME / "logs"

else:
    LOG_DIR = Path.home() / f".{APP_NAME.lower()}" / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# ===========================
# Log file: last-run.log
# ===========================

log_path = LOG_DIR / "last-run.log"

logging.basicConfig(
    filename=log_path,
    filemode="w",  # overwrite each run
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info("=== AtomConnect started ===")

# ===========================
# Data Directory
# ===========================

if platform.system() == "Darwin":
    DATA_DIR = Path.home() / "Library/Application Support" / APP_NAME
elif platform.system() == "Windows":
    DATA_DIR = Path(os.getenv("APPDATA")) / APP_NAME
else:
    DATA_DIR = Path.home() / f".{APP_NAME.lower()}"

DATA_DIR.mkdir(parents=True, exist_ok=True)



