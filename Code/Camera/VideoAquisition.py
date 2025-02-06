import pypylon.pylon as py
import matplotlib.pyplot as plt
import numpy as np
import cv2

# get instance of the pylon TransportLayerFactory
tlf = py.TlFactory.GetInstance()

# list of pylon Device 
devices = tlf.EnumerateDevices()
# choose camera
device = devices[0]
cd = tlf.CreateDevice(device)
cam = py.InstantCamera(cd)
cam.Open()

# cam settings
cam.Width.Value = 1440
cam.Height.Value = 1080
cam.AcquisitionFrameRateEnable.Value = True
cam.AcquisitionFrameRate.Value = 200
cam.ExposureTime.Value = 4000
cam.DeviceLinkThroughputLimitMode.Value = "Off"

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