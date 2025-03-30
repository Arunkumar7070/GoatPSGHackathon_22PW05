import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import os

def log_action(gui, message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_message = f"{timestamp} {message}"

    print(log_message)

    gui.log_text.insert(tk.END, log_message + "\n")
    gui.log_text.see(tk.END)

    log_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'fleet_logs.txt')
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    with open(log_file_path, 'a') as log_file:
        log_file.write(log_message + "\n")
def notify_user(gui, message):
    messagebox.showwarning("Occupancy Alert", message)