import pypylon.pylon as py
import cv2
import time
import os
import sys
import threading
import queue
import json
import numpy as np
import shutil

# ------ Configuration ------
CHUNK_SIZE = 200        # frames per .npy chunk (200 frames = 1 s at 200 Hz)
H, W = 540, 720         # frame dimensions after 2×2 binning (must match camera settings below)
NVME_BASE = r"C:\Users\TomBombadil\Documents\Data"

# Fill in Basler serial numbers before first use.
# Run the script with no cameras configured to print detected serials.
SERIAL_TOPCAM   = "40486089"   # e.g. "12345678"
SERIAL_FRONTCAM = "40442087"   # e.g. "87654321"

# ------ Set up Output Directory ------
session_folder = sys.argv[1]   # full LTS path, e.g. D:\Animals\Cohort01_Training\OPI2714\S1_B1
animal_name = sys.argv[2]
session_name = sys.argv[3]

# Mirror the cohort/animal/session hierarchy on the NVMe fast disc
cohort_name = os.path.basename(os.path.dirname(os.path.dirname(session_folder)))
nvme_session_path = os.path.join(NVME_BASE, cohort_name, animal_name, session_name)
os.makedirs(nvme_session_path, exist_ok=True)

folder_top   = os.path.join(nvme_session_path, f"{animal_name}_{session_name}_topcam_frames")
folder_front = os.path.join(nvme_session_path, f"{animal_name}_{session_name}_frontcam_frames")
ts_file_top   = os.path.join(nvme_session_path, f"{animal_name}_{session_name}_topcam_video_timestamps.txt")
ts_file_front = os.path.join(nvme_session_path, f"{animal_name}_{session_name}_frontcam_video_timestamps.txt")

for folder in (folder_top, folder_front):
    if os.path.exists(folder):
        print(f"WARNING: Frame folder '{folder}' already exists.")
        user_input = input("Do you want to overwrite it? (y/n): ").strip().lower()
        if user_input == 'y':
            shutil.rmtree(folder)
        else:
            print("Aborting. Remove or rename existing frame folders before starting.")
            sys.exit(1)
    os.makedirs(folder)

# ------ Camera Discovery ------
tlf = py.TlFactory.GetInstance()
devices = tlf.EnumerateDevices()
if not devices:
    raise RuntimeError("No cameras found!")

detected_serials = [d.GetSerialNumber() for d in devices]
print(f"Detected cameras: {detected_serials}")

if not SERIAL_TOPCAM or not SERIAL_FRONTCAM:
    print("\nERROR: SERIAL_TOPCAM and SERIAL_FRONTCAM must be set at the top of this script.")
    print("Detected serials:")
    for serial in detected_serials:
        print(f"  {serial}")
    sys.exit(1)

def _open_camera(serial):
    for dev in devices:
        if dev.GetSerialNumber() == serial:
            cam = py.InstantCamera(tlf.CreateDevice(dev))
            cam.Open()
            return cam
    raise RuntimeError(f"Camera with serial '{serial}' not found. Detected: {detected_serials}")

cam_top   = _open_camera(SERIAL_TOPCAM)
cam_front = _open_camera(SERIAL_FRONTCAM)

# ------ Top Camera Settings (hardware-triggered, 200 Hz) ------
cam_top.BinningHorizontal.Value     = 2
cam_top.BinningVertical.Value       = 2
cam_top.BinningHorizontalMode.Value = "Average"
cam_top.BinningVerticalMode.Value   = "Average"
cam_top.Width.Value  = W
cam_top.Height.Value = H
cam_top.PixelFormat.Value = "Mono8"          # explicit — Pylon Viewer can leave Mono12
cam_top.ExposureTime.Value = 3500
cam_top.ExposureAuto.Value = "Off"
cam_top.Gain.Value = 12
cam_top.DeviceLinkThroughputLimitMode.Value = "Off"
cam_top.AcquisitionFrameRateEnable.Value = False
cam_top.AcquisitionMode.Value = "Continuous"

