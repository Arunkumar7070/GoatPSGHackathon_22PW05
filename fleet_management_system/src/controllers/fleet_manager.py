# src/controllers/fleet_manager.py
from tkinter import simpledialog
from src.utils.helpers import log_action, notify_user
from src.models.robot import Robot

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