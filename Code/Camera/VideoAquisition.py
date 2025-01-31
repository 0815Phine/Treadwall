# these four imports will provide most of the functionality required in 
# to start working with basler cameras
# pypylon 
import pypylon.pylon as py
# plotting for graphs and display of image
import matplotlib.pyplot as plt
# linear algebra and basic math on image matrices
import numpy as np
# OpenCV for image processing functions
#import cv2
# get instance of the pylon TransportLayerFactory
tlf = py.TlFactory.GetInstance()
# all pypylon objects are instances of SWIG wrappers around the underlying pylon c++ types
tlf

devices = tlf.EnumerateDevices()
# list of pylon Device 
devices
