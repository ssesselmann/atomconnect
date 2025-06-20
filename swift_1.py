
# swift_1.py — Connect and launch swift_2.py, uses saved device list by default
import threading
import asyncio
import subprocess
import json, re, csv
import subprocess, sys, os
import swift_connect
import swift_shared
import platform
import time
import swift_2

from PySide6.QtWidgets import (
    QApplication, 
    QWidget, 
    QVBoxLayout, 
    QPushButton,
    QListWidget, 
    QLabel, 
    QMessageBox, 
    QProgressBar, 
    QGridLayout,
    QSizePolicy,
    QMessageBox,
)
from datetime import datetime
from PySide6.QtGui import QPixmap, QFontDatabase, QFont
from PySide6.QtCore import QTimer, Qt
from swift_shared import latest_data
from pathlib import Path
from swift_2 import DisplayWindow
from swift_shared import logging


DEVICE_FILE = swift_shared.DATA_DIR / "device_map.json"

class ConnectionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.display_launched = False

        # Window setup
        self.setWindowTitle("Connect to Atom Device")
        self.setGeometry(300, 300, 450, 450)  
        self.setFixedWidth(420)

        # --- MAIN LAYOUT ---
        layout = QVBoxLayout(self)

        # 1) Status label
        self.status_label = QLabel("Select a device or scan for new ones.")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.status_label)

        # 2) Device list
        self.device_list = QListWidget()
        self.device_list.setFont(QFont("Courier New", 12, QFont.Bold))

        layout.addWidget(self.device_list)

        # 3) Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 30)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 4) Button grid (2×2)
        btn_grid = QGridLayout()
        # Scan
        self.scan_button = QPushButton("🔍 Scan fore devices")
        self.scan_button.setStyleSheet("background-color: white; font-weight: bold;")
        self.scan_button.clicked.connect(self.start_scan)
        btn_grid.addWidget(self.scan_button, 0, 0)
        # Connect
        self.connect_button = QPushButton("🔗 Connect")
        self.connect_button.setStyleSheet("background-color: green; color: white; font-weight: bold;")
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.connect_to_selected_device)
        btn_grid.addWidget(self.connect_button, 0, 1)
        # Download
        self.download_button = QPushButton("📥 Download CSV")
        self.download_button.setStyleSheet("background-color: white; font-weight: bold;")
        self.download_button.clicked.connect(self.download_csv)
        btn_grid.addWidget(self.download_button, 1, 0)
        # Disconnect
        self.disconnect_button = QPushButton("🔴 Disconnect")
        self.disconnect_button.setStyleSheet("background-color: grey; color: white; font-weight: bold;")
        self.disconnect_button.clicked.connect(self.disconnect_device)
        btn_grid.addWidget(self.disconnect_button, 1, 1)

        layout.addLayout(btn_grid)

        # 5) Logo banner
        if getattr(sys, 'frozen', False):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent

        logo_path  = base / "assets" / "logo.png"
        pixmap     = QPixmap(str(logo_path))
        logo_label = QLabel()
        logo_label.setPixmap(pixmap)
        logo_label.setScaledContents(True)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setMaximumHeight(160)
        layout.addWidget(logo_label)
        # --- Layout is already set on `self` by passing `self` into QVBoxLayout() ---

        # --- THE REST: timers, loading, signals ---
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(500)

        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress_bar)
        self.progress_seconds = 0

        self.load_saved_devices()
        self.device_list.itemSelectionChanged.connect(self.on_selection_changed)


    def save_found_devices(self):
        if not self.found_devices:
            return
        try:
            os.makedirs(os.path.dirname(DEVICE_FILE), exist_ok=True)
            with open(DEVICE_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    [{"name": n, "address": a, "sig": s} for (n, a, s) in self.found_devices],
                    f, indent=2
                )
        except Exception as e:
            logging.info(f"[swift_1] Failed to save device list: {e}")

    def load_saved_devices(self):
        self.device_list.clear()
        self.found_devices = []
        if os.path.exists(DEVICE_FILE):
            try:
                with open(DEVICE_FILE, "r", encoding="utf-8") as f:
                    devices = json.load(f)
                    for d in devices:
                        name = d.get("name", "Unknown")
                        addr = d.get("address", "")
                        rssi = d.get("sig", 0)
                        short = addr.replace(":", "")[-12:].upper()
                        self.device_list.addItem(f"{name:<20}  {short:<14}  {rssi:>4} dB")
                        self.found_devices.append((name, addr, rssi))
                    self.status_label.setText(f"Loaded {len(devices)} saved device(s).")
            except Exception as e:
                self.status_label.setText(f"⚠️ Failed to load saved devices: {e}")
        else:
            self.status_label.setText("No saved devices found. Click Scan to discover.")

    def start_scan(self):
        self.device_list.clear()
        self.found_devices = []
        swift_shared.scan_done = False
        swift_shared.connection_status = "🔍 Scanning..."
        self.status_label.setText("Scanning... (30 seconds)")

        self.progress_seconds = 0
        self.progress_bar.setValue(0)
        self.progress_timer.start(1000)

        thread = threading.Thread(target=self.run_scan_thread, daemon=True)
        thread.start()

    def run_scan_thread(self):
        try:
            result = asyncio.run(swift_connect.scan_for_devices(timeout=30))
            self.found_devices = result
            self.save_found_devices()
        except Exception as e:
            swift_shared.connection_status = f"⚠️ Scan error: {e}"
            self.found_devices = []
        finally:
            swift_shared.scan_done = True

    def update_progress_bar(self):
        self.progress_seconds += 1
        self.progress_bar.setValue(self.progress_seconds)
        if self.progress_seconds >= 30:
            self.progress_timer.stop()

    def update_status(self):
        self.status_label.setText(swift_shared.connection_status)

        # launch chart window once, when connection flag turns true
        if swift_shared.is_connected and not self.display_launched:
            self.display_launched = True
            self.launch_display_window()

        if swift_shared.scan_done and self.found_devices:
            self.device_list.clear()
            for name, addr, rssi in self.found_devices:
                short = addr.replace(":", "")[-12:].upper()
                self.device_list.addItem(f"{name} (...{short}) ({rssi} dB)")
            swift_shared.scan_done = False

    def on_selection_changed(self):
        idx = self.device_list.currentRow()
        if idx >= 0:
            name, addr, _ = self.found_devices[idx]
            swift_shared.selected_device_name = name
            swift_shared.selected_device_address = addr
            self.connect_button.setEnabled(True)

    def start_connection(self):
        threading.Thread(target=swift_connect.connect_to_device, daemon=True).start()

    def launch_display_window(self):
        if not hasattr(self, "_display_window"):
            from swift_2 import DisplayWindow
            self.display_window = DisplayWindow(on_close=self.on_display_closed)
            self.display_window.show()

    def on_display_closed(self):
        self.display_launched = False

    def connect_to_selected_device(self):
        self.status_label.setText("🔌 Connecting...")
        self.start_connection()
        QMessageBox.information(
            self,
            "Connection",
            f"Connecting to {swift_shared.selected_device_name}…"
        )

    def disconnect_device(self):
        swift_shared.stop_request     = True
        swift_shared.shutdown_request = True
        swift_shared.is_connected     = False
        swift_shared.connecting       = False
        swift_shared.scan_done        = False
        swift_shared.client           = None  # optional safety
        self.status_label.setText("🔴 Disconnected")
        QMessageBox.information(self, "Disconnected", "The device has been disconnected.")

    def download_csv(self):
        from datetime import datetime
        import csv
        import json
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox
        import swift_shared

        try:
            # 1) Locate the session log
            recording_file = swift_shared.SESSION_LOG

            if not recording_file.exists():
                raise FileNotFoundError(f"No session log found at {recording_file}")

            # 2) Read and parse JSONL (line-by-line)
            with open(recording_file, "r", encoding="utf-8") as f:
                data = [json.loads(line) for line in f if line.strip()]

            if not data:
                raise ValueError("No data to export.")

            # 3) Define CSV columns and corresponding JSON keys
            mapping = {
                "Timestamp"      : "time",
                "TotalCounts"    : "counts",
                "CPS"            : "cps",
                "Dose_mSv"       : "dose",
                "DoseRate_uSv_h" : "rate",
                "Battery_%"      : "battery",
                "Temp_C"         : "temp"
            }
            headers = list(mapping.keys())

            # 4) Output path
            out_fname = (
                Path.home() / "Downloads" /
                f"atom_data_{datetime.now():%Y%m%d_%H%M}.csv"
            )
            out_fname.parent.mkdir(parents=True, exist_ok=True)

            # 5) Write CSV
            with open(out_fname, "w", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()
                for row in data:
                    writer.writerow({
                        col: row.get(json_key, "")
                        for col, json_key in mapping.items()
                    })

            # 6) Notify user
            QMessageBox.information(
                self,
                "Download Complete",
                f"Saved to:\n{out_fname}"
            )

        except Exception as e:
            QMessageBox.warning(
                self,
                "Download Failed",
                f"Could not export data:\n{e}"
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ConnectionWindow()
    win.show()
    sys.exit(app.exec())
