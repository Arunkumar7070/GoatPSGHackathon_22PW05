from tkinter import simpledialog
from src.utils.helpers import log_action, notify_user
from src.models.robot import Robot

class FleetManager:
    def __init__(self, nav_graph, traffic_manager):
        """
        Initialize the FleetManager with a navigation graph and traffic manager.
        """
        self.nav_graph = nav_graph
        self.traffic_manager = traffic_manager
        self.gui = None  # GUI reference (optional)
        self.robots = []  # List to store robot instances
        self.robot_count = 0  # Counter for unique robot IDs
        self.colors = ["orange", "purple", "green", "yellow", "cyan"]  # Predefined colors for robots

    def spawn_robot(self, pos_idx):
        """
        Spawns a new robot at the given position index if it's not occupied.
        """
        self.robot_count += 1
        
        # Ask the user for the robot's priority (default is 1 if canceled)
        priority = simpledialog.askinteger("Priority", f"Enter priority for R{self.robot_count} (1-10):", minvalue=1, maxvalue=10)
        if priority is None:
            priority = 1
        
        # Create a new robot instance
        robot = Robot(f"R{self.robot_count}", pos_idx, self.colors[self.robot_count % len(self.colors)], priority)
        
        # Check if the position is already occupied
        if pos_idx in self.traffic_manager.occupied_vertices:
            log_action(self.gui, f"Cannot spawn {robot.id} at vertex {pos_idx} (occupied)")
            notify_user(self.gui, f"Vertex {pos_idx} is occupied")
            return None
        
        # Add the robot to the fleet
        self.robots.append(robot)
        log_action(self.gui, f"Spawned {robot.id} at vertex {pos_idx} with priority {robot.priority}")
        return robot

    def assign_task(self, robot, goal_idx):
        """
        Assigns a robot a task to move to the specified goal index.
        """
        # If the robot is already at the destination, do nothing
        if robot.pos_idx == goal_idx:
            log_action(self.gui, f"{robot.id} is already at destination")
            return False
        
        # Set the goal and calculate a path using the traffic manager
        robot.goal_idx = goal_idx
        robot.path = self.traffic_manager.find_path(robot.pos_idx, goal_idx)
        
        if robot.path:
            # If the goal position is occupied, cancel the move
            if goal_idx in self.traffic_manager.occupied_vertices:
                log_action(self.gui, f"{robot.id} (P:{robot.priority}) cannot move to {goal_idx} (occupied)")
                robot.path = []  # Clear path since movement is not possible
                robot.status = "idle"
                return False
            
            # Set the robot status to moving and confirm task assignment
            robot.status = "moving"
            log_action(self.gui, f"Assigned {robot.id} (P:{robot.priority}) to vertex {goal_idx}")
            return True
        
        # No valid path found, robot remains idle
        robot.status = "idle"
        log_action(self.gui, f"No path found for {robot.id} (P:{robot.priority}) to vertex {goal_idx}")
        return False
