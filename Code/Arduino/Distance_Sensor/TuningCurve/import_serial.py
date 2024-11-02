# this was a test on synchronizing data from arduino and Bpod
# things to change to make this work:
# -> trigger measurement via bpod at every trial
# -> establich serial connection between bpod and arduino


import os
import time
import serial
import pandas as pd
from datetime import datetime

# Path to the Excel file
stop_file_path = 'C:\\Users\\TomBombadil\\Documents\\GitHub\\Treadwall\\Code\\Arduino\\Distance_Sensor\\TuningCurve\\stop.txt'
file_path = 'C:\\Users\\TomBombadil\\Documents\\GitHub\\Treadwall\\Code\\Arduino\\Distance_Sensor\\TuningCurve\\sensor_data.xlsx'

# Set up serial connection
ser = serial.Serial('COM6', 9600, timeout=1)
ser.flush()

# Data storage
data = []

# Start reading data
try:
    while True:
        # Check for data from Arduino
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            timestamp = datetime.now()
            try:
                distance_right, distance_left = map(float, line.split(','))
                data.append([timestamp, distance_right, distance_left])
                print(f"{timestamp} - Right: {distance_right} mm, Left: {distance_left} mm")
            except ValueError:
                print(f"Received malformed data: {line}")

        # Check for stop file to exit
        if os.path.exists(stop_file_path):
            print("Stop file detected. Exiting data logging.")
            break

        time.sleep(0.1)  # Small delay for efficient looping

finally:
    # Save data to Excel on exit
    if data:  # Ensure there is data to save
        df = pd.DataFrame(data, columns=['Timestamp', 'Distance_Right', 'Distance_Left'])
        df.to_excel(file_path, index=False)
        print(f"Data saved to {file_path}")
    else:
        print("No data collected.")
    ser.close()