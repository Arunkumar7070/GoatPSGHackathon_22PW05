import tkinter as tk
import json
import os
import heapq
import random
from datetime import datetime
from tkinter import simpledialog, messagebox

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

class NavGraph:
    def __init__(self, file_path):
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            self.levels = data.get("levels", {})
            if not self.levels:
                raise ValueError("No levels found in nav_graph")
            level_key = next(iter(self.levels), None)
            if not level_key:
                raise ValueError("No valid level key in nav_graph")
            level = self.levels[level_key]
            self.vertices = level.get("vertices", [])
            self.lanes = level.get("lanes", [])
            if not self.vertices or not self.lanes:
                raise ValueError("Vertices or lanes missing in nav_graph")
        except (json.JSONDecodeError, IOError, ValueError) as e:
            raise ValueError(f"Invalid nav_graph file {file_path}: {str(e)}")

    def get_vertex_coords(self, idx):
        if 0 <= idx < len(self.vertices):
            return self.vertices[idx][0], self.vertices[idx][1]
        return 0, 0

    def get_vertex_name(self, idx):
        if 0 <= idx < len(self.vertices) and len(self.vertices[idx]) > 2:
            return self.vertices[idx][2].get("name", f"V{idx}")
        return f"V{idx}"

    def is_charger(self, idx):
        if 0 <= idx < len(self.vertices) and len(self.vertices[idx]) > 2:
            return self.vertices[idx][2].get("is_charger", False)
        return False

class Robot:
    def __init__(self, id, pos_idx, color, priority):
        self.id = id
        self.pos_idx = pos_idx
        self.color = color
        self.priority = priority
        self.status = "idle"
        self.goal_idx = None
        self.path = []
        self.progress = 0
        self.previous_pos_idx = None

