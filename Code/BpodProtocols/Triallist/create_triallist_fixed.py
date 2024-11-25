import os
import csv
from tkinter import Tk, filedialog
import random

# Initialize tkinter
root = Tk()
root.withdraw()  #Hide the main tkinter window

# Define the start path
start_path = os.path.join('Z:','Animals')
# Prompt the user to select a cohort directory
start_path = filedialog.askdirectory(initialdir=start_path, title='Select Cohort')

# Prompt the user for animal ID and session ID
animal_id = input("Enter the animal ID: ")
session_id = input("Enter the session ID: ")
# Path for the animal directory and session subdirectory
animal_dir = os.path.join(start_path, animal_id)
session_dir = os.path.join(animal_dir, session_id)

# Ensure the directories exist
os.makedirs(session_dir, exist_ok=True)
# Path for the output file
output_path = os.path.join(session_dir, 'triallist.csv')

# Create a list with the characters 'C' = centre, 'R' = right, 'L' = left
entries = ['C'] * 8 + ['R'] * 8 + ['L'] * 8
# Shuffle the list to randomize the order
random.shuffle(entries)
#print(entries)

# Save the list to a CSV file
with open(output_path, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['type'])  #Header line
    for entry in entries:
        writer.writerow([entry])
print(f"List saved to {output_path}")