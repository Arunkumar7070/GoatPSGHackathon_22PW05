# main.py
import tkinter as tk
from tkinter import messagebox
import os
from src.models.nav_graph import NavGraph
from src.controllers.traffic_manager import TrafficManager
from src.controllers.fleet_manager import FleetManager
from src.gui.fleet_gui import FleetGUI
from src.utils.helpers import log_action

def main():
    root = tk.Tk()
    try:
        nav_graph = NavGraph(os.path.join("data", "nav_graph_1.json"))
    except ValueError as e:
        messagebox.showerror("Error", str(e))
        root.destroy()
        return
    traffic_manager = TrafficManager(nav_graph, None)
    fleet_manager = FleetManager(nav_graph, traffic_manager)
    gui = FleetGUI(root, nav_graph, fleet_manager)
    traffic_manager.gui = gui
    log_action(gui, "System initialized")
    root.mainloop()

if __name__ == "__main__":
    main()