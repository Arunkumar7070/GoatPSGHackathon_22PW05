import tkinter as tk
import json
import os
import random

class FleetGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fleet Management System")

        # Canvas for drawing the map
        self.canvas_width = 500
        self.canvas_height = 700
        self.canvas = tk.Canvas(self.root, width=self.canvas_width, height=self.canvas_height, bg="white")
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)

        # Control panel
        control_frame = tk.Frame(self.root)
        control_frame.pack(side=tk.RIGHT, padx=10, pady=10)

        # Dropdown for selecting nav graph file
        self.graph_files = self.get_graph_files()
        if not self.graph_files:
            print("No navigation graph files found in 'data' directory.")
            return

        self.selected_graph = tk.StringVar(value=self.graph_files[0])
        tk.Label(control_frame, text="Select Graph:").pack()
        graph_menu = tk.OptionMenu(control_frame, self.selected_graph, *self.graph_files, command=self.load_nav_graph)
        graph_menu.pack(pady=5)

        # Start, Stop, and Assign Task buttons
        tk.Button(control_frame, text="Start Simulation", command=self.start_simulation).pack(pady=5)
        tk.Button(control_frame, text="Stop Simulation", command=self.stop_simulation).pack(pady=5)

        # Label to display the selected graph
        self.graph_label = tk.Label(control_frame, text=f"Current Graph: {self.selected_graph.get()}")
        self.graph_label.pack(pady=10)

        # Robot management
        self.robots = []
        self.robot_count = 0
        self.robot_colors = ["orange", "purple", "green", "yellow", "cyan"]
        self.running = False
        self.selected_robot = None  # For task assignment

        # Load default graph and bind clicks
        self.nodes = {}
        self.lanes = []  # Store lanes for pathfinding
        self.load_nav_graph(self.graph_files[0])
        self.canvas.bind("<Button-1>", self.handle_click)

    def get_graph_files(self):
        return [f for f in os.listdir("data") if f.startswith("nav_graph_") and f.endswith(".json")]

    def load_nav_graph(self, graph_file):
        self.canvas.delete("all")
        self.robots.clear()

        try:
            with open(f"data/{graph_file}") as f:
                data = json.load(f)

            self.nodes.clear()
            self.lanes = []

            level_key = next(iter(data["levels"]), None)
            if not level_key:
                raise KeyError("No valid level keys found in JSON file.")

            level = data["levels"].get(level_key)
            if "vertices" not in level or "lanes" not in level:
                raise KeyError("Missing 'vertices' or 'lanes' key in the selected JSON file.")

            vertices = level["vertices"]
            self.lanes = level["lanes"]

            # Calculate bounds
            x_values = [x for x, y, info in vertices]
            y_values = [y for x, y, info in vertices]
            min_x, max_x = min(x_values, default=0), max(x_values, default=0)
            min_y, max_y = min(y_values, default=0), max(y_values, default=0)
            graph_width = max_x - min_x or 1
            graph_height = max_y - min_y or 1

            # Scaling and centering
            padding = 50
            scale = min((self.canvas_width - 2 * padding) / graph_width, (self.canvas_height - 2 * padding) / graph_height)
            x_offset = (self.canvas_width - graph_width * scale) / 2 - min_x * scale
            y_offset = (self.canvas_height - graph_height * scale) / 2 - min_y * scale

            # Count intersections
            lane_count = {}
            for start, end, _ in self.lanes:
                lane_count[start] = lane_count.get(start, 0) + 1
                lane_count[end] = lane_count.get(end, 0) + 1

            # Draw nodes
            for i, (x, y, info) in enumerate(vertices):
                cx, cy = self.convert_coordinates(x, y, x_offset, y_offset, scale)
                self.nodes[i] = (cx, cy)
                color = "red" if info.get("is_charger") else "blue"
                size = 10 if lane_count.get(i, 0) > 2 else 5  # Larger for intersections
                self.canvas.create_oval(cx-size, cy-size, cx+size, cy+size, fill=color, tags=f"vertex_{i}")
                self.canvas.create_text(cx, cy-15, text=info["name"], font=("Arial", 10, "bold"), fill="black")

            # Draw lanes
            for start, end, _ in self.lanes:
                if start in self.nodes and end in self.nodes:
                    x1, y1 = self.nodes[start]
                    x2, y2 = self.nodes[end]
                    self.canvas.create_line(x1, y1, x2, y2, fill="gray")

            self.graph_label.config(text=f"Current Graph: {graph_file}")
            self.draw_robots()

        except Exception as e:
            print("Error loading nav graph:", e)

    def convert_coordinates(self, x, y, x_offset, y_offset, scale):
        return int(x * scale + x_offset), int(y * scale + y_offset)

    def handle_click(self, event):
        x, y = event.x, event.y
        clicked_vertex = None
        for idx, (vx, vy) in self.nodes.items():
            if abs(vx - x) < 15 and abs(vy - y) < 15:
                clicked_vertex = idx
                break

        if clicked_vertex is not None:
            # Check if clicking a robot
            for robot in self.robots:
                rx, ry = self.nodes[robot["pos_idx"]]
                if abs(rx - x) < 15 and abs(ry - y) < 15:
                    self.selected_robot = robot
                    print(f"Selected robot {robot['id']}")
                    return
            
            # If no robot selected, spawn one; if selected, assign task
            if self.selected_robot is None:
                self.spawn_robot(clicked_vertex)
            else:
                self.assign_task(self.selected_robot, clicked_vertex)
                self.selected_robot = None

    def spawn_robot(self, vertex_idx):
        self.robot_count += 1
        robot_id = f"R{self.robot_count}"
        color = self.robot_colors[self.robot_count % len(self.robot_colors)]
        robot = {
            "id": robot_id,
            "pos_idx": vertex_idx,
            "color": color,
            "status": "idle",
            "goal_idx": None,
            "path": [],
            "progress": 0
        }
        self.robots.append(robot)
        self.draw_robots()
        print(f"Spawned {robot_id} at vertex {vertex_idx}")

    def assign_task(self, robot, goal_idx):
        if robot["pos_idx"] == goal_idx:
            print(f"{robot['id']} is already at destination")
            return
        robot["goal_idx"] = goal_idx
        robot["path"] = self.simple_path(robot["pos_idx"], goal_idx)  # Basic pathfinding
        if robot["path"]:
            robot["status"] = "moving"
            print(f"Assigned {robot['id']} to go to vertex {goal_idx}")
        else:
            robot["status"] = "idle"
            print(f"No path found for {robot['id']} to vertex {goal_idx}")
        self.draw_robots()

    def simple_path(self, start_idx, goal_idx):
        """Simple BFS pathfinding (placeholder)."""
        visited = set()
        queue = [(start_idx, [start_idx])]
        while queue:
            current, path = queue.pop(0)
            if current == goal_idx:
                return path[1:]  # Exclude start
            if current not in visited:
                visited.add(current)
                for start, end, _ in self.lanes:
                    next_idx = end if start == current else (start if end == current else None)
                    if next_idx and next_idx not in visited:
                        queue.append((next_idx, path + [next_idx]))
        return []

    def draw_robots(self):
        self.canvas.delete("robot")
        for robot in self.robots:
            if robot["status"] == "moving" and robot["progress"] > 0 and robot["path"]:
                # Interpolate position along lane
                current_idx = robot["pos_idx"]
                next_idx = robot["path"][0]
                x1, y1 = self.nodes[current_idx]
                x2, y2 = self.nodes[next_idx]
                x = x1 + (x2 - x1) * robot["progress"]
                y = y1 + (y2 - y1) * robot["progress"]
            else:
                x, y = self.nodes[robot["pos_idx"]]
            
            status_color = {
                "idle": robot["color"],
                "moving": "green",
                "waiting": "red",
                "charging": "yellow",
                "task complete": "purple"
            }.get(robot["status"], robot["color"])
            self.canvas.create_oval(x-8, y-8, x+8, y+8, fill=status_color, tags="robot")
            self.canvas.create_text(x, y-15, text=robot["id"], font=("Arial", 8), tags="robot")
            self.canvas.create_text(x, y+15, text=robot["status"], font=("Arial", 8), tags="robot")

    def start_simulation(self):
        if not self.running:
            self.running = True
            self.update_simulation()
            print("Simulation started")

    def stop_simulation(self):
        self.running = False
        print("Simulation stopped")

    def update_simulation(self):
        if self.running:
            for robot in self.robots:
                if robot["status"] == "moving" and robot["path"]:
                    robot["progress"] += 0.05  # Slower movement for visibility
                    if robot["progress"] >= 1:
                        robot["pos_idx"] = robot["path"].pop(0)
                        robot["progress"] = 0
                        if not robot["path"]:
                            robot["status"] = "task complete"
                            robot["goal_idx"] = None
            self.draw_robots()
            self.root.after(100, self.update_simulation)
