# src/gui/fleet_gui.py
import tkinter as tk
from tkinter import simpledialog, messagebox
import os
from src.models.nav_graph import NavGraph
from src.controllers.fleet_manager import FleetManager
from src.controllers.traffic_manager import TrafficManager
from src.utils.helpers import log_action

class FleetGUI:
    def __init__(self, root, nav_graph, fleet_manager):
        self.root = root
        self.root.title("Fleet Management System")
        self.nav_graph = nav_graph
        self.fleet_manager = fleet_manager
        self.fleet_manager.gui = self

        # Left frame for canvas
        self.left_frame = tk.Frame(self.root)
        self.left_frame.pack(side=tk.LEFT, padx=10, pady=10)
        self.canvas_width = 1000
        self.canvas_height = 700
        self.canvas = tk.Canvas(self.left_frame, width=self.canvas_width, height=self.canvas_height, bg="white")
        self.canvas.pack()

        # Right frame for controls
        self.right_frame = tk.Frame(self.root)
        self.right_frame.pack(side=tk.RIGHT, padx=10, pady=10)

        # Control frame
        self.control_frame = tk.Frame(self.right_frame)
        self.control_frame.pack()
        self.graph_files = [f for f in os.listdir("data") if f.startswith("nav_graph_") and f.endswith(".json")]
        self.selected_graph = tk.StringVar(value=self.graph_files[0] if self.graph_files else "")
        tk.Label(self.control_frame, text="Select Graph:").pack()
        tk.OptionMenu(self.control_frame, self.selected_graph, *self.graph_files, command=self.load_nav_graph).pack(pady=5)
        
        self.start_button = tk.Button(self.control_frame, text="Start Simulation", command=self.start_simulation, bg="grey", fg="black", state="normal")
        self.start_button.pack(pady=5)
        self.stop_button = tk.Button(self.control_frame, text="Stop Simulation", command=self.stop_simulation, bg="green", fg="black", state="disabled")
        self.stop_button.pack(pady=5)
        self.pause_button = tk.Button(self.control_frame, text="Pause", command=self.toggle_pause, bg="yellow", fg="black")
        self.pause_button.pack(pady=5)
        
        self.graph_label = tk.Label(self.control_frame, text=f"Current Graph: {self.selected_graph.get()}")
        self.graph_label.pack(pady=10)

        # Log frame
        self.log_frame = tk.Frame(self.right_frame)
        self.log_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(self.log_frame, text="Logs:").pack()
        self.log_text = tk.Text(self.log_frame, height=20, width=50, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(self.log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # Dashboard frame
        self.dashboard_frame = tk.Frame(self.right_frame)
        self.dashboard_frame.pack(pady=10)
        self.num_robots_label = tk.Label(self.dashboard_frame, text="Number of robots: 0")
        self.num_robots_label.pack()
        self.num_idle_label = tk.Label(self.dashboard_frame, text="Idle: 0")
        self.num_idle_label.pack()
        self.num_moving_label = tk.Label(self.dashboard_frame, text="Moving: 0")
        self.num_moving_label.pack()
        self.num_waiting_label = tk.Label(self.dashboard_frame, text="Waiting: 0")
        self.num_waiting_label.pack()
        self.num_completed_label = tk.Label(self.dashboard_frame, text="Task complete: 0")
        self.num_completed_label.pack()

        self.running = False
        self.paused = False
        self.selected_robot = None
        self.nodes = {}
        self.lane_tags = {}
        
        # Initialize canvas binding and load graph after all widgets are created
        self.canvas.bind("<Button-1>", self.handle_click)
        # Move load_nav_graph after all GUI components are initialized
        if self.selected_graph.get():
            self.load_nav_graph(self.selected_graph.get())

    def load_nav_graph(self, graph_file):
        self.canvas.delete("all")
        if not graph_file:
            log_action(self, "No graph file selected")
            return
        try:
            self.nav_graph = NavGraph(os.path.join("data", graph_file))
            self.fleet_manager = FleetManager(self.nav_graph, TrafficManager(self.nav_graph, self))
            self.fleet_manager.gui = self
            log_action(self, f"Loaded {graph_file}")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        x_values = [x for x, y, _ in self.nav_graph.vertices]
        y_values = [y for x, y, _ in self.nav_graph.vertices]
        min_x, max_x = min(x_values, default=0), max(x_values, default=0)
        min_y, max_y = min(y_values, default=0), max(y_values, default=0)
        graph_width = max_x - min_x or 1
        graph_height = max_y - min_y or 1
        padding = 50
        scale = min((self.canvas_width - 2 * padding) / graph_width, (self.canvas_height - 2 * padding) / graph_height)
        x_offset = (self.canvas_width - graph_width * scale) / 2 - min_x * scale
        y_offset = (self.canvas_height - graph_height * scale) / 2 - min_y * scale

        self.nodes = {}
        self.lane_tags = {}
        for i, (x, y, _) in enumerate(self.nav_graph.vertices):
            cx, cy = self.convert_coordinates(x, y, x_offset, y_offset, scale)
            self.nodes[i] = (cx, cy)
            color = "red" if self.nav_graph.is_charger(i) else "blue"
            self.canvas.create_oval(cx-5, cy-5, cx+5, cy+5, fill=color, tags=f"vertex_{i}")
            self.canvas.create_text(cx, cy-15, text=self.nav_graph.get_vertex_name(i), font=("Arial", 10, "bold"))

        for start, end, _ in self.nav_graph.lanes:
            x1, y1 = self.nodes[start]
            x2, y2 = self.nodes[end]
            lane_tag = f"lane_{start}_{end}"
            self.lane_tags[tuple(sorted([start, end]))] = lane_tag
            self.canvas.create_line(x1, y1, x2, y2, fill="gray", tags=lane_tag)

        self.graph_label.config(text=f"Current Graph: {graph_file}")
        self.draw_robots()

    def convert_coordinates(self, x, y, x_offset, y_offset, scale):
        return int(x * scale + x_offset), int(y * scale + y_offset)

    def handle_click(self, event):
        x, y = event.x, event.y
        clicked_vertex = next((idx for idx, (vx, vy) in self.nodes.items() if abs(vx - x) < 15 and abs(vy - y) < 15), None)
        if clicked_vertex is not None:
            for robot in self.fleet_manager.robots:
                rx, ry = self.nodes[robot.pos_idx]
                if abs(rx - x) < 15 and abs(ry - y) < 15:
                    self.selected_robot = robot
                    log_action(self, f"Selected robot {robot.id}")
                    return
            if self.selected_robot is None:
                robot = self.fleet_manager.spawn_robot(clicked_vertex)
                if robot is None:
                    return
            else:
                if self.fleet_manager.assign_task(self.selected_robot, clicked_vertex):
                    if self.running:
                        self.update_simulation()
                self.selected_robot = None
            self.draw_robots()

    def draw_robots(self):
        self.canvas.delete("robot")
        self.canvas.delete("path")
        for robot in self.fleet_manager.robots:
            if robot.path:
                path_coords = []
                if robot.progress > 0 and robot.status == "moving":
                    x1, y1 = self.nodes[robot.pos_idx]
                    x2, y2 = self.nodes[robot.path[0]]
                    cx = x1 + (x2 - x1) * robot.progress
                    cy = y1 + (y2 - y1) * robot.progress
                    path_coords.append((cx, cy))
                    path_coords.append(self.nodes[robot.path[0]])
                    for i in range(1, len(robot.path)):
                        path_coords.append(self.nodes[robot.path[i]])
                else:
                    path_coords.append(self.nodes[robot.pos_idx])
                    for idx in robot.path:
                        path_coords.append(self.nodes[idx])
                if len(path_coords) > 1:
                    self.canvas.create_line([coord for point in path_coords for coord in point], fill=robot.color, width=1, dash=(2, 2), tags="path")

        for i in self.nodes:
            cx, cy = self.nodes[i]
            size = 10 if i in self.fleet_manager.traffic_manager.occupied_vertices else 5
            outline = "red" if i in self.fleet_manager.traffic_manager.occupied_vertices else "black"
            color = "red" if self.nav_graph.is_charger(i) else "blue"
            self.canvas.create_oval(cx-size, cy-size, cx+size, cy+size, fill=color, outline=outline, tags=f"vertex_{i}")
            self.canvas.create_text(cx, cy-15, text=self.nav_graph.get_vertex_name(i), font=("Arial", 10, "bold"))

        for lane in self.lane_tags:
            color = "red" if lane in self.fleet_manager.traffic_manager.occupied_lanes else "gray"
            self.canvas.itemconfig(self.lane_tags[lane], fill=color)

        for robot in self.fleet_manager.robots:
            if robot.status == "moving" and robot.progress > 0 and robot.path:
                current_idx = robot.pos_idx
                next_idx = robot.path[0]
                x1, y1 = self.nodes[current_idx]
                x2, y2 = self.nodes[next_idx]
                x = x1 + (x2 - x1) * robot.progress
                y = y1 + (y2 - y1) * robot.progress
            else:
                x, y = self.nodes[robot.pos_idx]
            
            status_color = {
                "idle": robot.color,
                "moving": "green",
                "waiting": "red",
                "task complete": "purple"
            }.get(robot.status, robot.color)
            self.canvas.create_oval(x-8, y-8, x+8, y+8, fill=status_color, tags="robot")
            self.canvas.create_text(x, y-25, text=f"{robot.id} (P:{robot.priority})", font=("Arial", 8), tags="robot")
            self.canvas.create_text(x, y+25, text=robot.status, font=("Arial", 8), tags="robot")

    def start_simulation(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.start_button.config(state="disabled", bg="grey")
            self.stop_button.config(state="normal", bg="red")
            self.pause_button.config(text="Pause", bg="yellow")
            self.update_simulation()
            log_action(self, "Simulation started")

    def stop_simulation(self):
        if self.running:
            self.running = False
            self.paused = False
            self.start_button.config(state="normal", bg="black")
            self.stop_button.config(state="disabled", bg="grey")
            self.pause_button.config(text="Pause", bg="yellow")
            log_action(self, "Simulation stopped")

    def toggle_pause(self):
        if self.running:
            self.paused = not self.paused
            self.pause_button.config(text="Resume" if self.paused else "Pause")
            log_action(self, "Simulation paused" if self.paused else "Simulation resumed")

    def update_simulation(self):
        if self.running and not self.paused:
            for robot in self.fleet_manager.robots:
                if robot.status == "moving" and robot.path:
                    robot.progress += 0.05
                    if robot.progress >= 1:
                        log_action(self, f"{robot.id} (P:{robot.priority}) moved to {robot.path[0]}")
            self.fleet_manager.traffic_manager.update_traffic(self.fleet_manager.robots)
            self.draw_robots()
            self.update_dashboard()
            self.root.after(100, self.update_simulation)

    def update_dashboard(self):
        num_robots = len(self.fleet_manager.robots)
        num_idle = sum(1 for r in self.fleet_manager.robots if r.status == "idle")
        num_moving = sum(1 for r in self.fleet_manager.robots if r.status == "moving")
        num_waiting = sum(1 for r in self.fleet_manager.robots if r.status == "waiting")
        num_completed = sum(1 for r in self.fleet_manager.robots if r.status == "task complete")
        self.num_robots_label.config(text=f"Number of robots: {num_robots}")
        self.num_idle_label.config(text=f"Idle: {num_idle}")
        self.num_moving_label.config(text=f"Moving: {num_moving}")
        self.num_waiting_label.config(text=f"Waiting: {num_waiting}")
        self.num_completed_label.config(text=f"Task complete: {num_completed}")

    def assign_to_highest(self):
        idle_robots = [r for r in self.fleet_manager.robots if r.status == "idle"]
        if not idle_robots:
            messagebox.showinfo("Info", "No idle robots available")
            return
        highest_priority_robot = max(idle_robots, key=lambda r: r.priority)
        goal_idx = simpledialog.askinteger("Goal Vertex", "Enter goal vertex index:", minvalue=0, maxvalue=len(self.nav_graph.vertices)-1)
        if goal_idx is not None:
            self.fleet_manager.assign_task(highest_priority_robot, goal_idx)
            self.draw_robots()