import serial
import pandas as pd
from datetime import datetime

# Set up serial connection (replace 'COM3' with your Arduino's port)
ser = serial.Serial('COM6', 9600)
ser.flush()

# Data storage
data = []

# Path to the Excel file
file_path = 'C:\\Users\\TomBombadil\\Documents\\GitHub\\Treadwall\\Code\\Arduino\\Distance_Sensor\\TuningCurve\\sensor_data.xlsx'

# Start reading data
try:
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            values = line.split(",")
            if len(values) == 4:
                sensVoltageR = float(values[0])
                sensVoltageL = float(values[1])
                maxVoltageR = float(values[2])
                maxVoltageL = float(values[3])

                # Timestamp each entry
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Append data to list
                data.append([timestamp, sensVoltageR, sensVoltageL, maxVoltageR, maxVoltageL])
                
                # Save to Excel every 10 entries to avoid data loss
                if len(data) >= 10:
                    df = pd.DataFrame(data, columns=['Timestamp', 'sensVoltageR', 'sensVoltageL', 'maxVoltageR', 'maxVoltageL'])
                    df.to_excel(file_path, index=False)
                    data.clear()
except KeyboardInterrupt:
    # Final save on exit
    if data:
        df = pd.DataFrame(data, columns=['Timestamp', 'sensVoltageR', 'sensVoltageL', 'maxVoltageR', 'maxVoltageL'])
        df.to_excel(file_path, index=False)
    print("Data saved to Excel.")