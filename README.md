# LightOn — 书房台灯 Controller

A minimal macOS app with **ON** and **OFF** buttons to control a Xiaomi smart light from your Desktop, with built-in idle detection to auto-off the light and monitor after an hour of inactivity.

![App Icon](icon.svg)

[
    <img src="icon.svg" width=30% title="App Icon" alt="App Icon"/>
](
icon.svg
)


## ⚠️ Prerequisite

> **This app is just a GUI wrapper around the `uvx` command.**
> You must ensure the following commands run successfully in your terminal *before* using the app:

```bash
uvx mijiaAPI set --dev_name "书房台灯" --prop_name "on" --value True
uvx mijiaAPI set --dev_name "书房台灯" --prop_name "on" --value False
```

If either command fails in the terminal, the app's buttons will also fail. Common issues to check:

- `uvx` is installed (`pip install uv` or see [uv docs](https://docs.astral.sh/uv/))
- [`mijiaAPI`](https://github.com/Do1e/mijia-api) package is accessible via `uvx`
- Your Xiaomi account credentials are configured for `mijiaAPI`
- The device name `书房台灯` matches exactly what is registered in your Mi Home account. You may change it in the app's Python code if needed.

## Requirements

- macOS
- Python 3 with **PyQt6** installed (`pip install PyQt6`)
- `uvx` available at `/opt/homebrew/bin/uvx` (Homebrew)

## Usage

Double-click **`LightControl.app`** to open the control panel, then click **ON** or **OFF**.

If macOS blocks the app on first launch (Gatekeeper), right-click → **Open** → **Open**.

### Auto-off (Idle Detection)

The app has an **"Auto-off after 1 hr idle"** checkbox at the bottom of the window. When checked:

- The app polls macOS IOKit every 60 seconds for mouse/keyboard activity.
- If no activity is detected for **1 hour**, it automatically turns off the light and sleeps the monitor.
- Clicking ON or OFF resets the idle counter.
- Unchecking the box stops the monitor at any time.

## Standalone Idle Monitor Scripts

The same idle detection logic is also available as two standalone scripts that can be run independently from the terminal — useful if you want the auto-off behaviour without opening the GUI app.

### `idle_monitor.py` (Python)

```bash
python3 idle_monitor.py
```

### `idle_monitor.fish` (Fish shell)

```bash
fish idle_monitor.fish
```

Both scripts:
- Check for activity every 30 seconds (vs. 60 seconds in the app)
- Turn off the light via `uvx mijiaAPI ...` after 1 hour of inactivity
- Sleep the monitor via `pmset displaysleepnow`
- Print timestamped status to the terminal
- Exit cleanly on Ctrl+C **without** triggering any actions

To run in the background and log output:
```bash
nohup python3 idle_monitor.py > ~/.idle_monitor.log 2>&1 &
```

## Project Structure

```
LightOn/
├── icon.svg
├── idle_monitor.py        # Standalone idle monitor (Python)
├── idle_monitor.fish      # Standalone idle monitor (Fish shell)
├── README.md
└── LightControl.app/
    └── Contents/
        ├── Info.plist
        ├── MacOS/
        │   └── LightControl        # Shell launcher (sets PATH, calls Python)
        └── Resources/
            ├── AppIcon.icns        # Generated from icon.svg
            └── light_control.py   # PyQt6 GUI with built-in idle monitor
```

## How It Works

1. The `.app` bundle's shell launcher explicitly adds `/opt/homebrew/bin` to `PATH` (Finder strips it).
2. The Python/PyQt6 script renders a small window with two buttons and an idle-monitor checkbox.
3. Each button click runs the corresponding `uvx mijiaAPI ...` command in a background thread so the UI stays responsive.
4. When the idle checkbox is enabled, a background thread polls macOS `IOHIDSystem` for the `HIDIdleTime` value and triggers auto-off once the threshold is reached.
5. A status label shows `✓ Light turned ON/OFF` on success or `✗ Command failed` on error.

