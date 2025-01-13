import serial
import time
import sys
import os

# Get file path from arguments
log_file_path = sys.argv[1]

# Initialize serial connection
arduino_port = 'COM6'  # Adjust as needed
baud_rate = 9600
ser = serial.Serial(arduino_port, baud_rate)
time.sleep(2)  # Allow time for connection

# Open the log file for appending data
with open(log_file_path, 'a') as log_file:
    log_file.write('Timestamp,VoltageRight,VoltageLeft\n')
    try:
        while not os.path.exists('stop.txt'):
            try:
                data = ser.readline().decode().strip().split(',')
                if len(data) == 2:
                    voltage_right = float(data[0])
                    voltage_left = float(data[1])
                    timestamp = time.strftime('%H:%M:%S')
                    log_file.write(f'{timestamp},{voltage_right},{voltage_left}\n')
                    log_file.flush()
            except Exception as e:
                print(f"Error reading data: {e}")
            time.sleep(0.05)  # Adjust the sampling rate if necessary
    finally:
        ser.close()