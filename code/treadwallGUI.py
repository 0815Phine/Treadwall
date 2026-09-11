"""
treadwallGUI.py - Central session management GUI for Treadwall experiments.

Sole launcher for a session (camera + Bpod + WaveSurfer + notes).
Launch: double-click startsession.bat  (or: python code/treadwallGUI.py)

Features:
  - Select RSpace notebook + animal ID from live dropdown (fetched from RSpace)
  - Start / update session without restarting MATLAB
  - Live camera preview from both cameras (requires videoacquisition.py --preview-dir)
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

sys.path.insert(0, str(Path(__file__).resolve().parent / "dependencies" / "IEECRSpace" / "src"))
import rspace

# ── Configuration (rig paths + hardware from parameters/treadwall_config.json) ──
_HERE       = Path(__file__).parent
CONFIG_FILE = _HERE / "parameters" / "treadwall_config.json"
with open(CONFIG_FILE) as _f:
    _CFG = json.load(_f)
_PATHS            = _CFG["paths"]
MATLAB_EXE        = _PATHS["matlab_exe"]
PYTHON_EXE        = _PATHS["python_exe"]
DATA_BASE         = _PATHS["data_root"]
IPC_DIR           = _PATHS["ipc_dir"]
PREVIEW_DIR       = _PATHS["preview_dir"]
RSPACE_METHOD_TAG = _CFG["rspace"]["method_tag"]
PROTOCOLS = [
    "treadwall_baseline",
    "treadwall_habituation_1",
    "treadwall_habituation_2",
    "treadwall_scrambled",
    "treadwall_predictable",
]
# Which Protocol Parameters each protocol reads live (via gui_readparams) and so
# can be adjusted in the GUI. Params not listed are fixed by the protocol and are
# shown greyed-out/read-only. Unknown protocols default to all three editable.
PROTOCOL_EDITABLE_PARAMS = {
    "treadwall_baseline":      set(),                                  # fixed once
    "treadwall_habituation_1": {"ITIDur", "stimDur", "ScalingFactor"},
    "treadwall_habituation_2": {"ITIDur", "stimDur", "ScalingFactor"},
    "treadwall_scrambled":     {"ITIDur", "stimDur", "ScalingFactor"},
    "treadwall_predictable":   {"ITIDur", "ScalingFactor"},            # no stimDur
}
# ──────────────────────────────────────────────────────────────────────────────

WSP_FILE      = _HERE / "parameters" / "wavesurfer" / "treadwall.wsp"
CAMERA_SCRIPT = _HERE / "src" / "videoacquisition.py"


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def _save_config(data: dict) -> None:
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


class CameraPreviewThread(QThread):
    """Reads preview .npy files written by videoacquisition.py and emits them."""
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
        # Start at the current end of the log so stale content from a previous
        # MATLAB run isn't dumped into the panel on launch. A fresh MATLAB launch
        # deletes + recreates the diary (size < pos), which run() detects and
        # resets to 0, so new content is still read in full.
        try:
            self._pos = self._log_path.stat().st_size if self._log_path.exists() else 0
        except Exception:
            self._pos = 0
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
    # Bpod-state status chip styling (toggled in _on_bpod_state).
    _STATE_STYLE_IDLE = (
        "font-weight:bold;font-size:18px;color:#888;"
        "background:#222;border:1px solid #333;border-radius:4px;padding:8px;"
    )
    _STATE_STYLE_ACTIVE = (
        "font-weight:bold;font-size:18px;color:white;"
        "background:#2a7a4a;border:1px solid #35a060;border-radius:4px;padding:8px;"
    )

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
        # Identifiers of the session the current notes belong to (set at session
        # start, so notes stay correctly attributed after the session ends even
        # if the animal/session fields are changed for the next run).
        self._cur_animal   = ""
        self._cur_session  = ""
        # True when the current notes are safely persisted (uploaded to RSpace or
        # written to a local draft). Empty notes count as saved. Used to decide
        # whether to auto-back-up before the next session clears them.
        self._notes_saved  = True
        self._matlab_proc        = None   # single MATLAB instance (WaveSurfer + Bpod)
        self._matlab_launch_time = None
        self._bpod_ready         = False  # WaveSurfer + Bpod finished initialising
        self._bpod_connected     = True   # False while Bpod is disconnected (standby)
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
                      "bpod_disconnected.flag", "loaded_params.json",
                      "camera_no_data.flag", "reconnect.flag", "quit.flag"):
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

        # Pre-warm MATLAB (WaveSurfer + Bpod) so they're ready by the first session.
        self._prewarm_matlab()

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
        # Editable so an animal ID can be typed by hand (e.g. when RSpace is
        # unreachable and the dropdown can't be populated from notebook tags).
        self._animal_combo.setEditable(True)
        self._animal_combo.setInsertPolicy(QComboBox.NoInsert)   # don't persist typed text
        self._animal_combo.lineEdit().setPlaceholderText("select or type animal ID")

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
            "QPushButton:disabled{background:#444;color:#888}"
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
        # Styled as a prominent status chip; colour switches with state in
        # _on_bpod_state (green = running, dim = idle).
        self._state_lbl = QLabel("Bpod state: —")
        self._state_lbl.setAlignment(Qt.AlignCenter)
        self._state_lbl.setStyleSheet(self._STATE_STYLE_IDLE)
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
        # One button toggles between disconnecting and reconnecting Bpod.
        self._disconnect_btn.clicked.connect(self._on_connect_btn)
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

        self._iti_spin   = self._make_spinbox(1.0, 0.1, 600.0)
        self._stim_spin  = self._make_spinbox(1.0, 0.1, 600.0)
        self._scale_spin = self._make_spinbox(1.0, 0.01, 10.0)
        pv.addLayout(self._row("ITI (s):",        self._iti_spin))
        pv.addLayout(self._row("Stim dur (s):",   self._stim_spin))
        pv.addLayout(self._row("Scaling factor:", self._scale_spin))

        for sp in (self._iti_spin, self._stim_spin, self._scale_spin):
            sp.valueChanged.connect(self._write_params)

        # Grey out parameters the selected protocol doesn't read live (e.g. all of
        # them for Baseline), so it's clear which are fixed / set once.
        self._prot_combo.currentTextChanged.connect(
            lambda _: self._update_param_editability())
        self._update_param_editability()

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
            last = self._cfg.get('rspace', {}).get('notebook_label', '')
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

        # A new session is about to overwrite the previous session's identifiers
        # and clear the notes pane — back up any un-uploaded notes from the last
        # session first so a forgotten upload can't lose them.
        self._backup_pending_notes()

        self._datetime_str = datetime.now().strftime("%Y%m%d_%H%M")
        self._base_name    = f"{animal}_{self._datetime_str}_{session}"
        self._session_dir  = Path(DATA_BASE) / animal / session
        self._session_dir.mkdir(parents=True, exist_ok=True)

        # Persist notebook choice
        self._cfg.setdefault('rspace', {})['notebook_label'] = self._nb_combo.currentText()
        _save_config(self._cfg)

        ipc = Path(IPC_DIR)
        ipc.mkdir(parents=True, exist_ok=True)

        # Clear stale IPC flags from a previous session so a leftover flag can't
        # immediately stop/mis-report this one.
        for fname in ("emergency_stop.flag", "stop_wavesurfer.flag",
                      "session_done.flag", "session_error.json",
                      "shutdown.flag", "bpod_disconnected.flag", "bpod_state.txt",
                      "protocol_params.json", "loaded_params.json",
                      "camera_no_data.flag", "reconnect.flag", "quit.flag"):
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

        # Do NOT pre-seed protocol_params.json here — the protocol publishes its
        # own loaded values to loaded_params.json, which _poll_ipc ingests into
        # the spinboxes. protocol_params.json is only written when the user edits
        # a value afterwards (so live changes still propagate per-trial).

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

        # Reset notes pane and record which session these notes belong to.
        self._notes = []
        self._notes_saved = True   # empty notes are trivially "saved"
        self._cur_animal  = animal
        self._cur_session = session
        self._notes_display.clear()
        self._notes_display.append(f"=== {self._base_name} ===\n")

        self._start_btn.setText("NEW SESSION")
        self._start_btn.setEnabled(False)        # can't start another mid-session
        self._estop_btn.setEnabled(True)
        self._disconnect_btn.setEnabled(False)   # a session is running now
        self._set_setup_enabled(False)           # lock setup fields during a session
        self.setWindowTitle(f"Treadwall — {self._base_name}")
        self._set_status(
            f"Session ready: {self._base_name}\n"
            f"→ Press RECORD in WaveSurfer when ready "
            f"(it will save as {self._base_name}.h5)"
        )

    # ── Process management ─────────────────────────────────────────────────────

    def _matlab_is_alive(self) -> bool:
        """True if an existing MATLAB session should be reused."""
        # Owned process still running — covers the whole prewarm/launch init window.
        if self._matlab_proc is not None and self._matlab_proc.poll() is None:
            return True
        # Heartbeat check — start_bpodsession.m touches this file every ~2 s in its
        # wait loop. Also covers a MATLAB adopted from a previous GUI run, for which
        # we have no owned process handle.
        hb = Path(IPC_DIR) / "matlab_alive.flag"
        if hb.exists() and time.time() - hb.stat().st_mtime < 10:
            return True
        # Startup grace — MATLAB takes ~30 s to start before the flag is written.
        if self._matlab_launch_time is not None and time.time() - self._matlab_launch_time < 60:
            return True
        return False

    def _spawn_matlab(self, session_dir: str, base_name: str,
                      animal: str, session: str, datetime_str: str, protocol: str):
        """Launch one MATLAB instance: start_wavesurfer opens WaveSurfer + its IPC
        timer and returns, then start_bpodsession runs in the same instance and
        blocks in its multi-session wait loop until end-of-day. An empty protocol
        makes start_bpodsession pre-warm (init + wait, no protocol run)."""
        # Clear any stale heartbeat from a previous (possibly crashed) session
        try:
            (Path(IPC_DIR) / "matlab_alive.flag").unlink(missing_ok=True)
        except Exception:
            pass
        self._matlab_launch_time = time.time()
        ws_part   = (
            f"addpath(genpath('{_HERE / 'src'}')); "
            f"addpath(genpath('{_HERE / 'protocols'}')); "
            f"addpath('{_HERE / 'parameters' / 'bpod'}'); "
            f"start_wavesurfer('{WSP_FILE}','{session_dir}','{base_name}'); "
        )
        bpod_part = (
            f"start_bpodsession('{animal}','{session}','{datetime_str}','{protocol}')"
        )
        self._matlab_proc = subprocess.Popen(
            [MATLAB_EXE, "-nosplash", "-r", ws_part + bpod_part]
        )

    def _launch_matlab(self, animal: str, session: str, protocol: str):
        self._spawn_matlab(str(self._session_dir), self._base_name,
                           animal, session, self._datetime_str, protocol)

    def _prewarm_matlab(self):
        """Launch MATLAB (WaveSurfer + Bpod) at GUI startup with placeholder names
        so they initialise while the operator sets up. The first Start Session then
        just updates the names via the pending IPC (like a subsequent session).

        If a MATLAB from a previous GUI run is still alive (fresh heartbeat), adopt
        it instead of spawning a second instance (which would collide on Bpod).

        Start stays disabled until start_bpodsession signals readiness via
        bpod_ready.flag (picked up in _poll_ipc); on a launch failure Start is left
        enabled so the on-demand launch path still works."""
        hb = Path(IPC_DIR) / "matlab_alive.flag"
        try:
            if hb.exists() and time.time() - hb.stat().st_mtime < 10:
                self._matlab_launch_time = time.time()
                # Existing MATLAB already ran init — its bpod_ready.flag (if in the
                # wait loop) re-enables Start on the next poll.
                self._start_btn.setEnabled(False)
                self._set_status("Existing MATLAB (WaveSurfer + Bpod) detected — reusing it.")
                return
        except Exception:
            pass
        try:
            # Fresh launch — drop any stale readiness/standby flags and gate Start
            # until the new MATLAB reports ready.
            (Path(IPC_DIR) / "bpod_ready.flag").unlink(missing_ok=True)
            (Path(IPC_DIR) / "bpod_standby.flag").unlink(missing_ok=True)
            self._start_btn.setEnabled(False)
            # Empty protocol → start_bpodsession pre-warms (init + wait, no run).
            self._spawn_matlab(DATA_BASE, "prewarm", "prewarm", "prewarm", "", "")
            self._set_status(
                "Starting WaveSurfer + Bpod (placeholder names) — "
                "Start will enable once they're ready."
            )
        except Exception as e:
            self._start_btn.setEnabled(True)   # fallback: allow on-demand launch
            self._set_status(f"Could not pre-launch MATLAB: {e}")

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

        # Protocol published its loaded parameters — show them as the initial
        # values in the spinboxes (these override whatever was selected before).
        lp_file = ipc / "loaded_params.json"
        if lp_file.exists():
            try:
                self._apply_loaded_params(json.loads(lp_file.read_text()))
            except Exception:
                pass
            lp_file.unlink(missing_ok=True)

        # WaveSurfer + Bpod finished initialising (or reconnected) — enable Start.
        if not self._bpod_ready and (ipc / "bpod_ready.flag").exists():
            self._bpod_ready = True
            self._bpod_connected = True
            self._start_btn.setEnabled(True)
            self._set_connect_mode(connected=True, enabled=True)
            self._set_status("WaveSurfer + Bpod ready — you can start a session.")

        # Bpod disconnected (standby) — offer Reconnect, disable Start. Triggered by
        # the one-shot bpod_disconnected.flag, or by a persistent bpod_standby.flag
        # (covers a GUI reopened while MATLAB was already in standby).
        disc_file = ipc / "bpod_disconnected.flag"
        in_standby = (ipc / "bpod_standby.flag").exists()
        if disc_file.exists() or (in_standby and self._bpod_connected):
            disc_file.unlink(missing_ok=True)
            self._bpod_ready = False
            self._bpod_connected = False
            self._estop_btn.setEnabled(False)
            self._start_btn.setEnabled(False)
            self._set_connect_mode(connected=False, enabled=True)
            self._set_status(
                "Bpod disconnected — press \"Reconnect Bpod\" to reconnect, "
                "or close the windows to quit."
            )
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
            self._start_btn.setEnabled(True)        # idle — can start again
            self._disconnect_btn.setEnabled(True)   # idle now — disconnect allowed
            self._set_setup_enabled(True)           # idle — setup editable again
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
        # The protocol marks camera_no_data.flag when it stopped before any
        # acquisition (e.g. emergency stop while waiting for WaveSurfer). In that
        # case the camera never triggered, so it can't self-stop on the BNC pulse
        # and has nothing to save — hard-stop it to release the devices at once.
        no_data = ipc / "camera_no_data.flag"
        aborted = no_data.exists()
        if aborted:
            no_data.unlink(missing_ok=True)
        self._estop_btn.setEnabled(False)
        self._start_btn.setEnabled(True)        # idle — can start again
        self._disconnect_btn.setEnabled(True)   # idle now — disconnect allowed
        self._set_setup_enabled(True)           # idle — setup editable again
        if aborted:
            self._stop_camera()
        else:
            # Let the camera self-stop (via the BNC trigger) and finish writing its
            # frames/timestamps/metadata; don't kill it mid-save.
            self._finish_camera()
        # WaveSurfer stops automatically — the protocol already wrote stop_wavesurfer.flag
        self._set_status(
            "Session stopped before start — camera released." if aborted
            else "Bpod protocol finished."
        )
        ans = QMessageBox.question(
            self, "Session complete",
            "Bpod protocol finished.\n\nUpload session notes to RSpace?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self._upload_notes()
        # If declined, the notes stay in the pane so more can be added or uploaded
        # later via the button. They're auto-backed-up at the next session start
        # (_backup_pending_notes) if still un-uploaded, so a forgotten upload can't
        # lose them.
        # Consistent end-of-session state (identical after every session): the
        # operator can start another session or shut down via Disconnect Bpod.
        self._set_status(
            "Session complete.\n"
            "→ Start a NEW SESSION, or click \"Disconnect Bpod\" "
            "and then close this window."
        )

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
        self._notes_saved = False   # new content not yet uploaded/drafted

    def _current_note_payload(self):
        """Build the (entry_name, tags, content) for the current notes, or None
        if there are no notes. Uses the identifiers of the session the notes
        belong to (captured at session start), not the live animal/session fields
        — those may already point at the next session."""
        if not self._notes:
            return None
        animal     = self._cur_animal
        session    = self._cur_session
        # RSpace 'text' fields hold HTML, so newlines collapse — wrap each note
        # in its own paragraph (escaped) so it renders on a separate line.
        content    = "".join(f"<p>{html.escape(n)}</p>" for n in self._notes)
        entry_name = f"{self._datetime_str}_treadwall_{session}"
        tags       = [f"id_{animal}", RSPACE_METHOD_TAG]
        return entry_name, tags, content

    def _write_note_draft(self, entry_name: str, tags: list, content: str) -> str:
        """Write the notes to a local RSpace draft (via rspace.save_draft) and
        return the draft path. Raises on failure."""
        draft_id = self._base_name or entry_name
        return rspace.save_draft(draft_id, {
            "name":    entry_name,
            "tags":    tags,
            "content": content,
        })

    def _upload_notes(self):
        payload = self._current_note_payload()
        if payload is None:
            QMessageBox.information(self, "No notes", "No notes to upload.")
            return
        entry_name, tags, content = payload

        # Try the live upload; if it can't happen (no client, no notebook, or the
        # call fails), fall back to a local draft so the notes are never lost.
        if self._rs and self._notebook_id:
            try:
                rspace.create_entry(self._notebook_id, tags, entry_name, content)
                self._notes_saved = True
                QMessageBox.information(self, "Uploaded", f"RSpace entry created: {entry_name}")
                return
            except Exception as e:
                reason = str(e)
        elif not self._rs:
            reason = "RSpace is not connected"
        else:
            reason = "no RSpace notebook selected"

        self._save_notes_backup(entry_name, tags, content, reason)

    def _save_notes_backup(self, entry_name: str, tags: list, content: str, reason: str):
        """RSpace upload failed — save a local draft that can be uploaded later
        from the IEECRSpace GUI."""
        try:
            draft_path = self._write_note_draft(entry_name, tags, content)
            self._notes_saved = True
            QMessageBox.warning(
                self, "Upload failed — saved locally",
                f"Could not upload to RSpace ({reason}).\n\n"
                f"Notes saved as a local draft:\n{draft_path}\n\n"
                "Upload it later from the IEECRSpace GUI.",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Upload and backup both failed",
                f"Could not upload to RSpace ({reason}) and could not save a "
                f"local draft either:\n\n{e}",
            )

    def _backup_pending_notes(self):
        """Safety net called just before a new session clears the notes pane. If
        the previous session's notes were never uploaded or drafted (the operator
        declined the upload and forgot to do it later), save them to a local draft
        so they aren't lost. No-op if there are no notes or they're already saved."""
        if self._notes_saved:
            return
        payload = self._current_note_payload()
        if payload is None:
            return
        entry_name, tags, content = payload
        try:
            draft_path = self._write_note_draft(entry_name, tags, content)
            self._notes_saved = True
            QMessageBox.information(
                self, "Previous notes backed up locally",
                f"The previous session's notes were never uploaded, so they were "
                f"saved as a local draft:\n{draft_path}\n\n"
                "Upload it later from the IEECRSpace GUI.",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Backup failed",
                f"The previous session's notes were not uploaded and a local "
                f"draft could not be saved either:\n\n{e}",
            )

    # ── Camera log ─────────────────────────────────────────────────────────────

    def _on_cam_log_line(self, line: str):
        self._cam_log.append(line)

    # ── MATLAB log + Bpod state ──────────────────────────────────────────────────

    def _on_matlab_log_line(self, line: str):
        self._matlab_log.append(line)

    def _on_bpod_state(self, state: str):
        if state:
            self._state_lbl.setText(f"Bpod: {state}")
            self._state_lbl.setStyleSheet(self._STATE_STYLE_ACTIVE)
        else:
            self._state_lbl.setText("Bpod state: —")
            self._state_lbl.setStyleSheet(self._STATE_STYLE_IDLE)

    # ── Protocol parameters ─────────────────────────────────────────────────────

    def _update_param_editability(self):
        """Enable only the Protocol Parameters the selected protocol reads live;
        grey out (with a tooltip) the ones it fixes, so it's clear they're set
        once and not adjustable during the session (e.g. all of them for Baseline)."""
        protocol = self._prot_combo.currentText()
        editable = PROTOCOL_EDITABLE_PARAMS.get(
            protocol, {"ITIDur", "stimDur", "ScalingFactor"})
        for key, spin in (("ITIDur",        self._iti_spin),
                          ("stimDur",       self._stim_spin),
                          ("ScalingFactor", self._scale_spin)):
            on = key in editable
            spin.setEnabled(on)
            spin.setToolTip("" if on else
                            "Fixed by this protocol — set once, not adjustable during the session.")

    def _apply_loaded_params(self, params: dict):
        """Set the spinboxes to the protocol's loaded values. Signals are blocked
        so applying them does not immediately re-write protocol_params.json (that
        only happens when the user edits a value)."""
        for key, spin in (("ITIDur",        self._iti_spin),
                          ("stimDur",       self._stim_spin),
                          ("ScalingFactor", self._scale_spin)):
            if key in params:
                spin.blockSignals(True)
                try:
                    spin.setValue(float(params[key]))
                finally:
                    spin.blockSignals(False)

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

    def _set_connect_mode(self, connected: bool, enabled: bool):
        """Toggle the connect button between Disconnect (when Bpod is connected)
        and Reconnect (when it's in standby), and set its enabled state."""
        self._disconnect_btn.setText("Disconnect Bpod" if connected else "Reconnect Bpod")
        self._disconnect_btn.setEnabled(enabled)

    def _on_connect_btn(self):
        """Single button: disconnect when connected, reconnect when in standby."""
        if self._bpod_connected:
            self._on_disconnect()
        else:
            self._on_reconnect()

    def _on_disconnect(self):
        """Ask MATLAB to cleanly EndBpod (e.g. to fix code), staying alive so it can
        be reconnected without restarting the GUI."""
        if not self._matlab_is_alive():
            self._set_status("No running MATLAB session to disconnect.")
            self._disconnect_btn.setEnabled(False)
            return
        ans = QMessageBox.question(
            self, "Disconnect Bpod",
            "Cleanly disconnect Bpod from MATLAB?\n\n"
            "MATLAB and WaveSurfer stay open; press \"Reconnect Bpod\" to bring "
            "Bpod back.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        try:
            # Drop readiness locally so a poll can't re-enable Start before MATLAB
            # finishes disconnecting.
            self._bpod_ready = False
            (Path(IPC_DIR) / "bpod_ready.flag").unlink(missing_ok=True)
            (Path(IPC_DIR) / "shutdown.flag").touch()
            self._start_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(False)
            self._set_status("Disconnecting Bpod…")
        except Exception as e:
            self._set_status(f"Disconnect failed: {e}")

    def _on_reconnect(self):
        """Ask MATLAB (in standby) to re-initialise Bpod. Readiness returns via
        bpod_ready.flag, which re-enables Start and flips the button back."""
        try:
            (Path(IPC_DIR) / "reconnect.flag").touch()
            self._disconnect_btn.setEnabled(False)
            self._set_status("Reconnecting Bpod…")
        except Exception as e:
            self._set_status(f"Reconnect failed: {e}")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _set_setup_enabled(self, on: bool):
        """Enable/disable the session-setup inputs so they can't be changed while a
        session is running."""
        for w in (self._nb_combo, self._animal_combo, self._session_edit,
                  self._prot_combo):
            w.setEnabled(on)

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)

    def closeEvent(self, event):
        # Release MATLAB from the connect/standby loop back to a normal prompt.
        try:
            (Path(IPC_DIR) / "quit.flag").touch()
        except Exception:
            pass
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
