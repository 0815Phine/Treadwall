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
fourcc = cv2.VideoWriter_fourcc(*'XVID')
video_writer = cv2.VideoWriter('output.avi', fourcc, fps=200, frameSize=(1440, 1080))

cam.StartGrabbingMax(400)

while cam.IsGrabbing():
    res = cam.RetrieveResult(1000)
    image = cv2.cvtColor(res.Array, cv2.COLOR_GRAY2BGR)
    video_writer.write(image)
    res.Release()
cam.Close()
video_writer.release()