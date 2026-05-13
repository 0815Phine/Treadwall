import pypylon.pylon as py
import cv2
import time
import os
import sys
import threading
import queue
import numpy as np
import shutil

# ------ Configuration ------
CHUNK_SIZE = 200        # frames per .npy chunk (200 frames = 1 s at 200 Hz)
H, W = 1080, 1440       # frame dimensions (must match camera settings below)
NVME_BASE = r"C:\Users\TomBombadil\Data"

# ------ Set up Output Directory ------
# get animal and session information
session_folder = sys.argv[1]
animal_name = sys.argv[2]
session_name = sys.argv[3]

# name new data folder and files
folder_name = f"{animal_name}_{session_name}_frames"
frames_folder = os.path.join(NVME_BASE, folder_name)
timestamp_filename = os.path.join(
    NVME_BASE,
    f"{animal_name}_{session_name}_video_timestamps.txt"
)

# prevent overwrite
if os.path.exists(frames_folder):
    print(f"WARNING: Frame folder '{frames_folder}' already exists.")
    user_input = input("Do you want to overwrite it? (y/n): ").strip().lower()
    if user_input == 'y':
        shutil.rmtree(frames_folder)
        if os.path.exists(timestamp_filename):
            os.remove(timestamp_filename)
    else:
        counter = 1
        while os.path.exists(frames_folder):
            frames_folder = os.path.join(
                NVME_BASE,
                f"{animal_name}_{session_name}_frames_{counter}"
            )
            timestamp_filename = os.path.join(
                NVME_BASE,
                f"{animal_name}_{session_name}_{counter}_video_timestamps.txt"
            )
            counter += 1
        print(f"Saving in new directory: {frames_folder}")

# create folder
os.makedirs(frames_folder)

# ------ Pre-allocate Double Buffer ------
# Writer reads slot N while acquisition fills slot N^1.
# Fill time at 200 Hz: 1000 ms. np.save time ≈ 256 ms → 744 ms safety margin.
chunk_buffers = [
    np.empty((CHUNK_SIZE, H, W), dtype=np.uint8),
    np.empty((CHUNK_SIZE, H, W), dtype=np.uint8),
]
ts_buffers = [
    np.empty(CHUNK_SIZE, dtype=np.int64),
    np.empty(CHUNK_SIZE, dtype=np.int64),
]
active_slot = 0
fill_idx = 0
chunk_counter = 0

# ------ Set up Camera ------
tlf = py.TlFactory.GetInstance()
devices = tlf.EnumerateDevices()
if not devices:
    raise RuntimeError("No cameras found!")

cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
cam.Open()

cam.Width.Value = W
cam.Height.Value = H
cam.ExposureTime.Value = 3500
cam.ExposureAuto.Value = "Off"
cam.Gain.Value = 12
cam.DeviceLinkThroughputLimitMode.Value = "Off"
cam.AcquisitionFrameRateEnable.Value = False
cam.AcquisitionMode.Value = "Continuous"

# hardware trigger
cam.TriggerMode.Value = "On"
cam.TriggerSource.Value = "Line1"
cam.TriggerActivation.Value = "RisingEdge"
cam.TriggerSelector.Value = "FrameStart"

# stop signal
cam.LineSelector.Value = "Line2"
cam.LineMode.Value = "Input"

# frame feedback
cam.LineSelector.Value = "Line3"
cam.LineMode.Value = "Output"
cam.LineSource.Value = "ExposureActive"

# ------ Live Stream ------
latest_display = None
display_lock = threading.Lock()

def live_stream():
    while cam.IsGrabbing():
        with display_lock:
            frame = latest_display
        if frame is not None:
            cv2.imshow("Live Stream", frame)
        cv2.waitKey(33)  # paces display to ~30 fps; also processes window events
    print("Closing live stream...")
    cv2.destroyAllWindows()

# ------ Writer Thread ------
write_queue = queue.Queue()  # unbounded — acquisition loop never blocks or drops