class TrafficManager:
    def __init__(self, nav_graph, gui):
        self.nav_graph = nav_graph
        self.gui = gui
        self.occupied_lanes = set()
        self.occupied_vertices = set()
        self.waiting_cooldown = {}

    def find_path(self, start_idx, goal_idx, avoid_vertex=None, avoid_lanes=None):
        if avoid_lanes is None:
            avoid_lanes = self.occupied_lanes

        def heuristic(idx1, idx2):
            x1, y1 = self.nav_graph.get_vertex_coords(idx1)
            x2, y2 = self.nav_graph.get_vertex_coords(idx2)
            return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

        open_set = [(0, start_idx, [start_idx])]
        heapq.heapify(open_set)
        g_score = {start_idx: 0}
        f_score = {start_idx: heuristic(start_idx, goal_idx)}
        came_from = {}

        while open_set:
            _, current, path = heapq.heappop(open_set)
            if current == goal_idx:
                log_action(self.gui, f"Path found from {start_idx} to {goal_idx}: {path[1:]}")
                return path[1:]

            for start, end, _ in self.nav_graph.lanes:
                if start == current:
                    neighbor = end
                elif end == current:
                    neighbor = start
                else:
                    continue

                if avoid_vertex == neighbor or neighbor in self.occupied_vertices:
                    continue

                lane = tuple(sorted([current, neighbor]))
                if lane in avoid_lanes:
                    continue

                tentative_g_score = g_score[current] + heuristic(current, neighbor)
                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal_idx)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor, path + [neighbor]))

        log_action(self.gui, f"No path found from {start_idx} to {goal_idx}")
        return []

    def update_traffic(self, robots):
        self.occupied_lanes.clear()
        self.occupied_vertices.clear()
        for robot in robots:
            if robot.status == "moving" and robot.path and robot.progress >= 1:
                next_idx = robot.path[0]
                lane = tuple(sorted([robot.pos_idx, next_idx]))
                self.occupied_lanes.add(lane)
                self.occupied_vertices.add(robot.pos_idx)
            elif robot.status in ["moving", "waiting"]:
                self.occupied_vertices.add(robot.pos_idx)

        sorted_robots = sorted(robots, key=lambda r: r.priority, reverse=True)
        for robot in sorted_robots:
            if robot.status == "moving" and robot.path:
                next_idx = robot.path[0]
                lane = tuple(sorted([robot.pos_idx, next_idx]))
                
                # Check for same-vertex conflict
                same_vertex_competitors = [
                    r for r in robots
                    if r != robot and r.pos_idx == robot.pos_idx and r.path and r.path[0] == next_idx
                ]
                if same_vertex_competitors:
                    highest_priority_competitor = max(same_vertex_competitors + [robot], key=lambda r: r.priority)
                    if robot != highest_priority_competitor:
                        robot.status = "waiting"
                        self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1
                        log_action(self.gui, f"{robot.id} (P:{robot.priority}) waiting at {robot.pos_idx} for {highest_priority_competitor.id} (P:{highest_priority_competitor.priority}) to move to {next_idx}")
                        continue

                blockers = [
                    r for r in robots
                    if r != robot and (
                        (r.status == "moving" and r.path and tuple(sorted([r.pos_idx, r.path[0] if r.path else r.pos_idx])) == lane)
                        or (r.pos_idx == next_idx and r.status in ["moving", "waiting"])
                    )
                ]

                if blockers and robot.progress >= 1:
                    highest_priority_blocker = max(blockers, key=lambda r: r.priority, default=None)
                    if highest_priority_blocker.priority > robot.priority:
                        alternative_path = self.find_path(robot.pos_idx, robot.goal_idx, avoid_vertex=next_idx)
                        if alternative_path and alternative_path[0] not in self.occupied_vertices:
                            robot.path = alternative_path
                            robot.progress = 0
                            robot.status = "moving"
                            log_action(self.gui, f"{robot.id} (P:{robot.priority}) rerouted to {robot.goal_idx} via {robot.path[0]}")
                            notify_user(self.gui, f"{robot.id} (P:{robot.priority}) took alternative path")
                        else:
                            robot.status = "waiting"
                            self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1
                            log_action(self.gui, f"{robot.id} (P:{robot.priority}) waiting at {robot.pos_idx} for {highest_priority_blocker.id} (P:{highest_priority_blocker.priority})")
                            notify_user(self.gui, f"{robot.id} (P:{robot.priority}) blocked by {highest_priority_blocker.id}")
                    elif highest_priority_blocker.priority < robot.priority:
                        for blocker in blockers:
                            if blocker.previous_pos_idx and blocker.previous_pos_idx not in self.occupied_vertices:
                                blocker.path = [blocker.previous_pos_idx] + self.find_path(blocker.previous_pos_idx, blocker.goal_idx)
                                blocker.pos_idx = blocker.previous_pos_idx
                                blocker.progress = 0
                                blocker.status = "moving"
                                log_action(self.gui, f"{blocker.id} (P:{blocker.priority}) backtracked to {blocker.pos_idx} for {robot.id} (P:{robot.priority})")
                                notify_user(self.gui, f"{blocker.id} backtracked for {robot.id}")
                            else:
                                blocker.status = "waiting"
                                self.waiting_cooldown[blocker.id] = self.waiting_cooldown.get(blocker.id, 0) + 1
                                log_action(self.gui, f"{blocker.id} (P:{blocker.priority}) waiting at {blocker.pos_idx}")
                    elif highest_priority_blocker.priority == robot.priority:
                        robot.status = "waiting"
                        self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1
                        log_action(self.gui, f"{robot.id} (P:{robot.priority}) waiting due to equal priority conflict with {highest_priority_blocker.id}")

                elif robot.progress >= 1:
                    robot.previous_pos_idx = robot.pos_idx
                    robot.pos_idx = robot.path.pop(0)
                    robot.progress = 0
                    if not robot.path:
                        robot.status = "task complete"
                        robot.goal_idx = None
                        log_action(self.gui, f"{robot.id} (P:{robot.priority}) completed task")
                    else:
                        new_path = self.find_path(robot.pos_idx, robot.goal_idx)
                        if new_path:
                            robot.path = new_path
                            log_action(self.gui, f"{robot.id} (P:{robot.priority}) moving to {robot.path[0]}")
                        else:
                            robot.status = "waiting"
                            self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1
                            log_action(self.gui, f"{robot.id} (P:{robot.priority}) waiting at {robot.pos_idx} (no path)")

            elif robot.status == "waiting" and robot.path:
                next_idx = robot.path[0]
                blockers = [
                    r for r in robots
                    if r != robot and (
                        (r.status == "moving" and r.path and tuple(sorted([r.pos_idx, r.path[0] if r.path else r.pos_idx])) == tuple(sorted([robot.pos_idx, next_idx])))
                        or (r.pos_idx == next_idx and r.status in ["moving", "waiting"])
                    )
                ]
                if not blockers or all(r.priority < robot.priority for r in blockers):
                    robot.status = "moving"
                    log_action(self.gui, f"{robot.id} (P:{robot.priority}) resumed moving to {next_idx}")
                    self.waiting_cooldown[robot.id] = 0

        # Enhanced random movement to break deadlocks
        for robot in robots:
            if robot.status == "waiting" and self.waiting_cooldown.get(robot.id, 0) >= 3:  # Reduced threshold
                adjacent_vertices = [
                    end for start, end, _ in self.nav_graph.lanes
                    if start == robot.pos_idx and end not in self.occupied_vertices
                ]
                if adjacent_vertices:
                    random_vertex = random.choice(adjacent_vertices)
                    robot.path = [random_vertex] + self.find_path(random_vertex, robot.goal_idx)
                    robot.pos_idx = random_vertex
                    robot.status = "moving"
                    robot.progress = 0
                    self.waiting_cooldown[robot.id] = 0
                    log_action(self.gui, f"{robot.id} (P:{robot.priority}) randomly moved to {random_vertex} to break deadlock")
                    notify_user(self.gui, f"{robot.id} moved randomly to {random_vertex} to resolve deadlock")

