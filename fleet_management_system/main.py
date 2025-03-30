# main.py - Entry point for the Fleet Management System

import tkinter as tk
from tkinter import messagebox
import os

# Importing necessary modules for navigation, traffic, fleet, GUI, and logging
from src.models.nav_graph import NavGraph
from src.controllers.traffic_manager import TrafficManager
from src.controllers.fleet_manager import FleetManager
from src.gui.fleet_gui import FleetGUI
from src.utils.helpers import log_action

def main():
    """
    Initializes the Fleet Management System:
    - Loads the navigation graph.
    - Sets up traffic and fleet managers.
    - Initializes the GUI.
    - Logs system initialization.
    """
    root = tk.Tk()  # Create the main GUI window

    try:
        # Load the navigation graph from a JSON file
        nav_graph = NavGraph(os.path.join("data", "nav_graph_1.json"))
    
    except ValueError as e:
        # Show an error popup if the navigation graph fails to load
        messagebox.showerror("Error", str(e))
        root.destroy()  # Close the GUI window
        return  # Exit the function to prevent further execution

    # Initialize traffic and fleet managers
    traffic_manager = TrafficManager(nav_graph, None)
    fleet_manager = FleetManager(nav_graph, traffic_manager)

    # Initialize the GUI and connect it to the fleet manager
    gui = FleetGUI(root, nav_graph, fleet_manager)

    # Pass the GUI reference to the traffic manager for interaction
    traffic_manager.gui = gui

    # Log that the system has been successfully initialized
    log_action(gui, "System initialized")

    # Start the GUI event loop
    root.mainloop()

# Run the main function when the script is executed
if __name__ == "__main__":
    main()
