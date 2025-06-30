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

# Define stimulus start and end times (hardcoded)
stimulus_start_time = 10  # seconds after the loop starts
stimulus_duration = 30  # in seconds (from MATLAB S.GUI.stimDur)
end_time = stimulus_start_time + stimulus_duration

# Flag to indicate whether data has already been collected during the stimulus period
data_collected = False

# Open the log file for appending data
with open(log_file_path, 'a') as log_file:
    log_file.write('Timestamp,VoltageRight,VoltageLeft\n')
    try:
        start_time = time.time()  # Capture the current time when the script starts
        while not os.path.exists('stop.txt'):
            current_time = time.time() - start_time  # Get the elapsed time since the script started
            
            # Check if current time is within stimulus period
            if stimulus_start_time <= current_time <= end_time:
                if not data_collected:
                    try:
                        line = ser.readline().decode().strip()
                        if ',' in line:  # Check if both values are present
                            data = line.split(',')
                            if len(data) == 2:
                                voltage_right = float(data[0].strip())
                                voltage_left = float(data[1].strip())
                                timestamp = time.strftime('%H:%M:%S')
                                log_file.write(f'{timestamp},{voltage_right},{voltage_left}\n')
                                log_file.flush()
                                print(f'{timestamp} - VoltageRight: {voltage_right}, VoltageLeft: {voltage_left}')  # Print statement added
                                # Mark that data has been collected for this stimulus period
                                data_collected = True
                            else:
                                print(f"Unexpected data format: {line}")
                        else:
                            print(f"Invalid data received: {line}")
                    except ValueError as e:
                        print(f"ValueError: Could not convert data to float: {e}")
                    except Exception as e:
                        print(f"Error reading data: {e}")

            # If stimulus period is over, reset the flag and update timing for the next stimulus period
            if current_time > end_time:
                data_collected = False  # Ready for the next stimulus period
                stimulus_start_time = current_time + 8  
                end_time = stimulus_start_time + stimulus_duration  # Set the new end time for the next stimulus period
                # Flush buffer to avoid stale data
                ser.reset_input_buffer()
    
    finally:
        ser.close()