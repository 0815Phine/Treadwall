"""
TreadwallGUI.py - Central session management GUI for Treadwall experiments.

Replaces the StartSession.ps1 + SessionNotes.py combination.
Launch: double-click StartSession.bat  (or: python Code/TreadwallGUI.py)

Features:
  - Select RSpace notebook + animal ID from live dropdown (fetched from RSpace)
  - Start / update session without restarting MATLAB
  - Live camera preview from both cameras (requires VideoAquisition.py --preview-dir)
  - Timestamped note-taking with direct RSpace upload
  - Auto-detects when Bpod session ends; prompts for notes upload + WaveSurfer stop
"""

import html
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, r'C:\Users\TomBombadil\CodingTools\IEECRSpace\src')
import rspace

# ── Configuration ─────────────────────────────────────────────────────────────
MATLAB_EXE        = r"C:\Program Files\MATLAB\R2024a\bin\matlab.exe"
PYTHON_EXE        = r"C:\Users\TomBombadil\anaconda3\python.exe"
DATA_BASE         = r"D:\\"
IPC_DIR           = r"C:\Users\TomBombadil\Data\ipc"
PREVIEW_DIR       = r"C:\Users\TomBombadil\Data\preview"
RSPACE_METHOD_TAG = "m_invivo_imaging"
PROTOCOLS = [
    "Treadwall_Baseline",
    "Treadwall_Habituation_1",
    "Treadwall_Habituation_2",
    "Treadwall_scrambled",
    "Treadwall_predictable",
]
# ──────────────────────────────────────────────────────────────────────────────

_HERE         = Path(__file__).parent
CONFIG_FILE   = _HERE / "treadwall_config.json"
WS_FOLDER     = _HERE / "Wavesurfer"
WSP_FILE      = WS_FOLDER / "Treadwall.wsp"
CAMERA_SCRIPT = _HERE / "Camera" / "VideoAquisition.py"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def _save_config(data: dict) -> None:
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


class CameraPreviewThread(QThread):
    """Reads preview .npy files written by VideoAquisition.py and emits them."""
    frames_ready = pyqtSignal(object, object)

    def __init__(self, preview_dir: str):
        super().__init__()
        self._dir    = Path(preview_dir)
        self._active = True

    def run(self):
        top_f   = self._dir / "preview_top.npy"
        front_f = self._dir / "preview_front.npy"
        while self._active:
            try:
                top   = np.load(str(top_f))   if top_f.exists()   else None
                front = np.load(str(front_f)) if front_f.exists() else None
            except Exception:
                top, front = None, None
            self.frames_ready.emit(top, front)
            self.msleep(66)    # ~15 fps display, matches camera write rate

    def stop(self):
        self._active = False


class CameraLogThread(QThread):
    """Reads stdout lines from the camera subprocess and emits them."""
    line_ready = pyqtSignal(str)

    def __init__(self, proc):
        super().__init__()
        self._proc = proc

    def run(self):
        try:
            for line in self._proc.stdout:
                self.line_ready.emit(line.rstrip())
        except Exception:
            pass


class CameraReaperThread(QThread):
    """Waits for the camera process to exit on its own (it self-stops on the
    BNC trigger and then saves timestamps + metadata), so the GUI never kills it
    mid-save. Force-terminates only if it overruns the timeout. Runs off the GUI
    thread to keep the UI responsive."""
    finished_reaping = pyqtSignal()

    def __init__(self, proc, log_thr, timeout_s: int = 120):
        super().__init__()
        self._proc    = proc
        self._log_thr = log_thr
        self._timeout = timeout_s

    def run(self):
        try:
            self._proc.wait(timeout=self._timeout)
        except Exception:
            try:
                self._proc.terminate()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=5)
            except Exception:
                pass
        if self._log_thr is not None:
            self._log_thr.wait(2000)
        self.finished_reaping.emit()


