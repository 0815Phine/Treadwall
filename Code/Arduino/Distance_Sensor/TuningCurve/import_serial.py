# this was a test on synchronizing data from arduino and Bpod
# things to change to make this work:
# -> trigger measurement via bpod at every trial
# -> establich serial connection between bpod and arduino

# Update 4.11.2024:
# -> trigger measurement every 15 seconds (to ensure measurement at every trial created with bpod)


import os
import time
import serial
import pandas as pd
from datetime import datetime

# Path to the Excel file
stop_file_path = 'C:\\Users\\TomBombadil\\Documents\\GitHub\\Treadwall\\Code\\Arduino\\Distance_Sensor\\TuningCurve\\stop.txt'
output_file_path = 'C:\\Users\\TomBombadil\\Documents\\GitHub\\Treadwall\\Code\\Arduino\\Distance_Sensor\\TuningCurve\\sensor_data.xlsx'

# Set up serial connection
ser = serial.Serial('COM6', 9600, timeout=1)
ser.flush()

# Data storage
data = []
initial_delay = 20
interval = 28  # Interval between measurements in seconds
single_value_mode = False  # Flag to detect if only one measurement value is received

# Start reading data
try:
    print("Starting data collection...")

    # Initial delay before the first measurement
    print(f"Waiting for {initial_delay} seconds before the first measurement...")
    time.sleep(initial_delay)

    while True:
        start_time = time.time()
        received_data = False  # Reset flag for each interval

        # Flush buffer to avoid stale data
        ser.reset_input_buffer()

        # Try to read data within the current interval
        while not received_data and (time.time() - start_time) < interval:
            if ser.in_waiting > 0:  # Check if data is available
                line = ser.readline().decode('utf-8').strip()
                print(f"Raw data received: {line}")  # Debug: Print every line received
                timestamp = datetime.now()

                # Parse data (assumes "distance_right, distance_left" format)
                try:
                    values = line.split(',')
                    if len(values) == 2:
                        distance_right, distance_left = map(float, line.split(','))
                        data.append([timestamp, distance_right, distance_left])
                        print(f"{timestamp} - Right: {distance_right} mV, Left: {distance_left} mV")
                    elif len(values) == 1:
                        # Single sensor value received
                        sensor_value = float(values[0])
                        data.append([timestamp, sensor_value])
                        print(f"{timestamp} - Sensor Value: {sensor_value} mV")
                        single_value_mode = True
                    else:
                        print(f"Unexpected data format: {line}")
                    received_data = True
                except ValueError:
                    print(f"Received unexpected data: {line}")
            
            # Check for stop file to exit the loop
            if os.path.exists(stop_file_path):
                print("Stop file detected. Exiting data logging.")
                break

            time.sleep(0.1)  # Small delay to avoid excessive CPU usage

        # If no data was received within the interval, log `NaN`
        if not received_data:
            print(f"No data received in this interval.")
            if single_value_mode:
                data.append([datetime.now(), float('nan')])
            else:
                data.append([datetime.now(), float('nan'), float('nan')])

        # Check again for stop file after each interval
        if os.path.exists(stop_file_path):
            print("Stop file detected. Exiting data logging.")
            break

        # Wait for the remainder of the interval, if necessary
        elapsed_time = time.time() - start_time
        remaining_time = max(0, interval - elapsed_time)
        time.sleep(remaining_time)

finally:
    # Save data to Excel once collection is complete
    if single_value_mode:
        df = pd.DataFrame(data, columns=['Timestamp', 'Sensor_Value'])
    else:
        df = pd.DataFrame(data, columns=['Timestamp', 'Distance_Right', 'Distance_Left'])
    df.to_excel(output_file_path, index=False)
    ser.close()
    print("Data saved to Excel and serial connection closed.")