# TriggerSelector must be set BEFORE TriggerMode/Source — it selects which trigger to configure
cam_top.TriggerSelector.Value   = "FrameStart"
cam_top.TriggerMode.Value       = "On"
cam_top.TriggerSource.Value     = "Line1"
cam_top.TriggerActivation.Value = "RisingEdge"

cam_top.LineSelector.Value = "Line2"
cam_top.LineMode.Value     = "Input"

cam_top.LineSelector.Value = "Line3"
cam_top.LineMode.Value     = "Output"
cam_top.LineSource.Value   = "ExposureActive"

# ------ Front Camera Settings (free-running) ------
# With 2×2 binning, bandwidth per camera is ~78 MB/s (200 Hz × 720×540).
# Total for both cameras: ~156 MB/s — well within USB 3.0 limits on a shared controller.
FRONTCAM_FPS = 200.0

cam_front.BinningHorizontal.Value     = 2
cam_front.BinningVertical.Value       = 2
cam_front.BinningHorizontalMode.Value = "Average"
cam_front.BinningVerticalMode.Value   = "Average"
cam_front.Width.Value  = W
cam_front.Height.Value = H
cam_front.PixelFormat.Value = "Mono8"
cam_front.ExposureTime.Value = 4900
cam_front.ExposureAuto.Value = "Off"
cam_front.Gain.Value = 10
cam_front.AcquisitionMode.Value = "Continuous"
cam_front.AcquisitionFrameRateEnable.Value = True
cam_front.AcquisitionFrameRate.Value = FRONTCAM_FPS
cam_front.TriggerMode.Value = "Off"  # free-running

# ------ Pre-allocate Double Buffers ------
# Each slot holds one full chunk. Writer reads the completed slot while
# acquisition fills the other. Fill time (1 s) >> np.save time (~256 ms).

def _make_buffers():
    return (
        [np.empty((CHUNK_SIZE, H, W), dtype=np.uint8),
         np.empty((CHUNK_SIZE, H, W), dtype=np.uint8)],
        [np.empty(CHUNK_SIZE, dtype=np.int64),
         np.empty(CHUNK_SIZE, dtype=np.int64)],
        [np.empty(CHUNK_SIZE, dtype=np.int64),
         np.empty(CHUNK_SIZE, dtype=np.int64)],
    )

chunk_top,   cam_ts_top,   pc_ts_top   = _make_buffers()
chunk_front, cam_ts_front, pc_ts_front = _make_buffers()

# ------ Shared Events ------
stop_event  = threading.Event()  # set by topcam when Line2 fires or trigger lost
start_event = threading.Event()  # set when topcam receives its first hardware trigger

# ------ Live Stream State ------
latest_top   = None
latest_front = None
display_lock = threading.Lock()
_DIVIDER     = np.zeros((480, 4), dtype=np.uint8)  # 4-pixel separator between views

# ------ Writer Threads ------
write_queue_top   = queue.Queue()
write_queue_front = queue.Queue()


def _writer(write_queue, frame_buffers, cam_ts_buffers, pc_ts_buffers, folder):
    while True:
        item = write_queue.get()
        if item is None:
            write_queue.task_done()
            break
        slot, n, chunk_idx = item
        try:
            np.save(os.path.join(folder, f"chunk_{chunk_idx:06d}.npy"),
                    frame_buffers[slot][:n])
            np.save(os.path.join(folder, f"chunk_{chunk_idx:06d}_cam_ts.npy"),
                    cam_ts_buffers[slot][:n])
            np.save(os.path.join(folder, f"chunk_{chunk_idx:06d}_pc_ts.npy"),
                    pc_ts_buffers[slot][:n])
        except Exception as e:
            print(f"ERROR writing chunk {chunk_idx} to {folder}: {e}")
        write_queue.task_done()


# ------ Acquisition Threads ------
fcount_top   = 0
fcount_front = 0
f_failed_top   = 0
f_failed_front = 0
etime_top = None


