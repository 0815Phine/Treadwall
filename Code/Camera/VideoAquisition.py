import pypylon.pylon as py
import cv2
import time
import os
import sys
import threading
import queue

# ------ Set up Output Directory ------
# get animal and session information
session_folder = sys.argv[1]
animal_name = sys.argv[2]
session_name = sys.argv[3]

# create video file
video_filename = f"{animal_name}_{session_name}.avi"
op_name = os.path.join(session_folder, video_filename)
# prevent overwriting an existing video file
if os.path.exists(op_name):
    print(f"WARNING: Video file '{video_filename}' already exists.")
    user_input = input("Do you want to overwrite it? (y/n): ").strip().lower()
    if user_input != 'y':
        # Generate a new filename by appending a number
        counter = 1
        while os.path.exists(op_name):
            new_video_filename = f"{animal_name}_{session_name}_{counter}.avi"
            op_name = os.path.join(session_folder, new_video_filename)
            counter += 1
        print(f"Saving as new file: {new_video_filename}")

# create a stop flag file
STOP_FILE = os.path.join(session_folder, "stop_signal.txt")
# remove existing stop file at startup
if os.path.exists(STOP_FILE):
    os.remove(STOP_FILE)
    print("Existing stop file found and removed.")

# ------ Set up Camera ------
tlf = py.TlFactory.GetInstance()
# list of pylon Device 
devices = tlf.EnumerateDevices()
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
cam.DeviceLinkThroughputLimitMode.Value = "Off"

# hardware trigger
cam.TriggerMode.Value = "On"  
cam.TriggerSource.Value = "Line1"  
cam.TriggerActivation.Value = "RisingEdge"
cam.TriggerSelector.Value = "FrameStart"

# ------ Live Stream ------
frame_queue = queue.Queue(maxsize=10)
stop_event = threading.Event() 
def live_stream():
    """ Continuously display frames from the queue """
    while not stop_event.is_set() or not frame_queue.empty():
        if not frame_queue.empty():
            frame = frame_queue.get()
            cv2.imshow("Live Stream", frame)
        
        time.sleep(1 / 30) # live streaming fps = 30
        # Ensure OpenCV refreshes window
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Live stream stopped by user.")
            stop_event.set()
            break
    print("Closing live stream...")
    cv2.destroyAllWindows()

thread = threading.Thread(target=live_stream, daemon=True)
thread.start()

# ------ Video Aquisition ------
cam.StartGrabbing(py.GrabStrategy_OneByOne)

# set up video writer
fourcc = cv2.VideoWriter_fourcc(*'XVID')
video_writer = cv2.VideoWriter(op_name, fourcc, fps=200, frameSize=(1440, 1080), isColor=False)

# pipeline
fcount = 0
f_failed = 0
trigger_lost = False
timestamps = [] 

print("Waiting for trigger...")
while not cam.LineStatus.Value: # waiting for first trigger
    pass

print("Acquisition started...")
stime = time.time()
while cam.IsGrabbing():
    try:
        res = cam.RetrieveResult(1000, py.TimeoutHandling_ThrowException)
        if res.GrabSucceeded():
            fcount += 1
            image = res.Array
            video_writer.write(image)

            timestamp = time.time()
            timestamps.append(timestamp)

            if not frame_queue.full():
                frame_queue.put(image)
        else:
            f_failed += 1
        res.Release()
    except py.TimeoutException:
        etime = time.time()
        print("WARNING: Camera stopped grabbing unexpectedly! Ensure trigger is functioning correctly.")
        trigger_lost = True
        stop_event.set()
        break

    # check for stop signal from MATLAB
    if os.path.exists(STOP_FILE):
        etime = time.time()
        print("Stop signal received. Exiting...")
        stop_event.set()
        break

# ------ Cleanup ------       
# release resources
cam.StopGrabbing()
cam.Close()
video_writer.release()
thread.join()

# remove stop file
if os.path.exists(STOP_FILE):
    os.remove(STOP_FILE)

# estimate fps
elapsed_time = etime - stime
if fcount > 0 and elapsed_time > 0:
    estimated_fps = fcount / elapsed_time
else:
    estimated_fps = 0.0  # No frames acquired, or very fast execution

if trigger_lost:
    print(f"Total frames: {fcount}, Failed frames: {f_failed}")
    print(f"Elapsed time: {elapsed_time:.2f} seconds, Estimated FPS: {estimated_fps :.2f}")
else:
    print(f"Acquisition stopped. Total frames: {fcount}, Failed frames: {f_failed}")
    print(f"Elapsed time: {elapsed_time:.2f} seconds, Estimated FPS: {estimated_fps :.2f}")

# save timestamps of frames
timestamp_filename = os.path.join(session_folder, f"{animal_name}_{session_name}_video_timestamps.txt")
with open(timestamp_filename, 'w') as f:
    for timestamp in timestamps:
        f.write(f"{timestamp}\n")