class MatlabLogThread(QThread):
    """Tails the MATLAB diary file (mirror of the MATLAB command window) and the
    current-Bpod-state file, both written by the MATLAB side over IPC. Emits new
    log lines and the latest state for the whole GUI lifetime."""
    line_ready  = pyqtSignal(str)
    state_ready = pyqtSignal(str)

    def __init__(self, log_path: str, state_path: str):
        super().__init__()
        self._log_path   = Path(log_path)
        self._state_path = Path(state_path)
        self._active     = True
        self._pos        = 0
        self._last_state = None

    def run(self):
        while self._active:
            # ── Tail the MATLAB log ──────────────────────────────────────────
            try:
                if self._log_path.exists():
                    size = self._log_path.stat().st_size
                    if size < self._pos:
                        self._pos = 0          # file recreated on a fresh launch
                    if size > self._pos:
                        with open(self._log_path, "r", errors="replace") as f:
                            f.seek(self._pos)
                            data = f.read()
                            self._pos = f.tell()
                        for line in data.splitlines():
                            self.line_ready.emit(line)
                else:
                    self._pos = 0
            except Exception:
                pass

            # ── Poll the current Bpod state ──────────────────────────────────
            try:
                if self._state_path.exists():
                    state = self._state_path.read_text(errors="replace").strip()
                else:
                    state = ""
                if state != self._last_state:
                    self._last_state = state
                    self.state_ready.emit(state)
            except Exception:
                pass

            self.msleep(500)

    def stop(self):
        self._active = False


class TreadwallWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Treadwall Session Manager")
        self.setMinimumSize(1200, 720)

        self._cfg          = _load_config()
        self._notebook_map = {}   # label → id
        self._notebook_id  = None
        self._base_name    = None
        self._session_dir  = None
        self._datetime_str = None
        self._notes        = []
        self._matlab_proc        = None   # single MATLAB instance (WaveSurfer + Bpod)
        self._matlab_launch_time = None
        self._cam_proc     = None   # camera Python process
        self._preview_thr  = None   # CameraPreviewThread
        self._cam_log_thr  = None   # CameraLogThread
        self._cam_reaper   = None   # CameraReaperThread (graceful camera shutdown)
        self._matlab_log_thr = None # MatlabLogThread (MATLAB log mirror + Bpod state)

        try:
            self._rs = rspace.default_client()
        except Exception as e:
            self._rs = None
            print(f"RSpace unavailable: {e}")

        self._build_ui()
        self._populate_notebooks()

        # Drop stale completion/error/disconnect signals from a previous run so
        # we don't react to them on launch.
        for fname in ("session_done.flag", "session_error.json",
                      "bpod_disconnected.flag"):
            try:
                (Path(IPC_DIR) / fname).unlink(missing_ok=True)
            except Exception:
                pass

        # Tail the MATLAB log mirror + Bpod-state file for the whole GUI lifetime.
        self._matlab_log_thr = MatlabLogThread(
            str(Path(IPC_DIR) / "matlab_log.txt"),
            str(Path(IPC_DIR) / "bpod_state.txt"),
        )
        self._matlab_log_thr.line_ready.connect(self._on_matlab_log_line)
        self._matlab_log_thr.state_ready.connect(self._on_bpod_state)
        self._matlab_log_thr.start()

        # Poll IPC dir every 2 s for session_done.flag / session_error.json from Bpod
        self._ipc_timer = QTimer(self)
        self._ipc_timer.timeout.connect(self._poll_ipc)
        self._ipc_timer.start(2000)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root    = QWidget()
        self.setCentralWidget(root)
        outer   = QHBoxLayout(root)
        splitter = QSplitter(Qt.Horizontal)

        # ── Left panel: camera feeds ────────────────────────────────────
        left = QWidget()
        lv   = QVBoxLayout(left)
        lv.setSpacing(6)

        top_box = QGroupBox("Top Camera")
        tl = QVBoxLayout(top_box)
        self._lbl_top = self._make_cam_label()
        tl.addWidget(self._lbl_top)

        front_box = QGroupBox("Front Camera")
        fl = QVBoxLayout(front_box)
        self._lbl_front = self._make_cam_label()
        fl.addWidget(self._lbl_front)

        log_box = QGroupBox("Camera Log")
        ll = QVBoxLayout(log_box)
        self._cam_log = QTextEdit()
        self._cam_log.setReadOnly(True)
        self._cam_log.setFont(QFont("Consolas", 8))
        self._cam_log.setMinimumHeight(120)
        self._cam_log.document().setMaximumBlockCount(200)
        ll.addWidget(self._cam_log)

        mlog_box = QGroupBox("MATLAB Log")
        ml = QVBoxLayout(mlog_box)
        self._matlab_log = QTextEdit()
        self._matlab_log.setReadOnly(True)
        self._matlab_log.setFont(QFont("Consolas", 8))
        self._matlab_log.setMinimumHeight(150)
        self._matlab_log.document().setMaximumBlockCount(500)
        ml.addWidget(self._matlab_log)

        lv.addWidget(top_box)
        lv.addWidget(front_box)
        lv.addWidget(log_box)
        lv.addWidget(mlog_box)

        # ── Right panel: session setup + notes ──────────────────────────
        right = QWidget()
        rv    = QVBoxLayout(right)

        # Session setup group
        setup_box = QGroupBox("Session Setup")
        sv = QVBoxLayout(setup_box)

        sv.addLayout(self._row("Notebook:", self._make_combo("_nb_combo")))
        self._nb_combo.currentIndexChanged.connect(self._on_notebook_changed)

        sv.addLayout(self._row("Animal:", self._make_combo("_animal_combo")))

        self._session_edit = QLineEdit()
        self._session_edit.setPlaceholderText("e.g. S1_B1")
        sv.addLayout(self._row("Session ID:", self._session_edit))

        self._prot_combo = QComboBox()
        for p in PROTOCOLS:
            self._prot_combo.addItem(p)
        sv.addLayout(self._row("Protocol:", self._prot_combo))

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("START SESSION")
        self._start_btn.setStyleSheet(
            "QPushButton{background:#2a7a4a;color:white;font-weight:bold;padding:8px}"
            "QPushButton:hover{background:#35a060}"
        )
        self._start_btn.clicked.connect(self._on_start)

        # Single stop control: emergency stop. Sessions normally end on their own;
        # this aborts the running Bpod trial and then saves + stops everything.
        self._estop_btn = QPushButton("EMERGENCY STOP")
        self._estop_btn.setStyleSheet(
            "QPushButton{background:#cc0000;color:white;font-weight:bold;padding:8px}"
            "QPushButton:hover{background:#ff1111}"
            "QPushButton:disabled{background:#444;color:#888}"
        )
        self._estop_btn.setEnabled(False)
        self._estop_btn.clicked.connect(self._on_emergency_stop)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._estop_btn)
        sv.addLayout(btn_row)

        self._status_lbl = QLabel("Ready — select notebook and animal, then press Start.")
        self._status_lbl.setStyleSheet("color:#aaa;font-size:11px;")
        self._status_lbl.setWordWrap(True)
        sv.addWidget(self._status_lbl)

        # Live Bpod state (mirrors the Bpod console), fed from bpod_state.txt.
        self._state_lbl = QLabel("Bpod state: —")
        self._state_lbl.setStyleSheet("font-weight:bold;font-size:12px;color:#ddd;")
        sv.addWidget(self._state_lbl)

        # Clean disconnect of Bpod when done with all sessions (enabled only when
        # MATLAB is alive and no session is running).
        self._disconnect_btn = QPushButton("Disconnect Bpod")
        self._disconnect_btn.setStyleSheet(
            "QPushButton{background:#444;color:#ddd;padding:6px}"
            "QPushButton:hover{background:#666}"
            "QPushButton:disabled{background:#2a2a2a;color:#666}"
        )
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        sv.addWidget(self._disconnect_btn)

        # Notes group
        notes_box = QGroupBox("Session Notes")
        nv = QVBoxLayout(notes_box)

        self._notes_display = QTextEdit()
        self._notes_display.setReadOnly(True)
        self._notes_display.setFont(QFont("Consolas", 9))
        nv.addWidget(self._notes_display)

        note_row = QHBoxLayout()
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("Type a note and press Enter…")
        self._note_edit.returnPressed.connect(self._add_note)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_note)
        note_row.addWidget(self._note_edit, 1)
        note_row.addWidget(add_btn)
        nv.addLayout(note_row)

        self._upload_btn = QPushButton("Upload Notes to RSpace")
        self._upload_btn.clicked.connect(self._upload_notes)
        nv.addWidget(self._upload_btn)

        # Protocol parameters group (mirrors BpodParameterGUI)
        params_box = QGroupBox("Protocol Parameters")
        pv = QVBoxLayout(params_box)

        self._iti_spin   = self._make_spinbox(1.0, 0.1, 60.0)
        self._stim_spin  = self._make_spinbox(1.0, 0.1, 60.0)
        self._scale_spin = self._make_spinbox(1.0, 0.01, 10.0)
        pv.addLayout(self._row("ITI (s):",        self._iti_spin))
        pv.addLayout(self._row("Stim dur (s):",   self._stim_spin))
        pv.addLayout(self._row("Scaling factor:", self._scale_spin))

        for sp in (self._iti_spin, self._stim_spin, self._scale_spin):
            sp.valueChanged.connect(self._write_params)

        rv.addWidget(setup_box)
        rv.addWidget(params_box)
        rv.addWidget(notes_box, 1)

        # Scroll the left column so the extra MATLAB Log box never overflows the
        # fixed-size camera labels.
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left)

        splitter.addWidget(left_scroll)
        splitter.addWidget(right)
        splitter.setSizes([540, 440])
        outer.addWidget(splitter)

    @staticmethod
    def _make_spinbox(default: float, minimum: float, maximum: float) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setDecimals(2)
        sb.setRange(minimum, maximum)
        sb.setValue(default)
        sb.setSingleStep(0.1)
        return sb

    @staticmethod
    def _make_cam_label() -> QLabel:
        lbl = QLabel("Waiting for camera…")
        lbl.setFixedSize(480, 360)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background:#111;color:#555;border:1px solid #333;font-size:12px;")
        return lbl

    def _make_combo(self, attr: str) -> QComboBox:
        cb = QComboBox()
        setattr(self, attr, cb)
        return cb

    @staticmethod
    def _row(label: str, widget) -> QHBoxLayout:
        h = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(82)
        h.addWidget(lbl)
        h.addWidget(widget, 1)
        return h

    # ── RSpace ─────────────────────────────────────────────────────────────────

    def _populate_notebooks(self):
        if not self._rs:
            self._nb_combo.addItem("(RSpace unavailable)")
            return
        try:
            folders = self._rs.list_folders()
            self._notebook_map = {f['label']: f['id'] for f in folders}
            for label in self._notebook_map:
                self._nb_combo.addItem(label)
            last = self._cfg.get('notebook_label', '')
            idx  = self._nb_combo.findText(last)
            if idx >= 0:
                self._nb_combo.setCurrentIndex(idx)
        except Exception as e:
            self._set_status(f"RSpace error loading notebooks: {e}")

    def _on_notebook_changed(self, _idx):
        label = self._nb_combo.currentText()
        self._notebook_id = self._notebook_map.get(label)
        if not self._notebook_id or not self._rs:
            return
        try:
            tags    = self._rs.list_tags(folder_id=self._notebook_id)
            animals = sorted(t.removeprefix('id_') for t in tags if t.startswith('id_'))
            self._animal_combo.clear()
            for a in animals:
                self._animal_combo.addItem(a)
        except Exception as e:
            self._set_status(f"Could not fetch animal IDs: {e}")

    # ── Session start / stop ───────────────────────────────────────────────────

    def _on_start(self):
        animal   = self._animal_combo.currentText().strip()
        session  = self._session_edit.text().strip()
        protocol = self._prot_combo.currentText()

        if not animal or not session:
            QMessageBox.warning(self, "Missing info", "Animal ID and Session ID are required.")
            return

        self._datetime_str = datetime.now().strftime("%Y%m%d_%H%M")
        self._base_name    = f"{animal}_{self._datetime_str}_{session}"
        self._session_dir  = Path(DATA_BASE) / animal / session
        self._session_dir.mkdir(parents=True, exist_ok=True)

        # Persist notebook choice
        self._cfg['notebook_label'] = self._nb_combo.currentText()
        _save_config(self._cfg)

        ipc = Path(IPC_DIR)
        ipc.mkdir(parents=True, exist_ok=True)

        # Clear stale IPC flags from a previous session so a leftover flag can't
        # immediately stop/mis-report this one.
        for fname in ("emergency_stop.flag", "stop_wavesurfer.flag",
                      "session_done.flag", "session_error.json",
                      "shutdown.flag", "bpod_disconnected.flag", "bpod_state.txt"):
            try:
                (ipc / fname).unlink(missing_ok=True)
            except Exception:
                pass

        if self._matlab_is_alive():
            # MATLAB already running — write two separate IPC files so the
            # WaveSurfer timer and the Bpod waiting loop each read their own
            # file and there is no race condition over who deletes it first.
            payload = json.dumps({
                "animal_id":    animal,
                "session_id":   session,
                "datetime_str": self._datetime_str,
                "protocol":     protocol,
                "session_dir":  str(self._session_dir),
                "base_name":    self._base_name,
            })
            (ipc / "pending_ws.json").write_text(payload)
            (ipc / "pending_bpod.json").write_text(payload)
            self._set_status(f"Session updated: {self._base_name}")
        else:
            self._launch_matlab(animal, session, protocol)
            self._set_status(f"Launching: {self._base_name}")

        # Write initial protocol params IPC file
        self._write_params()

        # Always restart camera; clear stale preview files first
        self._stop_camera()
        for fname in ("preview_top.npy", "preview_front.npy"):
            p = Path(PREVIEW_DIR) / fname
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        self._lbl_top.setText("Waiting for trigger…")
        self._lbl_front.setText("Waiting for trigger…")
        self._start_camera(animal, session)

        # Reset notes pane
        self._notes = []
        self._notes_display.clear()
        self._notes_display.append(f"=== {self._base_name} ===\n")

        self._start_btn.setText("NEW SESSION")
        self._estop_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(False)   # a session is running now
        self.setWindowTitle(f"Treadwall — {self._base_name}")
        self._set_status(
            f"Session ready: {self._base_name}\n"
            f"→ Press RECORD in WaveSurfer when ready "
            f"(it will save as {self._base_name}.h5)"
        )

    # ── Process management ─────────────────────────────────────────────────────

    def _matlab_is_alive(self) -> bool:
        """True if an existing MATLAB session should be reused."""
        if self._matlab_proc is None:
            return False
        # Direct check — works if matlab.exe itself is the main process
        if self._matlab_proc.poll() is None:
            return True
        # Heartbeat check — StartBpodSession.m touches this file every 2 s in its wait loop
        hb = Path(IPC_DIR) / "matlab_alive.flag"
        if hb.exists() and time.time() - hb.stat().st_mtime < 10:
            return True
        # Startup grace — MATLAB takes ~30 s to start before the flag is written
        if self._matlab_launch_time is not None and time.time() - self._matlab_launch_time < 60:
            return True
        return False

    def _launch_matlab(self, animal: str, session: str, protocol: str):
        # Clear any stale heartbeat from a previous (possibly crashed) session
        try:
            (Path(IPC_DIR) / "matlab_alive.flag").unlink(missing_ok=True)
        except Exception:
            pass
        self._matlab_launch_time = time.time()
        # StartWaveSurfer opens WaveSurfer, starts the IPC timer, then returns.
        # StartBpodSession then runs in the same instance and blocks until end-of-day.
        ws_part   = (
            f"addpath('{WS_FOLDER}'); "
            f"StartWaveSurfer('{WSP_FILE}','{self._session_dir}','{self._base_name}'); "
        )
        bpod_part = (
            f"StartBpodSession('{animal}','{session}','{self._datetime_str}','{protocol}')"
        )
        self._matlab_proc = subprocess.Popen(
            [MATLAB_EXE, "-nosplash", "-r", ws_part + bpod_part]
        )

    def _start_camera(self, animal: str, session: str):
        Path(PREVIEW_DIR).mkdir(parents=True, exist_ok=True)
        self._cam_proc = subprocess.Popen(
            [
                PYTHON_EXE, "-u", str(CAMERA_SCRIPT),
                str(self._session_dir), animal, session, self._datetime_str,
                "--preview-dir", PREVIEW_DIR,
                "--no-display",
                "--overwrite",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, text=True,
        )
        self._cam_log.clear()
        self._cam_log_thr = CameraLogThread(self._cam_proc)
        self._cam_log_thr.line_ready.connect(self._on_cam_log_line)
        self._cam_log_thr.start()

        self._preview_thr = CameraPreviewThread(PREVIEW_DIR)
        self._preview_thr.frames_ready.connect(self._on_frames)
        self._preview_thr.start()

    def _stop_camera(self):
        """Hard stop: terminate the camera immediately. Used when clearing a
        previous camera before a new session and on app close."""
        if self._preview_thr is not None:
            self._preview_thr.stop()
            self._preview_thr.wait(2000)
            self._preview_thr = None
        if self._cam_proc is not None and self._cam_proc.poll() is None:
            self._cam_proc.terminate()
        if self._cam_log_thr is not None:
            self._cam_log_thr.wait(2000)
            self._cam_log_thr = None
        self._cam_proc = None

    def _finish_camera(self):
        """Graceful stop: the camera self-stops on the BNC trigger and then
        saves its timestamps + metadata, which can take several seconds. Wait
        for it to exit on its own in the background (force-kill only on timeout)
        so the GUI stays responsive and the camera data is never truncated."""
        if self._preview_thr is not None:
            self._preview_thr.stop()
            self._preview_thr.wait(2000)
            self._preview_thr = None

        proc    = self._cam_proc
        log_thr = self._cam_log_thr
        # Hand ownership to the reaper so a subsequent _start_camera can create
        # fresh handles without colliding with the background wait.
        self._cam_proc    = None
        self._cam_log_thr = None

        if proc is not None and proc.poll() is None:
            self._cam_reaper = CameraReaperThread(proc, log_thr)
            self._cam_reaper.finished_reaping.connect(self._on_camera_reaped)
            self._cam_reaper.start()
        elif log_thr is not None:
            log_thr.wait(2000)

    def _on_camera_reaped(self):
        self._cam_reaper = None

    # ── Camera display ─────────────────────────────────────────────────────────

    def _on_frames(self, top, front):
        for frame, lbl in ((top, self._lbl_top), (front, self._lbl_front)):
            if frame is None:
                continue
            h, w = frame.shape[:2]
            if frame.ndim == 2:
                fmt, bpl = QImage.Format_Grayscale8, w
            else:
                fmt, bpl = QImage.Format_RGB888, w * 3
            qimg = QImage(frame.tobytes(), w, h, bpl, fmt)
            px   = QPixmap.fromImage(qimg).scaled(
                lbl.width(), lbl.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            lbl.setPixmap(px)

    # ── IPC polling ────────────────────────────────────────────────────────────

    def _poll_ipc(self):
        """Called every 2 s; checks for session_error.json, session_done.flag and
        bpod_disconnected.flag from MATLAB."""
        ipc = Path(IPC_DIR)

        # Bpod cleanly disconnected — the rig is safe to close.
        disc_file = ipc / "bpod_disconnected.flag"
        if disc_file.exists():
            disc_file.unlink(missing_ok=True)
            self._estop_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(False)
            self._start_btn.setEnabled(False)
            self._set_status("Bpod disconnected — safe to close MATLAB and WaveSurfer.")
            return

        # Session failed to start/run — surface it and reset controls so the GUI
        # doesn't appear stuck "running".
        err_file = ipc / "session_error.json"
        if err_file.exists():
            try:
                msg = json.loads(err_file.read_text()).get("message", "unknown error")
            except Exception:
                msg = "unknown error"
            err_file.unlink(missing_ok=True)
            self._estop_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)   # idle now — disconnect allowed
            # Startup error → the camera never got its trigger and recorded
            # nothing, so stop it immediately rather than waiting it out.
            self._stop_camera()
            self._set_status(f"Session error: {msg}")
            QMessageBox.critical(
                self, "Session error",
                f"The session could not run:\n\n{msg}\n\n"
                "Fix the issue and press NEW SESSION to try again.",
            )
            return

        flag = ipc / "session_done.flag"
        if not flag.exists():
            return
        flag.unlink(missing_ok=True)
        self._estop_btn.setEnabled(False)
        self._disconnect_btn.setEnabled(True)   # idle now — disconnect allowed
        # Let the camera self-stop (via the BNC trigger) and finish writing its
        # frames/timestamps/metadata; don't kill it mid-save.
        self._finish_camera()
        # WaveSurfer stops automatically — the protocol already wrote stop_wavesurfer.flag
        self._set_status("Bpod protocol finished.")
        ans = QMessageBox.question(
            self, "Session complete",
            "Bpod protocol finished.\n\nUpload session notes to RSpace?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self._upload_notes()

    # ── Notes ──────────────────────────────────────────────────────────────────

    def _add_note(self):
        text = self._note_edit.text().strip()
        if not text:
            return
        ts    = datetime.now().strftime('%H:%M:%S')
        entry = f"[{ts}] {text}"
        self._notes.append(entry)
        self._notes_display.append(entry)
        self._note_edit.clear()

    def _upload_notes(self):
        if not self._notes:
            QMessageBox.information(self, "No notes", "No notes to upload.")
            return
        if not self._notebook_id:
            QMessageBox.warning(self, "No notebook", "Select an RSpace notebook first.")
            return
        if not self._rs:
            QMessageBox.warning(self, "No RSpace", "RSpace is not connected.")
            return

        animal     = self._animal_combo.currentText().strip()
        session    = self._session_edit.text().strip()
        # RSpace 'text' fields hold HTML, so newlines collapse — wrap each note
        # in its own paragraph (escaped) so it renders on a separate line.
        content    = "".join(f"<p>{html.escape(n)}</p>" for n in self._notes)
        entry_name = f"{self._datetime_str}_treadwall_{session}"
        tags       = [f"id_{animal}", RSPACE_METHOD_TAG]

        try:
            rspace.create_entry(self._notebook_id, tags, entry_name, content)
            QMessageBox.information(self, "Uploaded", f"RSpace entry created: {entry_name}")
        except Exception as e:
            QMessageBox.critical(self, "Upload failed", str(e))

    # ── Camera log ─────────────────────────────────────────────────────────────

    def _on_cam_log_line(self, line: str):
        self._cam_log.append(line)

    # ── MATLAB log + Bpod state ──────────────────────────────────────────────────

    def _on_matlab_log_line(self, line: str):
        self._matlab_log.append(line)

    def _on_bpod_state(self, state: str):
        self._state_lbl.setText(f"Bpod state: {state}" if state else "Bpod state: —")

    # ── Protocol parameters ─────────────────────────────────────────────────────

    def _write_params(self):
        params = {
            "ITIDur":        self._iti_spin.value(),
            "stimDur":       self._stim_spin.value(),
            "ScalingFactor": self._scale_spin.value(),
        }
        try:
            p = Path(IPC_DIR)
            p.mkdir(parents=True, exist_ok=True)
            (p / "protocol_params.json").write_text(json.dumps(params))
        except Exception as e:
            self._set_status(f"Could not write params IPC: {e}")

    def _on_emergency_stop(self):
        try:
            (Path(IPC_DIR) / "emergency_stop.flag").touch()
            # Disable immediately so a double-press can't queue a second soft code.
            self._estop_btn.setEnabled(False)
            self._set_status(
                "Emergency stop sent — aborting trial; session will save and stop."
            )
        except Exception as e:
            self._set_status(f"Emergency stop failed: {e}")

    def _on_disconnect(self):
        """Ask MATLAB to cleanly EndBpod when done for the day."""
        if not self._matlab_is_alive():
            self._set_status("No running MATLAB session to disconnect.")
            self._disconnect_btn.setEnabled(False)
            return
        ans = QMessageBox.question(
            self, "Disconnect Bpod",
            "Cleanly disconnect Bpod from MATLAB?\n\n"
            "MATLAB and WaveSurfer stay open so you can close them yourself.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        try:
            (Path(IPC_DIR) / "shutdown.flag").touch()
            self._disconnect_btn.setEnabled(False)
            self._set_status("Disconnecting Bpod…")
        except Exception as e:
            self._set_status(f"Disconnect failed: {e}")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)

    def closeEvent(self, event):
        self._stop_camera()
        if self._cam_reaper is not None:
            self._cam_reaper.wait(3000)
            self._cam_reaper = None
        if self._matlab_log_thr is not None:
            self._matlab_log_thr.stop()
            self._matlab_log_thr.wait(2000)
            self._matlab_log_thr = None
        self._ipc_timer.stop()
        event.accept()


def main():
    for d in (IPC_DIR, PREVIEW_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = TreadwallWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