def acquire_topcam():
    global fcount_top, f_failed_top, etime_top, latest_top

    slot    = 0
    fill    = 0
    counter = 0
    trigger_lost = None
    stime = None

    cam_top.StartGrabbing(py.GrabStrategy_OneByOne)

    try:
        print("Topcam: waiting for first trigger...")
        # LineSelector is pointing to Line3 (ExposureActive output).
        # Wait until the first hardware trigger fires.
        while not cam_top.LineStatus.Value:
            time.sleep(0.001)

        start_event.set()
        cam_top.LineSelector.Value = "Line2"  # switch to monitor stop signal
        print("Topcam: acquisition running...")
        stime = time.perf_counter()

        try:
            while cam_top.IsGrabbing():
                try:
                    res = cam_top.RetrieveResult(1000, py.TimeoutHandling_ThrowException)
                    if res.GrabSucceeded():
                        image = res.Array
                        chunk_top[slot][fill]  = image
                        cam_ts_top[slot][fill] = res.TimeStamp
                        pc_ts_top[slot][fill]  = time.perf_counter_ns()
                        fill += 1
                        fcount_top += 1

                        with display_lock:
                            latest_top = cv2.resize(image, (640, 480))

                        if fill == CHUNK_SIZE:
                            write_queue_top.put((slot, CHUNK_SIZE, counter))
                            slot ^= 1
                            fill  = 0
                            counter += 1
                    else:
                        f_failed_top += 1
                        if f_failed_top <= 3:
                            print(f"  Topcam grab failed: code={res.ErrorCode}, {res.ErrorDescription}")

                    res.Release()

                    if cam_top.LineStatus.Value:
                        etime_top = time.perf_counter()
                        print("Topcam: stop signal received (Line2 HIGH).")
                        stop_event.set()
                        break

                except py.TimeoutException:
                    print("Topcam: grab timeout.")
                    if not cam_top.LineStatus.Value:
                        if trigger_lost is None:
                            etime_top = time.perf_counter()
                            trigger_lost = time.perf_counter()
                        elif time.perf_counter() - trigger_lost > 0.01:
                            print("Topcam: trigger lost. Ending acquisition.")
                            stop_event.set()
                            break
                    else:
                        trigger_lost = None

        except KeyboardInterrupt:
            print("Topcam: interrupted by user.")
            etime_top = time.perf_counter()
            stop_event.set()

    finally:
        if etime_top is None:
            etime_top = time.perf_counter()

        try:
            cam_top.StopGrabbing()
            cam_top.Close()
        except Exception as e:
            print(f"Topcam cleanup error: {e}")

        if fill > 0:
            write_queue_top.put((slot, fill, counter))
            counter += 1

        write_queue_top.put(None)

    elapsed = etime_top - (stime or etime_top)
    fps = fcount_top / elapsed if fcount_top > 0 and elapsed > 0 else 0.0
    print(f"Topcam: {fcount_top} frames, {f_failed_top} failed, {elapsed:.2f}s, {fps:.2f} fps")

    return counter, fps


def acquire_frontcam():
    global fcount_front, f_failed_front, latest_front

    slot    = 0
    fill    = 0
    counter = 0
    stime   = None

    cam_front.StartGrabbing(py.GrabStrategy_OneByOne)

    try:
        # Wait for topcam to receive its first trigger before capturing
        while not start_event.is_set():
            if stop_event.is_set():
                return 0, 0.0
            time.sleep(0.01)

        print("Frontcam: acquisition running...")
        stime = time.perf_counter()

        while not stop_event.is_set():
            try:
                res = cam_front.RetrieveResult(100, py.TimeoutHandling_Return)
                if res.IsValid():
                    if res.GrabSucceeded():
                        image = res.Array
                        chunk_front[slot][fill]   = image
                        cam_ts_front[slot][fill]  = res.TimeStamp
                        pc_ts_front[slot][fill]   = time.perf_counter_ns()
                        fill += 1
                        fcount_front += 1

                        with display_lock:
                            latest_front = cv2.resize(image, (640, 480))

                        if fill == CHUNK_SIZE:
                            write_queue_front.put((slot, CHUNK_SIZE, counter))
                            slot ^= 1
                            fill  = 0
                            counter += 1
                    else:
                        f_failed_front += 1
                    res.Release()

            except Exception as e:
                print(f"Frontcam: error during grab: {e}")

    finally:
        etime = time.perf_counter()

        try:
            cam_front.StopGrabbing()
            cam_front.Close()
        except Exception as e:
            print(f"Frontcam cleanup error: {e}")

        if fill > 0:
            write_queue_front.put((slot, fill, counter))
            counter += 1

        write_queue_front.put(None)

    elapsed = etime - (stime or etime)
    fps = fcount_front / elapsed if fcount_front > 0 and elapsed > 0 else 0.0
    print(f"Frontcam: {fcount_front} frames, {f_failed_front} failed, {elapsed:.2f}s, {fps:.2f} fps")

    return counter, fps