class FleetManager:
    def __init__(self, nav_graph, traffic_manager):
        self.nav_graph = nav_graph
        self.traffic_manager = traffic_manager
        self.gui = None
        self.robots = []
        self.robot_count = 0
        self.colors = ["orange", "purple", "green", "yellow", "cyan"]

    def spawn_robot(self, pos_idx):
        self.robot_count += 1
        priority = simpledialog.askinteger("Priority", f"Enter priority for R{self.robot_count} (1-10):", minvalue=1, maxvalue=10)
        if priority is None:
            priority = 1
        robot = Robot(f"R{self.robot_count}", pos_idx, self.colors[self.robot_count % len(self.colors)], priority)
        if pos_idx in self.traffic_manager.occupied_vertices:
            log_action(self.gui, f"Cannot spawn {robot.id} at vertex {pos_idx} (occupied)")
            notify_user(self.gui, f"Vertex {pos_idx} is occupied")
            return None
        self.robots.append(robot)
        log_action(self.gui, f"Spawned {robot.id} at vertex {pos_idx} with priority {robot.priority}")
        return robot

    def assign_task(self, robot, goal_idx):
        if robot.pos_idx == goal_idx:
            log_action(self.gui, f"{robot.id} is already at destination")
            return False
        robot.goal_idx = goal_idx
        robot.path = self.traffic_manager.find_path(robot.pos_idx, goal_idx)
        if robot.path:
            if goal_idx in self.traffic_manager.occupied_vertices:
                log_action(self.gui, f"{robot.id} (P:{robot.priority}) cannot move to {goal_idx} (occupied)")
                robot.path = []
                robot.status = "idle"
                return False
            robot.status = "moving"
            log_action(self.gui, f"Assigned {robot.id} (P:{robot.priority}) to vertex {goal_idx}")
            return True
        robot.status = "idle"
        log_action(self.gui, f"No path found for {robot.id} (P:{robot.priority}) to vertex {goal_idx}")
        return False

class FleetGUI:
    def __init__(self, root, nav_graph, fleet_manager):
        self.root = root
        self.root.title("Fleet Management System")
        self.nav_graph = nav_graph
        self.fleet_manager = fleet_manager
        self.fleet_manager.gui = self

        left_frame = tk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, padx=10, pady=10)
        self.canvas_width = 500
        self.canvas_height = 500
        self.canvas = tk.Canvas(left_frame, width=self.canvas_width, height=self.canvas_height, bg="white")
        self.canvas.pack()

        right_frame = tk.Frame(self.root)
        right_frame.pack(side=tk.RIGHT, padx=10, pady=10)

        control_frame = tk.Frame(right_frame)
        control_frame.pack()
        self.graph_files = [f for f in os.listdir("data") if f.startswith("nav_graph_") and f.endswith(".json")]
        self.selected_graph = tk.StringVar(value=self.graph_files[0] if self.graph_files else "")
        tk.Label(control_frame, text="Select Graph:").pack()
        tk.OptionMenu(control_frame, self.selected_graph, *self.graph_files, command=self.load_nav_graph).pack(pady=5)
        
        self.start_button = tk.Button(control_frame, text="Start Simulation", command=self.start_simulation, bg="grey", fg="black", state="normal")
        self.start_button.pack(pady=5)
        self.stop_button = tk.Button(control_frame, text="Stop Simulation", command=self.stop_simulation, bg="green", fg="black", state="disabled")
        self.stop_button.pack(pady=5)
        self.pause_button = tk.Button(control_frame, text="Pause", command=self.toggle_pause, bg="yellow", fg="black")
        self.pause_button.pack(pady=5)
        self.assign_highest_button = tk.Button(control_frame, text="Assign to Highest Priority Idle", command=self.assign_to_highest)
        self.assign_highest_button.pack(pady=5)
        
        self.graph_label = tk.Label(control_frame, text=f"Current Graph: {self.selected_graph.get()}")
        self.graph_label.pack(pady=10)

        log_frame = tk.Frame(right_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(log_frame, text="Logs:").pack()
        self.log_text = tk.Text(log_frame, height=20, width=50, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        dashboard_frame = tk.Frame(right_frame)
        dashboard_frame.pack(pady=10)
        self.num_robots_label = tk.Label(dashboard_frame, text="Number of robots: 0")
        self.num_robots_label.pack()
        self.num_idle_label = tk.Label(dashboard_frame, text="Idle: 0")
        self.num_idle_label.pack()
        self.num_moving_label = tk.Label(dashboard_frame, text="Moving: 0")
        self.num_moving_label.pack()
        self.num_waiting_label = tk.Label(dashboard_frame, text="Waiting: 0")
        self.num_waiting_label.pack()
        self.num_completed_label = tk.Label(dashboard_frame, text="Task complete: 0")
        self.num_completed_label.pack()

        self.running = False
        self.paused = False
        self.selected_robot = None
        self.nodes = {}
        self.lane_tags = {}
        self.load_nav_graph(self.selected_graph.get())
        self.canvas.bind("<Button-1>", self.handle_click)

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