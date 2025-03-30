# src/utils/helpers.py
from datetime import datetime
from tkinter import messagebox

def log_action(gui, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    gui.log_text.insert(tk.END, log_message + "\n")
    gui.log_text.see(tk.END)
    with open("fleet_log.txt", "a") as f:
        f.write(log_message + "\n")

def notify_user(gui, message):
    messagebox.showwarning("Occupancy Alert", message)