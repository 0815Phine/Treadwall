import pypylon.pylon as py
import matplotlib.pyplot as plt
import numpy as np
import cv2
import time

# get instance of the pylon TransportLayerFactory
tlf = py.TlFactory.GetInstance()

# list of pylon Device 
devices = tlf.EnumerateDevices()
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

# video aquisition
cam.StartGrabbing(py.GrabStrategy_OneByOne)

# set output directory
op_name = 'output.avi'

# set up video writer
fourcc = cv2.VideoWriter_fourcc(*'XVID')
video_writer = cv2.VideoWriter(op_name, fourcc, fps=200, frameSize=(1440, 1080), isColor=False)

# 
fcount = 0
f_failed = 0
flag_status = False

while not flag_status: # while line status is false check line status again (waiting for first trigger)
    flag_status = cam.LineStatus.Value
    if flag_status: # if true: run pipeline
        stime = time.time()
        while cam.IsGrabbing():
            res = cam.RetrieveResult(1000)
            if res.GrabSucceeded():
                fcount += 1
                image = cv2.cvtColor(res.Array, cv2.COLOR_GRAY2BGR)
                video_writer.write(image)
            else:
                f_failed += 1
            res.Release()
        
        # to include: mechanism of stopping pipeline
        cam.StopGrabbing()
        cam.Close()
        video_writer.release()
        break

fcount
f_failed
# to include: time after stopping (to check for correct framerate)