def writer_thread():
    while True:
        item = write_queue.get()
        if item is None:
            write_queue.task_done()
            break
        slot, n, chunk_idx = item
        try:
            np.save(
                os.path.join(frames_folder, f"chunk_{chunk_idx:06d}.npy"),
                chunk_buffers[slot][:n]
            )
            np.save(
                os.path.join(frames_folder, f"chunk_{chunk_idx:06d}_ts.npy"),
                ts_buffers[slot][:n]
            )
        except Exception as e:
            print(f"ERROR writing chunk {chunk_idx}: {e}")
        write_queue.task_done()

# ------ Video Acquisition ------
fcount = 0
f_failed = 0
trigger_lost = None
etime = None

cam.StartGrabbing(py.GrabStrategy_OneByOne)

live_thread = threading.Thread(target=live_stream, daemon=True)
live_thread.start()
wt = threading.Thread(target=writer_thread, daemon=False)
wt.start()

print("Waiting for trigger...")
# LineSelector is already pointing to Line3 (ExposureActive output).
# Wait until the first hardware trigger fires.
while not cam.LineStatus.Value:
    time.sleep(0.001)

cam.LineSelector.Value = "Line2"  # switch to monitor stop signal
print("Acquisition running...")
stime = time.perf_counter()

try:
    while cam.IsGrabbing():
        try:
            res = cam.RetrieveResult(1000, py.TimeoutHandling_ThrowException)
            if res.GrabSucceeded():
                image = res.Array

                # in-place copy into pre-allocated chunk buffer — no allocation per frame
                chunk_buffers[active_slot][fill_idx] = image
                ts_buffers[active_slot][fill_idx] = res.TimeStamp
                fill_idx += 1
                fcount += 1

                # resize outside the lock so display_lock hold time is minimal
                small = cv2.resize(image, (640, 480))
                with display_lock:
                    latest_display = small

                if fill_idx == CHUNK_SIZE:
                    write_queue.put((active_slot, CHUNK_SIZE, chunk_counter))
                    active_slot ^= 1
                    fill_idx = 0
                    chunk_counter += 1
            else:
                f_failed += 1

            res.Release()

            if cam.LineStatus.Value:
                etime = time.perf_counter()
                print("Stop signal received. Ending acquisition.")
                cam.AcquisitionStop.Execute()
                break

        except py.TimeoutException:
            print("Grab timeout. Checking for sustained trigger loss...")
            if not cam.LineStatus.Value:
                if trigger_lost is None:
                    etime = time.perf_counter()
                    trigger_lost = time.perf_counter()
                elif time.perf_counter() - trigger_lost > 0.01:
                    print("Trigger stopped. Ending acquisition...")
                    break
            else:
                trigger_lost = None

except KeyboardInterrupt:
    print("Acquisition interrupted by user.")
    etime = time.perf_counter()

if etime is None:
    etime = time.perf_counter()

# ------ Cleanup ------
cam.StopGrabbing()
cam.Close()

# flush partial last chunk
if fill_idx > 0:
    write_queue.put((active_slot, fill_idx, chunk_counter))
    chunk_counter += 1

write_queue.put(None)   # sentinel to shut down writer
write_queue.join()
wt.join()
live_thread.join(timeout=2.0)

elapsed_time = etime - stime
estimated_fps = fcount / elapsed_time if fcount > 0 and elapsed_time > 0 else 0.0

print(f"Acquisition stopped. Total frames: {fcount}, Failed frames: {f_failed}")
print(f"Elapsed time: {elapsed_time:.2f} seconds, Estimated FPS: {estimated_fps:.2f}")
print(f"Chunks written: {chunk_counter}")

# Build combined timestamps.txt (bare int64 ns per line — parseable by MATLAB load())
print("Saving timestamps...")
all_ts = []
for idx in range(chunk_counter):
    ts_path = os.path.join(frames_folder, f"chunk_{idx:06d}_ts.npy")
    all_ts.append(np.load(ts_path))

combined_ts = np.concatenate(all_ts) if all_ts else np.array([], dtype=np.int64)
with open(timestamp_filename, 'w') as f:
    for ts in combined_ts:
        f.write(f"{ts}\n")

print(f"Timestamps saved: {len(combined_ts)} entries → {timestamp_filename}")
