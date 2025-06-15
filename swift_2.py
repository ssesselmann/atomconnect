"""
swift_2_qtcharts.py  –  Qt-Charts version with 300-s moving window
------------------------------------------------------------------
PySide6 >= 6.4 required (Qt Charts ships with PySide6).
"""

import json, time
import swift_shared 

from swift_shared import logging
from pathlib import Path
from PySide6.QtCore    import Qt, QTimer, QPointF
from PySide6.QtGui     import QColor, QPainter, QFont, QPixmap, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame
from PySide6.QtCharts  import QChart, QChartView, QLineSeries, QValueAxis

DATA_DIR    = Path(swift_shared.DATA_DIR)
LATEST_PATH = DATA_DIR / "latest_data.json"

# ------------------------------------------------------------------- #
class DisplayWindow(QWidget):
    def __init__(self, on_close=None) -> None:
        super().__init__()
        self.on_close_callback = on_close
        self.setWindowTitle("Atom Radiation Monitor — Qt Charts")
        self.resize(960, 600)

        # --- strip-chart parameters ---------------------------------
        self.t_seconds  = 0           # current sample time (s)
        self.window_sec = 300         # width of x-axis (5 min)
        self.window_pts = self.window_sec // 2   # timer = 2 s → 150 pts
        self.y_buf: list[float] = []  # ring-buffer of CPS values
        self.counts_buf: list[int] = []
        self.last_total_counts = 0


        # ---------- Qt Charts setup ---------------------------------
        vbox  = QVBoxLayout(self)

        # ——— ADD THIS HEADING ———
        heading = QLabel(f"AtomConnect - Bluetooth Radiation Monitor v{swift_shared.version}")
        heading.setStyleSheet("""
            background-color: rgb(0, 102, 209);
            margin-left: 5px;
            margin-right: 5px;
            padding: 5px;
            color: white;
        """)
        font    = QFont()
        font.setPointSize(20)
        font.setBold(True)
        heading.setFont(font)
        heading.setAlignment(Qt.AlignCenter)
        vbox.addWidget(heading)

        # ---------- layouts -----------------------------------------
        
        grid  = QGridLayout()
        vbox.addLayout(grid, 0)

        self.series = QLineSeries()
        self.series.setColor(QColor("red"))
        self.series.setPointsVisible(False)

        chart = QChart()
        chart.addSeries(self.series)

        # axes
        self.x_axis = QValueAxis()
        self.x_axis.setTitleText("Time (s)")
        self.x_axis.setRange(0, self.window_sec)      # fixed span

        self.y_axis = QValueAxis()
        self.y_axis.setTitleText("CPS")
        #self.y_axis.setRange(0, 10)

        chart.addAxis(self.x_axis, Qt.AlignBottom)
        chart.addAxis(self.y_axis, Qt.AlignLeft)
        self.series.attachAxis(self.x_axis)
        self.series.attachAxis(self.y_axis)
        chart.legend().hide()

        self.chart_view = QChartView(chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        vbox.addWidget(self.chart_view, 1)            # stretch = 1

        # ---------- numeric grid ------------------------------------
        fields = [
            ("📈 CPM", "cpm"), ("🎯 CPS", "cps"), ("☢️ Dose (mSv)", "dose"),
            ("🔄 Dose Rate (µSv/h)", "rate"), ("🔋 Battery (%)", "battery"),
            ("🌡️ Temp (°C)", "temp"), ("⏱️ Timestamp", "time"),
            ("🧮 Counts", "counts")
        ]
        self.labels = {}
        for i, (title, key) in enumerate(fields):
            r, c = divmod(i, 4)
            ttl = QLabel(title, alignment=Qt.AlignCenter)
            ttl.setStyleSheet("font-weight:bold;")
            val = QLabel("--", alignment=Qt.AlignCenter)
            val.setFrameShape(QFrame.Box)
            val.setStyleSheet("font-size:18px; background:#eef; padding:4px;")
            grid.addWidget(ttl, r*2,     c)
            grid.addWidget(val, r*2 + 1, c)
            self.labels[key] = val

            # ——— ADD THIS FOOTER ———
        footer = QLabel(
            "Compatible dosimeters, spectrometers and neutron detectors available from,\n"
            "GammaSpectacular.com\n"
            "Developed by: Steven Sesselmann (2025)\n"
            "https://github.com/ssesselmann/atomconnect/releases"
        )
        footer.setAlignment(Qt.AlignCenter)
        footer.setWordWrap(True)
        vbox.addWidget(footer)
    
        # ---------- timer -------------------------------------------
        timer = QTimer(self)
        timer.timeout.connect(self.update_data)
        timer.start(2_000)            # every 2 s

    # ----------------------------------------------------------------
    def update_data(self) -> None:
        # -------- read JSON ----------------------------------------
        try:
            data = json.loads(LATEST_PATH.read_text())
        except Exception as e:
            logging.info(f"[UI] JSON read error:{e}")
            return
        if not data:
            return

        # Get total counts since start
        total_counts = int(data.get("counts", 0) or 0)

        # Calculate the number of counts in the last 2-second interval
        delta_counts = total_counts - self.last_total_counts
        self.last_total_counts = total_counts  # update for next time

        # Append delta to buffer
        self.counts_buf.append(delta_counts)
        if len(self.counts_buf) > 30:  # last 60 seconds at 2s interval
            self.counts_buf.pop(0)

        # Compute true rolling CPM
        data["cpm"] = sum(self.counts_buf)

        # Update other fields
        data["status"] = "Live"
        data["time"]   = time.strftime("%H:%M:%S")
        cps = float(data.get("cps", 0) or 0)

        # -------- numeric grid ------------------------------------
        for key, lbl in self.labels.items():
            val = data.get(key, "--")
            try:
                if key in {"dose", "rate"}:
                    val = f"{float(val):.3f}"
                elif key in {"cps", "cpm"}:
                    val = f"{float(val):.1f}"
            except (ValueError, TypeError):
                pass
            lbl.setText(str(val))

        # -------- update trace ------------------------------------
        # 1) append new CPS value
        self.y_buf.append(cps)
        if len(self.y_buf) > self.window_pts:
            self.y_buf.pop(0)

        # 2) build matching X values (fixed 300-s width)
        right  = self.t_seconds
        left   = max(0, right - self.window_sec)
        xs = list(range(right - 2*(len(self.y_buf)-1), right+1, 2))
        ys = self.y_buf

        # after you’ve rebuilt the series …
        y_max = max(ys) if ys else 1        # ys = current CPS values in window
        self.y_axis.setRange(0, y_max * 1.1)  # 10 % head-room

        # 3) redraw series (≤150 points → trivial)
        self.series.clear()
        for x, y in zip(xs, ys):
            self.series.append(QPointF(x, y))

        # keep a fixed 300-s span; start with 0-300, then slide
        if self.t_seconds < self.window_sec:
            left, right = 0, self.window_sec
        else:
            left, right = self.t_seconds - self.window_sec, self.t_seconds
        self.x_axis.setRange(left, right)


        self.t_seconds += 2           # next sample time

    def closeEvent(self, event):
        if self.on_close_callback:
            self.on_close_callback()
        event.accept()

# ------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    win = DisplayWindow()
    win.show()
    sys.exit(app.exec())
