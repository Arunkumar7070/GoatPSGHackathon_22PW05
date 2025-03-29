import tkinter as tk
from src.gui.fleet_gui import FleetGUI

def main():
    # Create the Tkinter root window
    root = tk.Tk()
    
    # Initialize and run the GUI
    app = FleetGUI(root)
    
    # Start the Tkinter event loop
    root.mainloop()

if __name__ == "__main__":
    main()