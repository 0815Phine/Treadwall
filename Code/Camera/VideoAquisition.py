import pypylon.pylon as py
import cv2
import time
import os
import sys

# set output directory
session_folder = sys.argv[1]
animal_name = sys.argv[2]
session_name = sys.argv[3]

video_filename = f"{animal_name}_{session_name}.avi"
op_name = os.path.join(session_folder, video_filename)

# Create a stop flag file
STOP_FILE = os.path.join(session_folder, "stop_signal.txt") 
# Function to check if MATLAB requested a stop
def check_stop_signal():
    return os.path.exists(STOP_FILE)

# ------ set up camera ------
# get instance of the pylon TransportLayerFactory
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
cam.ExposureTime.Value = 4000
cam.ExposureAuto.Value = "Off"
cam.DeviceLinkThroughputLimitMode.Value = "Off"

# hardware trigger
cam.TriggerMode.Value = "On"  
cam.TriggerSource.Value = "Line1"  
cam.TriggerActivation.Value = "RisingEdge"
cam.TriggerSelector.Value = "FrameStart"

# ------ video aquisition ------
cam.StartGrabbing(py.GrabStrategy_OneByOne)

# set up video writer
fourcc = cv2.VideoWriter_fourcc(*'XVID')
video_writer = cv2.VideoWriter(op_name, fourcc, fps=200, frameSize=(1440, 1080), isColor=False)

# pipeline
fcount = 0
f_failed = 0
flag_status = False

print("Waiting for trigger...")
try:
    while not flag_status: # waiting for first trigger
        flag_status = cam.LineStatus.Value
        if flag_status: # if triggered: start pipeline
            print("Acquisition started...")
            stime = time.time()
            while cam.IsGrabbing():
                res = cam.RetrieveResult(1000)
                if res.GrabSucceeded():
                    fcount += 1
                    image = res.Array
                    video_writer.write(image)
                else:
                    f_failed += 1
                res.Release()

                # check for stop signal from MATLAB
                if check_stop_signal():
                    print("Stop signal received. Exiting...")
                    break
except KeyboardInterrupt:
    print("Acquisition stopped manually.")
        
# stop writing and cleanup
cam.StopGrabbing()
cam.Close()
video_writer.release()

if os.path.exists(STOP_FILE):
    os.remove(STOP_FILE)  # Cleanup stop file

etime = time.time()
elapsed_time = etime - stime
print(f"Acquisition stopped. Total frames: {fcount}, Failed frames: {f_failed}")
print(f"Elapsed time: {elapsed_time:.2f} seconds, Estimated FPS: {fcount / elapsed_time:.2f}")