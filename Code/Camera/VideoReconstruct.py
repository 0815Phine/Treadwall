"""
VideoReconstruct.py — reconstruct a video from chunked .npy frame files.

GUI mode (no arguments):
    python VideoReconstruct.py

CLI mode:
    python VideoReconstruct.py <chunks_dir> <output_video_path> <fps> [output_dir]

The script also copies the accompanying _video_timestamps.txt (if found in the
parent of chunks_dir) to the output directory so MATLAB analysis scripts can
locate both the video and timestamps in one folder.
"""

import sys
import os
import glob
import shutil
import subprocess
import time
import queue
import threading
import numpy as np


# ======================================================================
# Core reconstruction logic (shared by GUI and CLI)
# ======================================================================

def _has_nvenc():
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False


def run_reconstruction(chunks_dir, output_video_path, fps, output_dir=None, log_fn=print):
    """
    Reconstruct a video from chunk_NNNNNN.npy files.

    Parameters
    ----------
    chunks_dir        : directory containing chunk_NNNNNN.npy files
    output_video_path : full path for the output .mp4 (filename used even if output_dir given)
    fps               : frame rate for the output video
    output_dir        : if given, video is placed here instead
    log_fn            : callable(str) for progress messages — print in CLI, GUI widget writer
    """
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_video_path = os.path.join(output_dir, os.path.basename(output_video_path))
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)

    # --- Discover and sort chunk files ---
    chunk_files = sorted(
        glob.glob(os.path.join(chunks_dir, "chunk_??????.npy")),
        key=lambda p: int(os.path.basename(p)[6:12])
    )
    if not chunk_files:
        raise FileNotFoundError(f"No chunk files (chunk_NNNNNN.npy) found in: {chunks_dir}")

    # --- Detect frame dimensions / pixel format from the data itself ---
    # (Resolution varies between recording sessions, so never hardcode it.)
    first = np.load(chunk_files[0], mmap_mode='r')
    if first.ndim == 4 and first.shape[-1] == 3:
        height, width = int(first.shape[1]), int(first.shape[2])
        pix_fmt_in = "rgb24"
    elif first.ndim == 3:
        height, width = int(first.shape[1]), int(first.shape[2])
        pix_fmt_in = "gray"
    else:
        raise ValueError(
            f"Unexpected chunk shape {first.shape} in {chunk_files[0]}; "
            "expected (frames, H, W) grayscale or (frames, H, W, 3) color."
        )

    total_frames = sum(np.load(f, mmap_mode='r').shape[0] for f in chunk_files)
    log_fn(f"Found {len(chunk_files)} chunks, {total_frames} frames total")
    log_fn(f"Frame size: {width}x{height} ({pix_fmt_in})")
    log_fn(f"Frame rate: {fps} Hz")
    log_fn(f"Output: {output_video_path}")

    # --- Select encoder ---
    encoder = "h264_nvenc" if _has_nvenc() else "libx264"
    log_fn(f"Using encoder: {encoder}")

    # --- Build ffmpeg command ---
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", pix_fmt_in,
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "pipe:0",
    ]
    if encoder == "h264_nvenc":
        # nvenc does not support -crf; use constant QP mode
        ffmpeg_cmd += [
            "-vcodec", "h264_nvenc",
            "-gpu", "0",
            "-profile:v", "high",
            "-preset", "p4",
            "-rc", "constqp",
            "-qp", "17",
        ]
    else:
        ffmpeg_cmd += [
            "-vcodec", "libx264",
            "-preset", "fast",
            "-crf", "17",
        ]
    ffmpeg_cmd += ["-pix_fmt", "yuv420p", "-an", output_video_path]

    # --- Pipe chunks to ffmpeg ---
    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    frames_written = 0
    t0 = time.perf_counter()

    stderr_bytes = b""
    try:
        for chunk_file in chunk_files:
            data = np.load(chunk_file)
            proc.stdin.write(data.tobytes())
            frames_written += data.shape[0]
            pct = frames_written / total_frames * 100
            log_fn(f"  {frames_written}/{total_frames} frames ({pct:.1f}%)")

        proc.stdin.close()
        # communicate() drains the stderr pipe while waiting for ffmpeg to exit.
        # Using proc.wait() here deadlocks once the ~64 KB stderr buffer fills.
        _, stderr_bytes = proc.communicate()

    except BrokenPipeError:
        proc.communicate()  # drain stderr to unblock ffmpeg before reading
        raise RuntimeError("ffmpeg terminated early")

    stderr_str = (stderr_bytes or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg error (code {proc.returncode}):\n{stderr_str}")

    elapsed = time.perf_counter() - t0
    log_fn(f"Reconstruction complete: {frames_written} frames in {elapsed:.1f}s")
    log_fn(f"Video saved to: {output_video_path}")

    # --- Copy timestamps.txt alongside video so MATLAB can find both together ---
    out_dir = output_dir or os.path.dirname(os.path.abspath(output_video_path))
    parent_dir = os.path.dirname(os.path.abspath(chunks_dir))
    # Frame dirs are named "<stem>_frames" with timestamps "<stem>_timestamps.txt"
    # in the parent (session) directory, e.g. "..._frontcam_frames" ->
    # "..._frontcam_timestamps.txt". Fall back to older "*_video_timestamps.txt".
    chunks_base = os.path.basename(os.path.normpath(chunks_dir))
    ts_candidates = []
    if chunks_base.endswith("_frames"):
        derived = os.path.join(parent_dir, chunks_base[:-len("_frames")] + "_timestamps.txt")
        if os.path.exists(derived):
            ts_candidates = [derived]
    if not ts_candidates:
        ts_candidates = (glob.glob(os.path.join(parent_dir, "*_timestamps.txt"))
                         or glob.glob(os.path.join(parent_dir, "*_video_timestamps.txt")))
    if ts_candidates:
        ts_src = ts_candidates[0]
        ts_dst = os.path.join(out_dir, os.path.basename(ts_src))
        if os.path.abspath(ts_src) != os.path.abspath(ts_dst):
            shutil.copy2(ts_src, ts_dst)
            log_fn(f"Timestamps copied to: {ts_dst}")
        else:
            log_fn(f"Timestamps already at destination.")
    else:
        log_fn("No timestamps file found alongside chunks directory.")


# ======================================================================
# Batch reconstruction (walk a root directory)
# ======================================================================

def find_frame_dirs(root_dir):
    """Return sorted list of '*_frames' directories under root_dir that
    actually contain chunk_NNNNNN.npy files."""
    found = []
    for dirpath, dirnames, _ in os.walk(root_dir):
        for d in dirnames:
            if d.endswith("_frames"):
                full = os.path.join(dirpath, d)
                if glob.glob(os.path.join(full, "chunk_??????.npy")):
                    found.append(full)
    return sorted(found)


def run_batch(root_dir, fps, log_fn=print, skip_existing=True):
    """
    Reconstruct every '*_frames' directory found under root_dir.

    The output .mp4 is written next to each frames directory (in the session
    folder), named after the frames directory with '_frames' stripped.
    Failures are isolated so one bad folder does not abort the whole run.
    """
    frame_dirs = find_frame_dirs(root_dir)
    if not frame_dirs:
        raise FileNotFoundError(f"No '*_frames' directories with chunks found under: {root_dir}")

    log_fn(f"=== Batch: {len(frame_dirs)} frame folder(s) under {root_dir} ===")

    succeeded, skipped, failed = [], [], []
    for i, chunks_dir in enumerate(frame_dirs, 1):
        base = os.path.basename(os.path.normpath(chunks_dir))
        name = base[:-len("_frames")] if base.endswith("_frames") else base
        session_dir = os.path.dirname(os.path.normpath(chunks_dir))
        output_video_path = os.path.join(session_dir, name + ".mp4")

        log_fn("")
        log_fn(f"--- [{i}/{len(frame_dirs)}] {base} ---")

        if skip_existing and os.path.exists(output_video_path):
            log_fn(f"  Output already exists, skipping: {output_video_path}")
            skipped.append(chunks_dir)
            continue

        try:
            run_reconstruction(chunks_dir, output_video_path, fps, log_fn=log_fn)
            succeeded.append(chunks_dir)
        except Exception as exc:
            log_fn(f"  ERROR reconstructing {base}: {exc}")
            failed.append((chunks_dir, str(exc)))

    log_fn("")
    log_fn(f"=== Batch complete: {len(succeeded)} ok, {len(skipped)} skipped, {len(failed)} failed ===")
    for cd, err in failed:
        log_fn(f"  FAILED: {cd} -> {err}")
    return succeeded, skipped, failed


# ======================================================================
# tkinter GUI
# ======================================================================

def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Video Reconstruction")
    root.resizable(True, True)

    # ---- StringVars ----
    var_chunks = tk.StringVar()
    var_output = tk.StringVar()
    var_fps    = tk.StringVar(value="200")

    # ---- Layout ----
    pad = {"padx": 8, "pady": 4}

    frame_inputs = ttk.Frame(root, padding=10)
    frame_inputs.grid(row=0, column=0, sticky="ew")
    root.columnconfigure(0, weight=1)

    def add_row(parent, row, label, var, browse_cmd):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", **pad)
        entry = ttk.Entry(parent, textvariable=var, width=55)
        entry.grid(row=row, column=1, sticky="ew", **pad)
        ttk.Button(parent, text="Browse…", command=browse_cmd).grid(row=row, column=2, **pad)
        parent.columnconfigure(1, weight=1)
        return entry

    def browse_chunks():
        d = filedialog.askdirectory(title="Select chunks directory")
        if d:
            var_chunks.set(d)
            # auto-fill output path if empty
            if not var_output.get():
                parent = os.path.dirname(d)
                basename = os.path.basename(d).replace("_frames", "")
                var_output.set(os.path.join(parent, basename + ".mp4"))

    def browse_output():
        f = filedialog.asksaveasfilename(
            title="Save video as",
            filetypes=[("MP4 video", "*.mp4")],
            defaultextension=".mp4",
        )
        if f:
            var_output.set(f)

    add_row(frame_inputs, 0, "Chunks directory:", var_chunks, browse_chunks)
    add_row(frame_inputs, 1, "Output video:",     var_output, browse_output)

    ttk.Label(frame_inputs, text="Frame rate (Hz):").grid(row=2, column=0, sticky="w", **pad)
    ttk.Entry(frame_inputs, textvariable=var_fps, width=10).grid(row=2, column=1, sticky="w", **pad)

    # ---- Action buttons ----
    frame_buttons = ttk.Frame(root)
    frame_buttons.grid(row=1, column=0, pady=8)
    btn_run = ttk.Button(frame_buttons, text="Reconstruct", padding=(20, 6))
    btn_run.grid(row=0, column=0, padx=6)
    btn_batch = ttk.Button(frame_buttons, text="Batch folder…", padding=(20, 6))
    btn_batch.grid(row=0, column=1, padx=6)

    # ---- Log area ----
    frame_log = ttk.Frame(root, padding=(10, 0, 10, 10))
    frame_log.grid(row=2, column=0, sticky="nsew")
    root.rowconfigure(2, weight=1)
    frame_log.columnconfigure(0, weight=1)
    frame_log.rowconfigure(0, weight=1)

    log_text = tk.Text(frame_log, height=16, state="disabled", wrap="word",
                       font=("Consolas", 9))
    scrollbar = ttk.Scrollbar(frame_log, command=log_text.yview)
    log_text.configure(yscrollcommand=scrollbar.set)
    log_text.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    # ---- Thread-safe logging via queue + root.after polling ----
    log_queue = queue.Queue()

    def _flush_log():
        while True:
            try:
                msg = log_queue.get_nowait()
            except queue.Empty:
                break
            log_text.configure(state="normal")
            log_text.insert("end", msg + "\n")
            log_text.see("end")
            log_text.configure(state="disabled")
        root.after(100, _flush_log)

    root.after(100, _flush_log)

    def gui_log(msg):
        log_queue.put(msg)

    # ---- Run reconstruction in background thread ----
    def on_run():
        chunks_dir = var_chunks.get().strip()
        output_path = var_output.get().strip()
        fps_str = var_fps.get().strip()

        if not chunks_dir:
            messagebox.showerror("Missing input", "Please select a chunks directory.")
            return
        if not output_path:
            messagebox.showerror("Missing input", "Please specify an output video path.")
            return
        try:
            fps = float(fps_str)
        except ValueError:
            messagebox.showerror("Invalid input", f"Frame rate must be a number, got: {fps_str!r}")
            return

        _set_buttons("disabled")
        gui_log(f"--- Starting reconstruction ---")
        gui_log(f"Chunks: {chunks_dir}")

        def worker():
            try:
                run_reconstruction(chunks_dir, output_path, fps, log_fn=gui_log)
                gui_log("--- Done ---")
            except Exception as exc:
                gui_log(f"ERROR: {exc}")
            finally:
                root.after(0, lambda: _set_buttons("normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _set_buttons(state):
        btn_run.configure(state=state)
        btn_batch.configure(state=state)

    # ---- Batch: reconstruct every '*_frames' folder under a chosen root ----
    def on_batch():
        fps_str = var_fps.get().strip()
        try:
            fps = float(fps_str)
        except ValueError:
            messagebox.showerror("Invalid input", f"Frame rate must be a number, got: {fps_str!r}")
            return

        root_dir = filedialog.askdirectory(title="Select root folder to batch-reconstruct")
        if not root_dir:
            return

        _set_buttons("disabled")
        gui_log(f"--- Starting batch reconstruction ---")
        gui_log(f"Root: {root_dir}")

        def worker():
            try:
                run_batch(root_dir, fps, log_fn=gui_log)
                gui_log("--- Batch done ---")
            except Exception as exc:
                gui_log(f"ERROR: {exc}")
            finally:
                root.after(0, lambda: _set_buttons("normal"))

        threading.Thread(target=worker, daemon=True).start()

    btn_run.configure(command=on_run)
    btn_batch.configure(command=on_batch)

    root.mainloop()


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        # Batch mode: python VideoReconstruct.py --batch <root_dir> [fps]
        if len(sys.argv) < 3:
            print("Usage: python VideoReconstruct.py --batch <root_dir> [fps]")
            sys.exit(1)
        root_dir = sys.argv[2]
        fps = float(sys.argv[3]) if len(sys.argv) > 3 else 200.0
        run_batch(root_dir, fps)
    elif len(sys.argv) > 1:
        # CLI mode
        if len(sys.argv) < 4:
            print("Usage: python VideoReconstruct.py <chunks_dir> <output_video_path> <fps> [output_dir]")
            print("   or: python VideoReconstruct.py --batch <root_dir> [fps]")
            sys.exit(1)
        chunks_dir        = sys.argv[1]
        output_video_path = sys.argv[2]
        fps               = float(sys.argv[3])
        output_dir        = sys.argv[4] if len(sys.argv) > 4 else None
        run_reconstruction(chunks_dir, output_video_path, fps, output_dir=output_dir)
    else:
        run_gui()
