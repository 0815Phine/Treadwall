# Treadwall

<p align="center">
  <!-- TODO: setup overview image to be added -->
</p>

### Hardware Components
- [Treadmill-Main](hardware/treadmillmain)
- [Treadwall-Main](hardware/treadwallmain)
- [Wall Synchronizer](hardware/wallsynchronizer)
- [Wall Mover](hardware/wallmover)
- [Circuit Box](hardware/circuitbox)

### Wiring Overview
<p align="center">
  <img src="./hardware/connections_overview.png" width="800">
</p>

## Lasercutting
We used a Trotec Speedy Flex lasercutter with a 100W CO2 laser with the following settings:

| Parameter | Cutting Quality | Engraving Quality |
| :---: | :---: | :---: |
| Power | 70 % | 70 % |
| Speed | 0.2 % | 3.5 % |
| Laser Source | CO2 | CO2 |
| Frequency | 20'000 Hz | 1'000 Hz |
| Passes | 1 | 1 |
| Power Correction | 10 | 10 |
| z-Offset | -2 | 0 |
| Resolution | N.A. | 500 DPI |

Red lines -> cut; black lines -> engrave; blue lines -> not assigned

## 3D Printing

## Bpod System
Control of the system is done with the Bpod System. All used modules are controlled by a 'state machine' ([sanworks.io](https://sanworks.io/shop/viewproduct?productID=1036)).

Modules used for scrambled and predictable experiments:
| Module | Link | Functionality |
| :---: | :---: | :---: |
| Analog Output Module | [sanworks.io](https://sanworks.io/shop/viewproduct?productID=1038) | loaded with Waveplayer Firmware, can play certain analog signals, controls lateral movement of walls |
| Analog Input Module | [sanworks.io](https://sanworks.io/shop/viewproduct?productID=1037) | reads analog signals, used for zone transition in predictable paradigm |
| Rotary Encoder Module V2 | [sanworks.io](https://sanworks.io/shop/viewproduct?productID=1034) | connected directly to the rotary encoder, provides power and sends speed information to analog input module, loaded with modified firmware ([github.com](https://github.com/0815Phine/Bpod_RotaryEncoder_Firmware)) |

For further modules see [sanworks.io/products](https://sanworks.io/shop/products.php).

## Software Dependencies
External code is vendored as **git submodules** under [code/dependencies/](code/dependencies/).
Clone with `git clone --recurse-submodules`, or run `git submodule update --init --recursive`
after cloning.

| Submodule | Source | Notes |
| :--- | :--- | :--- |
| `Bpod_Gen2` | [LenaGschossmann/Bpod_Gen2](https://github.com/LenaGschossmann/Bpod_Gen2) @ `softcodes-udp-sync` | Bpod control framework (sanworks fork). The `softcodes-udp-sync` branch is required and is pinned in `.gitmodules`. |
| `Bpod_RotaryEncoder_Firmware` | [0815Phine/Bpod_RotaryEncoder_Firmware](https://github.com/0815Phine/Bpod_RotaryEncoder_Firmware) | Modified rotary-encoder module firmware (needed for the *predictable* experiments). |
| `Wavesurfer` | [JaneliaSciComp/Wavesurfer](https://github.com/JaneliaSciComp/Wavesurfer) | WaveSurfer app for synchronized data acquisition. |
| `IEECRSpace` | [IEECR-BeckGroup/IEECRSpace](https://github.com/IEECR-BeckGroup/IEECRSpace) | RSpace integration; `treadwallGUI.py` adds `IEECRSpace/src` to `sys.path` and imports `rspace`. |

**IEECRSpace must be set up once before the GUI's RSpace features work.** The submodule is a
self-contained app that installs itself on first launch. If you haven't done this yet, run its
first-time setup — on Windows double-click
[`code/dependencies/IEECRSpace/IEECRSpace_Launcher.bat`](code/dependencies/IEECRSpace/) (the first
launch downloads its own private Python + dependencies, so it needs an internet connection) — and
then paste your RSpace API key into the app's **Settings** tab. See the
[IEECRSpace README](code/dependencies/IEECRSpace/README.md) for the full instructions.

**Arduino libraries** are installed via the Arduino IDE **Library Manager** (the IDE resolves
libraries from its own sketchbook `libraries/` folder, not from this repo):
- `CapacitiveSensor` (PaulStoffregen) — Lickport sketches.
- `Tic` (Pololu) — Wall Mover / Wall Synchronizer sketches.
- `Servo`, `SoftwareSerial` — ship with the Arduino IDE.

### Python environment
The GUI and camera scripts run on a dedicated conda environment pinned in
[`code/dependencies/environment.yml`](code/dependencies/environment.yml). Create it once:

```
conda env create -f code/dependencies/environment.yml
```

This builds an env named `treadwall` (Python 3.11 + numpy, opencv-python, pypylon, PyQt5,
requests). The launcher ([code/startsession.bat](code/startsession.bat)) and the camera subprocess
already point at this env's interpreter, so **the `treadwall` env must exist for the app to run**.
(`rspace` is not listed here — it is imported from the `IEECRSpace` submodule source.)

**ffmpeg** is required for live video encoding and is **not** a conda package here — the camera
calls `ffmpeg` by name, so it must be on the system `PATH`. FFmpeg's official home is
[ffmpeg.org](https://ffmpeg.org/), which doesn't ship Windows binaries itself but links trusted
builders on its [download page](https://ffmpeg.org/download.html) (→ *Windows*). Install the
**gyan.dev _full_ build**: `winget install Gyan.FFmpeg`, or download `ffmpeg-full` from
[gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/), unzip, and add its `bin\` folder to
`PATH`; verify with `ffmpeg -version`. Use the *full* build (not the conda-forge one): the camera
auto-detects and prefers the `h264_nvenc` (NVIDIA GPU) encoder, which the full build ships but the
conda-forge build generally omits — otherwise capture silently falls back to CPU `libx264`.

### External tools
| Tool | Version / build | Purpose |
| :--- | :--- | :--- |
| MATLAB | R2024a | Runs Bpod (`Bpod_Gen2`) + WaveSurfer |
| WaveSurfer | 1.0.x (see `code/dependencies/Wavesurfer`) | Synchronized data acquisition (needs a DAQ) |
| ffmpeg ([ffmpeg.org](https://ffmpeg.org/)) | gyan.dev **full** build, on `PATH` | Live H.264 encoding in `videoacquisition.py`; full build needed for `h264_nvenc` (GPU) |
| Anaconda / Python | Python 3.11 | Runs the GUI + camera scripts (`treadwall` env) |
| Basler pylon Camera Software Suite | matching pypylon 4.1 | Camera drivers/runtime for `pypylon` |
| NI-DAQmx driver + NI DAQ device | — | WaveSurfer acquisition + TTL sync (the "DAQ-Box") |
| Pololu Tic software (Tic Control Center) | — | Configure the Wall Mover / Wall Synchronizer stepper controllers |
| Arduino IDE | 2.x ([arduino.cc](https://www.arduino.cc/en/software)) | Flash/modify the Wall-Synchronizer Arduino + rotary-encoder firmware |
| git | ≥ 2.x | Clone the repo with `--recurse-submodules` |

## Camera


## Data aquisition

