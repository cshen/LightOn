import os
import re
import sys
import subprocess
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

ENV = os.environ.copy()
ENV["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + ENV.get("PATH", "")

IDLE_CHECK_INTERVAL_MS = 60_000   # check every 60 seconds
IDLE_THRESHOLD_S       = 3600     # trigger after 1 hour of inactivity

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "device.config")


def get_device_name() -> str:
    default = "书房台灯"
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
    except Exception:
        pass
    return default


DEVICE_NAME = get_device_name()


def get_idle_seconds() -> int:
    """Return seconds since last mouse/keyboard input via macOS IOKit HIDIdleTime."""
    try:
        out = subprocess.check_output(
            ["ioreg", "-c", "IOHIDSystem"],
            stderr=subprocess.DEVNULL, text=True,
        )
        match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
        if match:
            return int(int(match.group(1)) / 1_000_000_000)
    except Exception:
        pass
    return 0


class CommandRunner(QThread):
    finished = pyqtSignal(bool)

    def __init__(self, args: list[str]):
        super().__init__()
        self.args = args

    def run(self):
        try:
            subprocess.run(self.args, env=ENV, check=True)
            self.finished.emit(True)
        except Exception:
            self.finished.emit(False)


class IdleMonitor(QThread):
    """
    Polls idle time every IDLE_CHECK_INTERVAL_MS milliseconds using a QTimer
    that lives on the main thread, but does the ioreg subprocess call here
    so the UI never blocks.
    """
    idle_tick   = pyqtSignal(int, int)   # (idle_seconds, remaining_seconds)
    triggered   = pyqtSignal()           # fired when idle threshold is reached

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active    = True
        self._last_activity = time.time()

    def reset(self):
        """Call when activity is detected externally (e.g. user clicks a button)."""
        self._last_activity = time.time()

    def run(self):
        while self._active:
            idle = get_idle_seconds()
            now  = time.time()
            if idle < 5:
                self._last_activity = now
            elapsed  = now - self._last_activity
            remaining = max(0, int(IDLE_THRESHOLD_S - elapsed))
            self.idle_tick.emit(idle, remaining)
            if elapsed >= IDLE_THRESHOLD_S:
                self.triggered.emit()
                return
            # sleep in small steps so stop() is responsive
            for _ in range(60):
                if not self._active:
                    return
                time.sleep(1)

    def stop(self):
        self._active = False


class LightControlWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(DEVICE_NAME)
        self.setFixedSize(300, 290)
        self._idle_monitor: IdleMonitor | None = None
        self._runners: list[CommandRunner] = []
        self.setup_ui()
        self.center_on_screen()

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        title = QLabel(f"{DEVICE_NAME} Desk Light")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("PingFang SC", 20, QFont.Weight.Bold))
        layout.addWidget(title)

        self.on_btn = QPushButton("ON")
        self.on_btn.setFixedHeight(52)
        self.on_btn.setFont(QFont("SF Pro Text", 16, QFont.Weight.Bold))
        self.on_btn.clicked.connect(self.turn_on)
        self.on_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFB800; color: white;
                border-radius: 10px; border: none;
            }
            QPushButton:hover   { background-color: #FFA000; }
            QPushButton:pressed { background-color: #FF8F00; }
            QPushButton:disabled { background-color: #E0E0E0; color: #aaa; }
        """)
        layout.addWidget(self.on_btn)

        self.off_btn = QPushButton("OFF")
        self.off_btn.setFixedHeight(52)
        self.off_btn.setFont(QFont("SF Pro Text", 16, QFont.Weight.Bold))
        self.off_btn.clicked.connect(self.turn_off)
        self.off_btn.setStyleSheet("""
            QPushButton {
                background-color: #5C5C5C; color: white;
                border-radius: 10px; border: none;
            }
            QPushButton:hover   { background-color: #484848; }
            QPushButton:pressed { background-color: #333333; }
            QPushButton:disabled { background-color: #E0E0E0; color: #aaa; }
        """)
        layout.addWidget(self.off_btn)

        self.status = QLabel("Ready")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFont(QFont("SF Pro Text", 12))
        self.status.setStyleSheet("color: #888888;")
        layout.addWidget(self.status)

        # ── Idle monitor checkbox ──────────────────────────────────────────
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #E0E0E0;")
        layout.addWidget(separator)

        self.idle_checkbox = QCheckBox("Auto-off after 1 hr idle")
        self.idle_checkbox.setFont(QFont("SF Pro Text", 12))
        self.idle_checkbox.setStyleSheet("color: #444444;")
        self.idle_checkbox.stateChanged.connect(self._on_idle_toggled)
        layout.addWidget(self.idle_checkbox)

        self.idle_status = QLabel("")
        self.idle_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.idle_status.setFont(QFont("SF Pro Text", 10))
        self.idle_status.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(self.idle_status)

    # ── Idle monitor ──────────────────────────────────────────────────────

    def _on_idle_toggled(self, state):
        if state == Qt.CheckState.Checked.value:
            self._start_idle_monitor()
        else:
            self._stop_idle_monitor()
            self.idle_status.setText("")

    def _start_idle_monitor(self):
        self._stop_idle_monitor()
        self._idle_monitor = IdleMonitor(self)
        self._idle_monitor.idle_tick.connect(self._on_idle_tick)
        self._idle_monitor.triggered.connect(self._on_idle_triggered)
        self._idle_monitor.start()
        self.idle_status.setText("Watching for idle…")
        self.idle_status.setStyleSheet("color: #888888;")

    def _stop_idle_monitor(self):
        if self._idle_monitor:
            self._idle_monitor.stop()
            self._idle_monitor.wait(2000)
            self._idle_monitor = None

    def _on_idle_tick(self, idle: int, remaining: int):
        mins = remaining // 60
        secs = remaining % 60
        self.idle_status.setText(f"Idle: {idle}s  ·  off in {mins}m {secs:02d}s")
        self.idle_status.setStyleSheet("color: #aaaaaa;")

    def _on_idle_triggered(self):
        self.idle_status.setText("Idle limit reached — shutting down…")
        self.idle_status.setStyleSheet("color: #FF9500;")
        self.idle_checkbox.setChecked(False)

        # Turn off light
        r1 = CommandRunner(["uvx", "mijiaAPI", "set",
                            "--dev_name", DEVICE_NAME,
                            "--prop_name", "on", "--value", "False"])
        r1.finished.connect(lambda ok: self.status.setText(
            "✓ Auto-off: light off" if ok else "✗ Auto-off: light command failed"
        ))
        self._runners.append(r1)
        r1.start()

        # Turn off monitor (slight delay so light command fires first)
        QTimer.singleShot(1500, self._sleep_monitor)

    def _sleep_monitor(self):
        r2 = CommandRunner(["pmset", "displaysleepnow"])
        self._runners.append(r2)
        r2.start()

    # ── Light buttons ────────────────────────────────────────────────────

    def _run(self, args: list[str], label: str):
        self.on_btn.setEnabled(False)
        self.off_btn.setEnabled(False)
        self.status.setText("Sending…")
        self.status.setStyleSheet("color: #888888;")
        if self._idle_monitor:
            self._idle_monitor.reset()

        runner = CommandRunner(args)
        runner.finished.connect(lambda ok: self._done(ok, label))
        self._runners.append(runner)
        runner.start()

    def _done(self, success: bool, label: str):
        self.on_btn.setEnabled(True)
        self.off_btn.setEnabled(True)
        if success:
            color = "#34C759" if label == "ON" else "#888888"
            self.status.setText(f"✓ Light turned {label}")
            self.status.setStyleSheet(f"color: {color};")
        else:
            self.status.setText("✗ Command failed")
            self.status.setStyleSheet("color: #FF3B30;")

    def turn_on(self):
        self._run(["uvx", "mijiaAPI", "set",
                   "--dev_name", DEVICE_NAME,
                   "--prop_name", "on", "--value", "True"], "ON")

    def turn_off(self):
        self._run(["uvx", "mijiaAPI", "set",
                   "--dev_name", DEVICE_NAME,
                   "--prop_name", "on", "--value", "False"], "OFF")

    def closeEvent(self, event):
        self._stop_idle_monitor()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(DEVICE_NAME)
    win = LightControlWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    sys.exit(app.exec())

