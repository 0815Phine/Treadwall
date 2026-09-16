# Treadwall — control software

All software for running the rig. A session is launched and coordinated from the
central GUI ([`treadwallGUI.py`](treadwallGUI.py)); see
[Running a Session](../README.md#running-a-session) in the top-level README for the
operator's view. This file documents the code layout and how the pieces fit
together.

## Structure

```
code/
├── treadwallGUI.py     # central PyQt5 GUI: session setup, live camera preview,
│                       #   notes → RSpace, protocol-parameter panel, emergency stop
├── startsession.bat    # double-click launcher (points at the treadwall conda env)
├── src/                # utility + GUI-helper scripts
│   ├── videoacquisition.py     dual-camera capture + live H.264 encoding
│   ├── start_bpodsession.m     launches Bpod non-interactively, multi-session loop
│   ├── start_wavesurfer.m      launches / stops WaveSurfer, renames its .h5
│   ├── gui_*.m                 shared GUI↔protocol helpers (IPC dir, session init,
│   │                             param publish/read, estop timer, done signal)
│   ├── treadwall_config.m      MATLAB reader for the central JSON config
│   ├── create_triallist.m / create_zones.m / get_stimoutput.m  stimulus helpers
│   └── arduino/                on-board firmware — see arduino/README.md
├── protocols/          # the five Bpod experiment protocols
│   ├── treadwall_baseline/         treadwall_habituation_1/   treadwall_habituation_2/
│   └── treadwall_scrambled/        treadwall_predictable/
├── parameters/         # ALL tunable settings (see below)
└── dependencies/       # vendored submodules (Bpod_Gen2, Wavesurfer, IEECRSpace,
                        #   Bpod_RotaryEncoder_Firmware) — see top-level README
```

## Configuration

Everything tunable lives in
[`parameters/treadwall_config.json`](parameters/treadwall_config.json) and is read
by both sides of the rig — `treadwall_config.m` in MATLAB and `json.load(...)` in
Python. It holds machine paths, Bpod/WaveSurfer/camera settings, and GUI timing.
Edit this file (not the scripts) to retarget the rig to another machine.

Device-specific settings that don't belong in the JSON live alongside it:

| Path | What |
| :-- | :-- |
| [`parameters/bpod/`](parameters/bpod/) | Bpod protocol parameter `.m` files + a test trial list |
| [`parameters/camera/`](parameters/camera/) | Basler `.pfs` full-feature camera profiles |
| [`parameters/tics/`](parameters/tics/) | Pololu Tic stepper-controller register settings |
| [`parameters/wavesurfer/`](parameters/wavesurfer/) | WaveSurfer protocol (`treadwall.wsp`) |

The Arduino sketches are the one exception — they are compiled and flashed, so
their constants are fixed in the `#define`s at the top of each sketch. Those are
documented in [`src/arduino/README.md`](src/arduino/README.md).

## How a session runs

`startsession.bat` → `treadwallGUI.py`, which:
1. starts the camera subprocess ([`src/videoacquisition.py`](src/videoacquisition.py)),
2. launches Bpod via [`src/start_bpodsession.m`](src/start_bpodsession.m) (which
   stays alive between sessions, polling for the next one), and
3. drives WaveSurfer via [`src/start_wavesurfer.m`](src/start_wavesurfer.m).

The GUI and the MATLAB scripts coordinate through small files in the IPC directory
(`paths.ipc_dir` in the config) — session hand-off, live parameter edits, emergency
stop, and end-of-session signalling. The shared `src/gui_*.m` helpers implement the
protocol side of this, so all five protocols behave consistently.

<p align="center">
  <!-- TODO: add the same GUI screenshot referenced from the top-level README -->
  <img src="./docs/gui_screenshot.png" width="800">
</p>

## Requirements

Language and library versions are pinned centrally — see
[Software Dependencies](../README.md#software-dependencies) and
[Python environment](../README.md#python-environment) in the top-level README
(Python 3.11 via [`dependencies/environment.yml`](dependencies/environment.yml),
MATLAB R2024a, plus ffmpeg on `PATH`).
