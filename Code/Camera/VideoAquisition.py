import pypylon.pylon as py
import cv2
import time
import os
import sys
import threading
import queue
import numpy as np
import shutil

# ------ Set up Output Directory ------
# writing fast disk path
NVME_base_path = r"C:\Users\TomBombadil\Data"

# get animal and session information
session_folder = sys.argv[1]
animal_name = sys.argv[2]
session_name = sys.argv[3]

# create output folder for frames
folder_name = f"{animal_name}_{session_name}_frames"
frames_folder = os.path.join(NVME_base_path, folder_name)

# create timestamp file
timestamp_filename = os.path.join(
    NVME_base_path,
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
    else: # generate new folder with appending number
        counter = 1
        while os.path.exists(frames_folder):
            frames_folder = os.path.join(
                NVME_base_path,
                f"{animal_name}_{session_name}_frames_{counter}"
            )
            timestamp_filename = os.path.join(
                NVME_base_path,
                f"{animal_name}_{session_name}_{counter}_vi_timestamps.txt"
            )
            counter += 1

        print(f"Saving in new directory: {frames_folder}")

# create folder
os.makedirs(frames_folder)

# ------ Set up Camera ------
tlf = py.TlFactory.GetInstance()
devices = tlf.EnumerateDevices() # list of pylon Device 
if not devices:
    raise RuntimeError("No cameras found!")

# choose camera
cam = py.InstantCamera(tlf.CreateDevice(devices[0]))
cam.Open()

# cam settings
cam.Width.Value = 1440
cam.Height.Value = 1080
cam.ExposureTime.Value = 3500
cam.ExposureAuto.Value = "Off"
cam.Gain.Value = 12
cam.DeviceLinkThroughputLimitMode.Value = "Off"
cam.AcquisitionFrameRateEnable.Value = False
cam.AcquisitionMode.Value = "Continuous"

# internal buffer

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
cam.LineSource.Value = "ExposureActive" #"FrameTriggerWait"

# ------ Live Stream ------
latest_frame = None
latest_frame_lock = threading.Lock()

def live_stream():
    """ Continuously display frames from the queue """

    while cam.IsGrabbing():
        frame = None

        with latest_frame_lock:
            if latest_frame is not None:
                frame = latest_frame.copy()

        if frame is not None:
            display_frame = cv2.resize(frame, (640, 480))
            cv2.imshow("Live Stream", display_frame)
            cv2.waitKey(1)

        time.sleep(1 / 30)

    print("Closing live stream...")
    cv2.destroyAllWindows()

# ------ Image-Writer ------
num_writers = 2
save_queue = queue.Queue(maxsize=1000)  # Larger buffer for writing

frame_counter = 0
frame_lock = threading.Lock()

timestamps = []
timestamp_lock = threading.Lock()

def writer_thread():
    """ Saves frames from the queue """

    global frame_counter

    while cam.IsGrabbing() or not save_queue.empty():
        try:
            frame, timestamp = save_queue.get(timeout=0.1)

            with frame_lock:
                frame_idx = frame_counter
                frame_counter += 1

            filename = os.path.join(
                frames_folder,
                f"frame_{frame_idx:06d}.bin"
            )
            frame.tofile(filename) # save as binary

            with timestamp_lock:
                timestamps.append((frame_idx, timestamp))

            save_queue.task_done()
        except queue.Empty:
            continue

# ------ Video Aquisition ------
fcount = 0
f_failed = 0
trigger_lost = None
trigger_started = False
trigger_stopped = False

# PIPELINE
cam.StartGrabbing(py.GrabStrategy_OneByOne)
live_thread = threading.Thread(target=live_stream, daemon=True)
live_thread.start()

writer_threads = []
for _ in range(num_writers):
    t = threading.Thread(target=writer_thread, daemon=True)
    t.start()
    writer_threads.append(t)

print("Waiting for trigger...")
while not cam.LineStatus.Value: # this most likely reads line 3
    pass

cam.LineSelector.Value = "Line2"
print("Acquisition running...")
stime = time.time()
trigger_started = True
while cam.IsGrabbing():
    try:
        res = cam.RetrieveResult(1000, py.TimeoutHandling_ThrowException)
        if res.GrabSucceeded():
            # get frame and timestamp
            image = res.Array
            timestamp = res.TimeStamp

            try:
                # save frame and timestamp
                save_queue.put_nowait((image.copy(), timestamp))
            except queue.Full:
                f_failed += 1
                print("Video queue full. Dropping frame.")
                
            # live stream
            with latest_frame_lock:
                latest_frame = image

            fcount += 1
        else:
            f_failed += 1
        res.Release()

        if cam.LineStatus.Value:
            etime = time.time()
            print("Stop signal received. Ending acquisition.")
            cam.AcquisitionStop.Execute()
            break

    except py.TimeoutException:
        print("Grab timeout. Checking for sustained trigger loss...")
        if not cam.LineStatus.Value:
            if trigger_lost is None: # first round
                etime = time.time()
                trigger_lost = time.time()
            elif time.time() - trigger_lost > 0.01: # second round
                print("Trigger stopped. Ending acquisition...")
                trigger_stopped = True
                break
        else: # not sure if this works properly
            trigger_lost = None  # Trigger is back, reset

# ------ Cleanup ------       
# release resources
cam.StopGrabbing()
cam.Close()
save_queue.join() # Wait for all frames to be written
for t in writer_threads:
    t.join() # Wait for writer thread to finish
live_thread.join()

# estimate fps
elapsed_time = etime - stime
if fcount > 0 and elapsed_time > 0:
    estimated_fps = fcount / elapsed_time
else:
    estimated_fps = 0.0  # No frames acquired, or very fast execution

print(f"Acquisition stopped. Total frames: {fcount}, Failed frames: {f_failed}")
print(f"Elapsed time: {elapsed_time:.2f} seconds, Estimated FPS: {estimated_fps :.2f}")
#print(f"Final video queue size before shutdown: {video_queue.qsize()}")
#print(f"Frames written to ffmpeg: {frame_write_count}")

# save timestamps of frames
print("Saving timestamps...")
with open(timestamp_filename, 'w') as f:
    for timestamp in timestamps:
        f.write(f"{timestamp}\n")