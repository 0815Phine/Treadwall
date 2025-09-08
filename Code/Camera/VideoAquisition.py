import pypylon.pylon as py
import cv2
import time
import os
import sys
import threading
import queue
import subprocess
import numpy as np
import shutil

# ------ Set up Output Directory ------
# get animal and session information
session_folder = sys.argv[1]
animal_name = sys.argv[2]
session_name = sys.argv[3]

# create timestamp and video file
video_filename = f"{animal_name}_{session_name}.mp4"
timestamp_filename = os.path.join(session_folder, f"{animal_name}_{session_name}_video_timestamps.txt")
op_name = os.path.join(session_folder, video_filename)
# prevent overwriting an existing video file
if os.path.exists(op_name):
    print(f"WARNING: Video file '{video_filename}' already exists.")
    user_input = input("Do you want to overwrite it? (y/n): ").strip().lower()
    if user_input != 'y':
        # Generate a new filename by appending a number
        counter = 1
        while os.path.exists(op_name):
            new_video_filename = f"{animal_name}_{session_name}_{counter}.mp4"
            timestamp_filename = os.path.join(session_folder, f"{animal_name}_{session_name}_{counter}_vi_timestamps.txt")
            op_name = os.path.join(session_folder, new_video_filename)
            counter += 1
        print(f"Saving as new file: {new_video_filename}")

# create a stop flag file
#STOP_FILE = os.path.join(session_folder, "stop_signal.txt")
# remove existing stop file at startup
#if os.path.exists(STOP_FILE):
#    os.remove(STOP_FILE)
#    print("Existing stop file found and removed.")

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
cam.ExposureTime.Value = 3500 #check lowest possible exposure time with animal!!
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
cam.LineSource.Value = "ExposureActive" #"FrameTriggerWait"

# ------ Live Stream ------
frame_queue = queue.Queue(maxsize=10)
#stop_event = threading.Event() 
def live_stream():
    """ Continuously display frames from the queue """
    while cam.IsGrabbing() or not frame_queue.empty():
        if not frame_queue.empty():
            frame = frame_queue.get()

            if frame is None or frame.size == 0:
                continue  # Skip empty frames

            # Resize the frame for display
            display_frame = cv2.resize(frame, (960, 720))

            cv2.imshow("Live Stream", display_frame)
            cv2.waitKey(1)
        
        time.sleep(1 / 30) # live streaming fps = 30

        #if cv2.waitKey(1) & 0xFF == ord('q'):
        #    print("Live stream stopped by user.")
        #    stop_event.set()
        #    break
    print("Closing live stream...")
    cv2.destroyAllWindows()

# ------ Video-Writer ------
# set up OpenCV
#fourcc = cv2.VideoWriter_fourcc(*'XVID')
#video_writer = cv2.VideoWriter(op_name, fourcc, fps=200, frameSize=(1440, 1080), isColor=False)

# set up ffmpeg
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path is None:
    raise RuntimeError("FFmpeg was not found. Make sure it's in your system PATH.")
ffmpeg_cmd = [
    ffmpeg_path,  # use absolute path found by shutil
    '-y',
    '-f', 'rawvideo',
    '-vcodec', 'rawvideo',
    '-pix_fmt', 'gray',
    '-s', '1440x1080',
    '-r', '200',
    '-i', '-',

    '-vcodec', 'h264_nvenc',
    '-gpu', '0',
    '-profile:v', 'high',
    '-preset', 'slow',
    '-crf', '17',
    '-an',
    '-vf', 'format=gray',
    '-pix_fmt', 'yuv420p',
    '-r', '200',
    '-f', 'mp4',
    op_name]
ffmpeg_process = subprocess.Popen(
    ffmpeg_cmd,
    stdin=subprocess.PIPE,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL)

frame_write_count = 0
video_queue = queue.Queue(maxsize=100)  # Larger buffer for writing
def video_writer_thread():
    """ Writes frames from the queue """
    global frame_write_count
    while cam.IsGrabbing() or not video_queue.empty():
        try:
            frame = video_queue.get(timeout=0.1)
            ffmpeg_process.stdin.write(frame.tobytes())
            frame_write_count += 1
            video_queue.task_done()
        except queue.Empty:
            continue

# ------ Video Aquisition ------
fcount = 0
f_failed = 0
timestamps = []
trigger_lost = None
trigger_started = False
trigger_stopped = False

# PIPELINE
cam.StartGrabbing(py.GrabStrategy_OneByOne)
live_thread = threading.Thread(target=live_stream, daemon=True)
live_thread.start()
writer_thread = threading.Thread(target=video_writer_thread, daemon=True)
writer_thread.start()

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
            image = res.Array

            # video writer
            #ffmpeg_process.stdin.write(image.tobytes())
            try:
                video_queue.put_nowait(image)
            except queue.Full:
                print("Video queue full. Dropping frame.")
                
            # timestamps
            timestamp = res.TimeStamp #time.time() #cam.TimestampLatch.Execute()
            timestamps.append(timestamp)
                
            # live stream
            if not frame_queue.full():
                frame_queue.put(image)

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
                #stop_event.set()
                break
        else: # not sure if this works properly
            trigger_lost = None  # Trigger is back, reset
    
    # check for stop signal from MATLAB
    #if os.path.exists(STOP_FILE):
    #    etime = time.time()
    #    print("Stop signal received. Exiting...")
    #    stop_event.set()
    #    break

# ------ Cleanup ------       
# release resources
cam.StopGrabbing()
cam.Close()
video_queue.join()       # Wait for all frames to be written
writer_thread.join()     # Wait for writer thread to finish
live_thread.join()
ffmpeg_process.stdin.close()
ffmpeg_process.wait()

# remove stop file
#f os.path.exists(STOP_FILE):
#    os.remove(STOP_FILE)

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