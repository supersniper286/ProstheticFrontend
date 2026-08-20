# Modern Prosthetic IoB Frontend Application

## Overview

This repository contains a **Tkinter** based desktop application that provides a real‑time dashboard for monitoring and controlling a prosthetic device via BLE (or simulated mock data). The app visualises vital signs (heart rate, blood oxygen, temperature) and EMG signals, supports gesture threshold configuration, and logs events for clinical analysis.

Key features:
- Live BLE data acquisition using **bleak** (or mock data generator).
- Interactive UI built with **Tkinter** and **ttk**.
- Real‑time EMG waveform plotted with **matplotlib**.
- Gesture‑threshold management (add, edit, remove).
- Historical data view and CSV export.
- Device registration and removal UI.
- Configurable color palette for a modern look.

## Project Structure

```
README.md                # This documentation
modern_prosthetic_app.py  # Main application source (the code you provided)
requirements.txt          # Python dependencies
```

## Requirements

- Python 3.9 or newer
- Windows OS (tested on Windows 10/11)
- Bluetooth Low Energy adapter (if using real devices)

## Installation

1. **Clone the repository** (or copy the source file into a folder, e.g., `d:\fyp`).
2. Open a command prompt and navigate to the project directory:
   ```
   cd d:\fyp
   ```
3. (Optional) Create a virtual environment to isolate dependencies:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install required packages:
   ```
   pip install -r requirements.txt
   ```
   The `requirements.txt` should contain:
   ```
   bleak
   matplotlib
   ```
5. Run the application:
   ```
   python modern_prosthetic_app.py
   ```

## Getting Started Guide

1. **Launch the app** – The main window appears with a sidebar listing registered devices.
2. **Register a device**
   - Click **"＋  Pair / Register Device"**.
   - Enter a device serial (e.g., `ESP32-PROSTHETIC-01`).
   - For testing without hardware, leave **"Run in Offline Simulation Mode"** checked. This creates a mock device that streams synthetic telemetry.
3. **Select a device** from the list to make it active. The header updates with the active serial and mode (Mock or BLE).
4. **Observe live vitals** – Heart rate, SpO₂, and temperature cards update in real time.
5. **Monitor EMG waveform** – The chart below shows the live EMG signal. Threshold lines are drawn for each configured gesture.
6. **Configure gesture thresholds**
   - **Add**: Click **"＋ Add Threshold"**, give a name and a value (0‑4095 mV).
   - **Edit**: Use the same dialog (currently re‑uses the add UI).
   - **Remove**: Click **"🗑️ Remove Threshold"**, select a threshold, and confirm.
7. **Gesture detection** – When the EMG signal crosses a threshold, the banner changes to show the active hand state.
8. **Historical view**
   - Click **"Analytics ↗"** on any vital‑card to open a window displaying the recent data series and a log of timestamps.
   - Use **"Export Log to CSV"** to save the data for further analysis.
9. **System event log** – Bottom panel records informational messages and critical alerts (e.g., out‑of‑bounds heart rate).
10. **Remove a device** – Use **"✕  Remove Active Device"** to delete the selected device from the registry.

## Customization

- **Color palette** – Modify the `COLOR_*` constants at the top of `modern_prosthetic_app.py` to change the UI theme.
- **Critical thresholds** – Adjust `CRITICAL_HR_HIGH`, `CRITICAL_HR_LOW`, and `CRITICAL_OX_LOW` to suit clinical requirements.
- **BLE characteristic UUID** – Update `CHARACTERISTIC_UUID` if your prosthetic device uses a different UUID.

## Troubleshooting

- **BLE connection fails** – Ensure Bluetooth is enabled and the device advertises the expected name. Verify the UUID matches.
- **Mock data not appearing** – Confirm the device is registered with *Simulation Mode* enabled.
- **Missing dependencies** – Run `pip install -r requirements.txt` again inside the activated virtual environment.

## License

This project is provided for educational purposes and may be adapted for research or commercial use with appropriate attribution and express consent from the project author(s)

---

*End of README*
