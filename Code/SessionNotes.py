r"""
Interactive session notes tool for Treadwall experiments.

Launched automatically from MATLAB at session start:
    python SessionNotes.py <animalID> <datetime_str> <sessionID> <session_dir>

Can also be run manually from a terminal (reads the saved session context):
    python Code/SessionNotes.py

Type notes and press Enter; each entry gets a timestamp. Type 'done' or
press Ctrl+C to finish, then choose whether to upload to RSpace.

One-time setup (run once before first use):
    import sys
    sys.path.insert(0, r'C:\Users\TomBombadil\CodingTools\IEECRSpace\src')
    import rspace
    rspace.save_credentials('YOUR_API_KEY', 'https://rspace.uni-bonn.de')
    rspace.save_lab_group('ag_beck')

Also set RSPACE_FOLDER_ID below to the numeric ID of your RSpace target folder
(find it in RSpace > My RSpace > right-click folder > Properties).
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, r'C:\Users\TomBombadil\CodingTools\IEECRSpace\src')
import rspace

# ── Configuration ────────────────────────────────────────────────────────────
CURRENT_SESSION_FILE = r"C:\Users\TomBombadil\Data\current_session.json"
RSPACE_FOLDER_ID = None   # Set to your RSpace folder ID (integer), e.g. 12345
RSPACE_METHOD_TAG = "m_invivo_imaging"  # Method tag added to every RSpace entry
# ─────────────────────────────────────────────────────────────────────────────


def _write_session_json(animal, date_time, session, session_dir_lts):
    base_name = f"{animal}_{date_time}_{session}"
    info = {
        "animal":          animal,
        "date_time":       date_time,
        "session":         session,
        "base_name":       base_name,
        "session_dir_lts": session_dir_lts,
    }
    os.makedirs(os.path.dirname(CURRENT_SESSION_FILE), exist_ok=True)
    with open(CURRENT_SESSION_FILE, 'w') as f:
        json.dump(info, f, indent=2)
    return info


def _load_session_json():
    if not os.path.exists(CURRENT_SESSION_FILE):
        print("ERROR: current_session.json not found.")
        print(f"  Expected at: {CURRENT_SESSION_FILE}")
        print("  Start SessionNotes.py from MATLAB, or pass args manually:")
        print("    python SessionNotes.py <animalID> <datetime_str> <sessionID> <session_dir>")
        sys.exit(1)
    with open(CURRENT_SESSION_FILE) as f:
        return json.load(f)


def _collect_notes():
    notes = []
    print()
    print("Type a note and press Enter to add it with a timestamp.")
    print("Type 'done' or press Ctrl+C to finish.\n")
    while True:
        try:
            text = input(f"[{datetime.now().strftime('%H:%M:%S')}] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if text.lower() == 'done':
            break
        if text:
            timestamp = datetime.now().strftime('%H:%M:%S')
            notes.append(f"[{timestamp}] {text}")
    return notes


def _upload(info, notes_text):
    if RSPACE_FOLDER_ID is None:
        print("\nRSPACE_FOLDER_ID is not set — open SessionNotes.py and set it to the")
        print("numeric ID of your target RSpace folder (right-click folder > Properties).")
        return

    if not rspace.has_credentials():
        print("\nNo RSpace credentials found. Run the one-time setup:")
        print("  import sys; sys.path.insert(0, r'C:\\Users\\TomBombadil\\CodingTools\\IEECRSpace\\src')")
        print("  import rspace; rspace.save_credentials('YOUR_API_KEY', 'https://rspace.uni-bonn.de')")
        return

    date, time_str = info['date_time'].split('_', 1)
    entry_name = f"{date}_{time_str}_{info['session']}"
    tags = [f"id_{info['animal']}", RSPACE_METHOD_TAG]

    try:
        rspace.create_entry(RSPACE_FOLDER_ID, tags, entry_name, notes_text)
        print(f"Uploaded to RSpace: {entry_name}  (tags: {', '.join(tags)})")
    except Exception as e:
        print(f"Upload failed: {e}")
        print("Draft is still saved locally and can be uploaded via the IEECRSpace GUI.")


def main():
    # When launched from MATLAB: SessionNotes.py <animal> <datetime_str> <session> <session_dir>
    if len(sys.argv) == 5:
        info = _write_session_json(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        info = _load_session_json()

    print("=" * 55)
    print(f"  Session notes for: {info['base_name']}")
    print("=" * 55)

    notes = _collect_notes()

    if not notes:
        print("No notes entered.")
        return

    notes_text = "\n".join(notes)
    print(f"\n--- {len(notes)} note(s) recorded ---")
    print(notes_text)

    # Always save a local draft first
    draft_id = info['base_name']
    date, time_str = info['date_time'].split('_', 1)
    draft_path = rspace.save_draft(draft_id, {
        "name":    f"{date}_{time_str}_{info['session']}",
        "tags":    [f"id_{info['animal']}", RSPACE_METHOD_TAG],
        "content": notes_text,
    })
    print(f"\nDraft saved: {draft_path}")

    # Offer to upload
    try:
        answer = input("\nUpload to RSpace now? (y/n): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        answer = 'n'

    if answer == 'y':
        _upload(info, notes_text)
    else:
        print("Skipped upload. Draft is saved and can be uploaded via the IEECRSpace GUI.")


if __name__ == '__main__':
    main()
