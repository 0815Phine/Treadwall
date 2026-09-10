"""
DailyDataManager.py — end-of-day pipeline to sync recorded data to the server.

Run once at the end of each recording day:
    python DailyDataManager.py

The camera now encodes video live to .mp4 straight into each session's data folder
on long-term storage, so the old NVMe reconstruct + move-to-LTS steps are gone. The
only remaining job is:
  - Sync server — copy any LTS sessions not yet present on the raw-data server

State is inferred from directory contents — no database needed.
"""

import os
import json
import shutil

# ======================================================================
# Configuration — edit these paths to match the current setup
# TODO: migrate to the central config (parameters/treadwall_config.json → paths.server)
#       when DailyDataManager is reworked.
# ======================================================================

LTS_BASE    = r"D:\Animals"                          # long-term storage
SERVER_BASE = r"Y:\AG-Beck\JosephineTimm"            # raw-data server
SERVER_SKIP_ANIMALS = {"FakeSubject"}               # animal folders to exclude from server sync


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


# ======================================================================
# Sync to server
# ======================================================================

def sync_server():
    print("\n" + "=" * 60)
    print("Sync to raw-data server")
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
    print(f"  LTS   : {LTS_BASE}")
    print(f"  Server: {SERVER_BASE}")

    copied, skipped = sync_server()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Copied to server : {copied} session(s)  ({skipped} already present, skipped)")