# ------ Thread Result Holders ------
top_results   = [0, 0.0]
front_results = [0, 0.0]


def _run_topcam():
    try:
        top_results[0], top_results[1] = acquire_topcam()
    except Exception:
        import traceback
        print(f"FATAL ERROR in topcam thread:\n{traceback.format_exc()}")
        stop_event.set()


def _run_frontcam():
    try:
        front_results[0], front_results[1] = acquire_frontcam()
    except Exception:
        import traceback
        print(f"FATAL ERROR in frontcam thread:\n{traceback.format_exc()}")
        stop_event.set()


# ------ Start All Threads ------
wt_top   = threading.Thread(target=_writer,
                            args=(write_queue_top, chunk_top, cam_ts_top, pc_ts_top, folder_top),
                            daemon=False)
wt_front = threading.Thread(target=_writer,
                            args=(write_queue_front, chunk_front, cam_ts_front, pc_ts_front, folder_front),
                            daemon=False)

acq_top_thread   = threading.Thread(target=_run_topcam,   daemon=False)
acq_front_thread = threading.Thread(target=_run_frontcam, daemon=False)

wt_top.start()
wt_front.start()
acq_top_thread.start()
acq_front_thread.start()

# Main thread runs the live display.
# cv2.imshow must be called from the main thread on Windows — never from a secondary thread.
while acq_top_thread.is_alive() or acq_front_thread.is_alive():
    with display_lock:
        top_frame   = latest_top
        front_frame = latest_front

    if top_frame is not None and front_frame is not None:
        combined = np.hstack([top_frame, _DIVIDER, front_frame])
    elif top_frame is not None:
        combined = top_frame
    elif front_frame is not None:
        combined = front_frame
    else:
        combined = None

    if combined is not None:
        cv2.imshow("Live Stream  [top | front]", combined)
    cv2.waitKey(33)

cv2.destroyAllWindows()

# Acquisition threads are done; wait for pending writes to flush
acq_top_thread.join()
acq_front_thread.join()
write_queue_top.join()
write_queue_front.join()
wt_top.join()
wt_front.join()

counter_top,   fps_top   = top_results
counter_front, fps_front = front_results


# ------ Save Timestamps ------
def _save_timestamps(folder, ts_file, n_chunks):
    all_ts = []
    for idx in range(n_chunks):
        p = os.path.join(folder, f"chunk_{idx:06d}_cam_ts.npy")
        all_ts.append(np.load(p))
    combined = np.concatenate(all_ts) if all_ts else np.array([], dtype=np.int64)
    with open(ts_file, 'w') as f:
        for ts in combined:
            f.write(f"{ts}\n")
    print(f"Timestamps saved: {len(combined)} entries → {ts_file}")


print("Saving timestamps...")
_save_timestamps(folder_top,   ts_file_top,   counter_top)
_save_timestamps(folder_front, ts_file_front, counter_front)


# ------ Save Session Metadata ------
metadata = {
    "animal":          animal_name,
    "session":         session_name,
    "cohort":          cohort_name,
    "session_dir_lts": session_folder,
    "topcam": {
        "serial":        SERIAL_TOPCAM,
        "total_frames":  fcount_top,
        "fps_estimated": round(fps_top, 2),
    },
    "frontcam": {
        "serial":        SERIAL_FRONTCAM,
        "total_frames":  fcount_front,
        "fps_estimated": round(fps_front, 2),
    },
}
meta_path = os.path.join(nvme_session_path, "session_metadata.json")
with open(meta_path, 'w') as f:
    json.dump(metadata, f, indent=2)
print(f"Metadata saved → {meta_path}")
