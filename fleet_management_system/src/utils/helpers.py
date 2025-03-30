import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import os

def log_action(gui, message):
    """
    Logs an action message with a timestamp.
    
    - Displays the log message in the GUI.
    - Prints it to the console.
    - Saves it to a log file.

    :param gui: Reference to the GUI application where logs are displayed.
    :param message: The message to log.
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")  # Generate current timestamp
    log_message = f"{timestamp} {message}"  # Format the log entry

    print(log_message)  # Print log to console (useful for debugging)

    # Append the log message to the GUI text widget
    gui.log_text.insert(tk.END, log_message + "\n")
    gui.log_text.see(tk.END)  # Auto-scroll to the latest log entry

    # Define the log file path (located three directories up inside 'logs' folder)
    log_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'fleet_logs.txt')

    # Ensure the logs directory exists before writing the file
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Open the log file in append mode and write the log entry
    with open(log_file_path, 'a') as log_file:
        log_file.write(log_message + "\n")

def notify_user(gui, message):
    """
    Displays a warning message to the user via a popup alert.
    
    :param gui: Reference to the GUI application.
    :param message: The message to be displayed in the warning alert.
    """
    messagebox.showwarning("Occupancy Alert", message)  # Show a warning popup
