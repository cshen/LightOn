#!/usr/bin/env python3
"""
idle_monitor.py — macOS idle detection script.

Checks every 30 or 60 seconds for mouse/keyboard activity via macOS IOKit.
If no activity is detected for 1 hour, turns off the desktop light
(via uvx mijiaAPI) and puts the monitor to sleep, then exits.

Press Ctrl+C to quit without triggering any actions.
"""

import os
import re
import signal
import subprocess
import sys
import time

CHECK_INTERVAL = 60       # seconds between each check
IDLE_THRESHOLD = 3600     # 1 hour in seconds

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

# Prepend Homebrew bin so uvx/pmset are found even outside a login shell
ENV = os.environ.copy()
ENV["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + ENV.get("PATH", "")


def ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def get_idle_time() -> int:
    """Return seconds since last mouse/keyboard activity via IOKit HIDIdleTime."""
    try:
        out = subprocess.check_output(
            ["ioreg", "-c", "IOHIDSystem"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
        if match:
            idle_ns = int(match.group(1))
            return int(idle_ns / 1_000_000_000)
    except Exception:
        pass
    return 0


def turn_off_light() -> bool:
    result = subprocess.run(
        ["uvx", "mijiaAPI", "set", "--dev_name", DEVICE_NAME, "--prop_name", "on", "--value", "False"],
        env=ENV,
    )
    return result.returncode == 0


def turn_off_monitor() -> bool:
    result = subprocess.run(["pmset", "displaysleepnow"], env=ENV)
    return result.returncode == 0


def cleanup_and_exit():
    print(f"\n[{ts()}] Activity timeout reached. Turning off light and monitor...")

    if turn_off_light():
        print(f"[{ts()}] ✓ Light turned off")
    else:
        print(f"[{ts()}] ✗ Failed to turn off light")

    if turn_off_monitor():
        print(f"[{ts()}] ✓ Monitor turned off")
    else:
        print(f"[{ts()}] ✗ Failed to turn off monitor")

    print(f"[{ts()}] Exiting idle detection script")
    sys.exit(0)


def handle_sigint(sig, frame):
    print(f"\n[{ts()}] Interrupted — exiting without triggering actions")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, handle_sigint)

    last_activity = time.time()
    print(
        f"[{ts()}] Starting idle detection "
        f"(check every {CHECK_INTERVAL}s, timeout after {IDLE_THRESHOLD}s)"
    )

    while True:
        idle_time = get_idle_time()
        now = time.time()
        time_since_last_activity = now - last_activity

        if idle_time < 5:
            last_activity = now
            print(f"[{ts()}] Activity detected (idle: {idle_time}s, counter reset)")
        else:
            if time_since_last_activity >= IDLE_THRESHOLD:
                cleanup_and_exit()
            else:
                remaining = int(IDLE_THRESHOLD - time_since_last_activity)
                print(
                    f"[{ts()}] No activity "
                    f"(idle: {idle_time}s, {remaining}s remaining before timeout)"
                )

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
