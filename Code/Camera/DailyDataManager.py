"""
DailyDataManager.py — end-of-day pipeline to reconstruct, move, and archive video data.

Run once at the end of each recording day:
    python DailyDataManager.py

Three phases, executed in order:
  1. Reconstruct  — encode any chunk_*.npy sessions on the NVMe that have no .mp4 yet
  2. Move to LTS  — move fully reconstructed sessions from NVMe to long-term storage
  3. Sync server  — copy any LTS sessions not yet present on the raw-data server

State is inferred from directory contents — no database needed.
"""

import os
import sys
import glob
import json
import shutil

# ======================================================================
# Configuration — edit these paths to match the current setup
# ======================================================================

NVME_BASE   = r"C:\Users\TomBombadil\Data"          # fast acquisition disc
LTS_BASE    = r"D:\Animals"                          # long-term storage
SERVER_BASE = r"Y:\AG-Beck\JosephineTimm"            # raw-data server
DEFAULT_FPS = 200                                    # fallback if metadata.json is absent
SERVER_SKIP_ANIMALS = {"FakeSubject"}               # animal folders to exclude from server sync

# ======================================================================
# Import reconstruction logic from sibling VideoReconstruct.py
# ======================================================================

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
from VideoReconstruct import run_reconstruction


# ======================================================================
# Helpers
# ======================================================================

def _load_meta(session_path):
    """Return metadata dict from session_metadata.json, or {} if absent/unreadable."""
    meta_file = os.path.join(session_path, "session_metadata.json")
    if not os.path.exists(meta_file):
        return {}
    try:
        with open(meta_file) as f:
            return json.load(f)
    except Exception:
        return {}


def _iter_sessions(base):
    """Yield (session_path, meta) for every cohort/animal/session directory under base."""
    if not os.path.isdir(base):
        return
    for cohort in sorted(os.listdir(base)):
        cohort_path = os.path.join(base, cohort)
        if not os.path.isdir(cohort_path):
            continue
        for animal in sorted(os.listdir(cohort_path)):
            animal_path = os.path.join(cohort_path, animal)
            if not os.path.isdir(animal_path):
                continue
            for session in sorted(os.listdir(animal_path)):
                session_path = os.path.join(animal_path, session)
                if not os.path.isdir(session_path):
                    continue
                yield session_path, _load_meta(session_path)


def _lts_target(session_path, meta):
    """Return the long-term storage path for a given NVMe session directory."""
    lts = meta.get("session_dir_lts", "")
    if lts and os.path.isabs(lts):
        return lts
    # Fallback: mirror NVMe hierarchy under LTS_BASE
    rel = os.path.relpath(session_path, NVME_BASE)
    return os.path.join(LTS_BASE, rel)


def _prune_empty_parents(path, stop_at):
    """Remove path and its empty ancestors up to (but not including) stop_at."""
    current = path
    while True:
        if os.path.normpath(current) == os.path.normpath(stop_at):
            break
        try:
            if not os.listdir(current):
                os.rmdir(current)
            else:
                break  # not empty, nothing left to prune
        except OSError:
            break
        current = os.path.dirname(current)


# ======================================================================
# Phase 1 — Reconstruct pending videos
# ======================================================================

def phase1_reconstruct():
    print("\n" + "=" * 60)
    print("Phase 1: Reconstruct pending videos")
    print("=" * 60)
    reconstructed = 0

    for session_path, meta in _iter_sessions(NVME_BASE):
        chunks_dirs = glob.glob(os.path.join(session_path, "*_frames"))
        mp4_files   = glob.glob(os.path.join(session_path, "*.mp4"))

        if not chunks_dirs:
            continue  # no acquisition data in this session dir

        if mp4_files:
            print(f"  [ok]   {session_path}")
            continue

        chunks_dir = chunks_dirs[0]
        fps    = meta.get("fps_estimated", DEFAULT_FPS)
        animal = meta.get("animal",  os.path.basename(os.path.dirname(session_path)))
        session = meta.get("session", os.path.basename(session_path))
        output_mp4 = os.path.join(session_path, f"{animal}_{session}.mp4")

        print(f"  [reconstruct] {session_path}")
        try:
            run_reconstruction(chunks_dir, output_mp4, fps)
            reconstructed += 1
        except Exception as exc:
            print(f"    ERROR: {exc}")

    return reconstructed


# ======================================================================
# Phase 2 — Move to long-term storage
# ======================================================================

def phase2_move_to_lts():
    print("\n" + "=" * 60)
    print("Phase 2: Move to long-term storage")
    print("=" * 60)
    moved = 0

    for session_path, meta in _iter_sessions(NVME_BASE):
        mp4_files = glob.glob(os.path.join(session_path, "*.mp4"))
        if not mp4_files:
            print(f"  [skip] No video yet: {session_path}")
            continue

        lts_target = _lts_target(session_path, meta)
        os.makedirs(lts_target, exist_ok=True)
        print(f"  [move] {session_path}")
        print(f"      → {lts_target}")

        all_ok = True
        for item in sorted(os.listdir(session_path)):
            src = os.path.join(session_path, item)
            dst = os.path.join(lts_target, item)
            if os.path.exists(dst):
                print(f"    [skip] Already at destination: {item}")
            else:
                try:
                    shutil.move(src, dst)
                    print(f"    Moved: {item}")
                except Exception as exc:
                    print(f"    ERROR moving {item}: {exc}")
                    all_ok = False

        if all_ok:
            try:
                os.rmdir(session_path)          # only succeeds if now empty
                _prune_empty_parents(os.path.dirname(session_path), NVME_BASE)
                moved += 1
            except OSError:
                print(f"    WARNING: Could not remove (not empty): {session_path}")
        else:
            print(f"    WARNING: Errors during move — session_path not removed.")

    return moved


# ======================================================================
# Phase 3 — Copy to server
# ======================================================================

def phase3_sync_server():
    print("\n" + "=" * 60)
    print("Phase 3: Sync to raw-data server")
    print("=" * 60)

    if not os.path.isdir(SERVER_BASE):
        print(f"  [skip] Server not accessible: {SERVER_BASE}")
        return 0, 0

    copied = 0
    skipped = 0

    for session_path, _ in _iter_sessions(LTS_BASE):
        rel = os.path.relpath(session_path, LTS_BASE)
        # rel is cohort\animal\session — skip excluded animal folders
        parts = rel.split(os.sep)
        if len(parts) >= 2 and parts[1] in SERVER_SKIP_ANIMALS:
            print(f"  [skip] Excluded animal '{parts[1]}': {session_path}")
            continue
        server_target = os.path.join(SERVER_BASE, rel)

        if os.path.exists(server_target):
            print(f"  [ok]   {server_target}")
            skipped += 1
        else:
            print(f"  [copy] {session_path}")
            print(f"      → {server_target}")
            try:
                shutil.copytree(session_path, server_target)
                copied += 1
            except Exception as exc:
                print(f"    ERROR: {exc}")

    return copied, skipped


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    print("Daily Data Manager")
    print(f"  NVMe  : {NVME_BASE}")
    print(f"  LTS   : {LTS_BASE}")
    print(f"  Server: {SERVER_BASE}")

    r1          = phase1_reconstruct()
    r2          = phase2_move_to_lts()
    r3, r3_skip = phase3_sync_server()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Reconstructed    : {r1} session(s)")
    print(f"  Moved to LTS     : {r2} session(s)")
    print(f"  Copied to server : {r3} session(s)  ({r3_skip} already present, skipped)")
