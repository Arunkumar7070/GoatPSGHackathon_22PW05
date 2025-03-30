import random
import heapq
from src.utils.helpers import log_action, notify_user
from tkinter import messagebox


class TrafficManager:
    def __init__(self, nav_graph, gui):
        self.nav_graph = nav_graph  # Stores the navigation graph for robot movement
        self.gui = gui  # GUI for logging actions
        self.occupied_lanes = set()  # Tracks lanes currently occupied by robots
        self.occupied_vertices = set()  # Tracks vertices currently occupied by robots
        self.waiting_cooldown = {}  # Stores cooldown timers for waiting robots

    def find_path(self, start_idx, goal_idx, avoid_vertex=None, avoid_lanes=None):
        if avoid_lanes is None:
            avoid_lanes = self.occupied_lanes

        # Heuristic function for A* (Euclidean distance)
        def heuristic(idx1, idx2):
            x1, y1 = self.nav_graph.get_vertex_coords(idx1)
            x2, y2 = self.nav_graph.get_vertex_coords(idx2)
            return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

        # Priority queue for A*
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
                # Identify neighbors
                if start == current:
                    neighbor = end
                elif end == current:
                    neighbor = start
                else:
                    continue

                # Avoid conflicts
                if avoid_vertex == neighbor or neighbor in self.occupied_vertices:
                    continue

                lane = tuple(sorted([current, neighbor]))
                if lane in avoid_lanes:
                    continue

                # A* Algorithm updates
                tentative_g_score = g_score[current] + heuristic(current, neighbor)
                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal_idx)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor, path + [neighbor]))

        log_action(self.gui, f"No path found from {start_idx} to {goal_idx}")
        return []


    def update_traffic(self, robots):
    # Reset occupied lanes and vertices
        self.occupied_lanes.clear()
        self.occupied_vertices.clear()

        # Track currently occupied lanes and vertices
        for robot in robots:
            if robot.status == "moving" and robot.path and robot.progress > 0:
                next_idx = robot.path[0]
                lane = tuple(sorted([robot.pos_idx, next_idx]))
                self.occupied_lanes.add(lane)
                self.occupied_vertices.add(robot.pos_idx)
            elif robot.status in ["moving", "waiting"]:
                self.occupied_vertices.add(robot.pos_idx)

        # Sort robots by priority (higher priority moves first)
        sorted_robots = sorted(robots, key=lambda r: r.priority, reverse=True)
        
        for robot in sorted_robots:
            if robot.status == "moving" and robot.path:
                next_idx = robot.path[0]
                lane = tuple(sorted([robot.pos_idx, next_idx]))
                
                # Check for robots meeting at the same vertex or lane
                meeting_robots = [
                    r for r in robots
                    if r != robot and r.status == "moving" and r.path and (
                        (r.pos_idx == next_idx and r.path[0] == robot.pos_idx) or  # Head-on collision
                        (tuple(sorted([r.pos_idx, r.path[0]])) == lane)  # Same lane conflict
                    )
                ]
                
                if meeting_robots:
                    # Both robots enter waiting state
                    robot.status = "waiting"
                    self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1
                    for other_robot in meeting_robots:
                        other_robot.status = "waiting"
                        self.waiting_cooldown[other_robot.id] = self.waiting_cooldown.get(other_robot.id, 0) + 1
                    log_action(self.gui, f"{robot.id} (P:{robot.priority}) and {meeting_robots[0].id} (P:{meeting_robots[0].priority}) waiting due to meeting")
                    continue

                # Handle same-vertex conflicts (existing logic)
                same_vertex_competitors = [
                    r for r in robots
                    if r != robot and r.pos_idx == robot.pos_idx and r.path and r.path[0] == next_idx
                ]
                if same_vertex_competitors:
                    highest_priority = max(same_vertex_competitors + [robot], key=lambda r: r.priority)
                    if robot != highest_priority:
                        robot.status = "waiting"
                        self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1
                        log_action(self.gui, f"{robot.id} waiting for {highest_priority.id} to move (same vertex)")
                        continue

                # Detect blockers (existing logic adapted)
                blockers = [
                    r for r in robots
                    if r != robot and (
                        (r.status == "moving" and r.path and tuple(sorted([r.pos_idx, r.path[0]])) == lane)
                        or (r.pos_idx == next_idx and r.status in ["moving", "waiting"])
                    )
                ]

                if blockers and robot.progress >= 1:
                    highest_priority_blocker = max(blockers, key=lambda r: r.priority, default=None)
                    if highest_priority_blocker.priority > robot.priority:
                        # Show conflict notification
                        messagebox.showwarning("Conflict Detected", 
                                            f"{robot.id} (P:{robot.priority}) blocked by {highest_priority_blocker.id} (P:{highest_priority_blocker.priority})")
                        # Lower-priority robot finds alternative path
                        alternative_path = self.find_path(robot.pos_idx, robot.goal_idx, avoid_vertex=next_idx, avoid_lanes=self.occupied_lanes)
                        if alternative_path:
                            robot.path = alternative_path
                            robot.status = "moving"
                            robot.progress = 0
                            log_action(self.gui, f"{robot.id} (P:{robot.priority}) rerouted to avoid {highest_priority_blocker.id}")
                        else:
                            robot.status = "waiting"
                            self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1
                            log_action(self.gui, f"{robot.id} (P:{robot.priority}) waiting due to no alternative path")
                    else:
                        # Higher-priority robot moves, lower-priority blockers adjust
                        for blocker in blockers:
                            messagebox.showwarning("Conflict Detected", 
                                                f"{blocker.id} (P:{blocker.priority}) blocked by {robot.id} (P:{robot.priority})")
                            alternative_path = self.find_path(blocker.pos_idx, blocker.goal_idx, avoid_vertex=robot.pos_idx)
                            if alternative_path:
                                blocker.path = alternative_path
                                blocker.status = "moving"
                                blocker.progress = 0
                                log_action(self.gui, f"{blocker.id} (P:{blocker.priority}) rerouted for {robot.id}")
                            else:
                                blocker.status = "waiting"
                                self.waiting_cooldown[blocker.id] = self.waiting_cooldown.get(blocker.id, 0) + 1
                                log_action(self.gui, f"{blocker.id} (P:{blocker.priority}) waiting for {robot.id}")
                elif robot.progress >= 1:
                    # No blockers, proceed with movement
                    robot.previous_pos_idx = robot.pos_idx
                    robot.pos_idx = robot.path.pop(0)
                    if not robot.path:
                        robot.status = "task complete"
                        log_action(self.gui, f"{robot.id} (P:{robot.priority}) completed task")

            elif robot.status == "waiting" and robot.path:
                next_idx = robot.path[0]
                blockers = [r for r in robots if r != robot and r.pos_idx == next_idx]
                if not blockers or all(r.priority < robot.priority for r in blockers):
                    # Resolve waiting state for higher-priority robot
                    robot.status = "moving"
                    self.waiting_cooldown[robot.id] = 0
                    log_action(self.gui, f"{robot.id} (P:{robot.priority}) resumed movement")
                else:
                    # Lower-priority robot finds alternative path
                    alternative_path = self.find_path(robot.pos_idx, robot.goal_idx, avoid_vertex=next_idx, avoid_lanes=self.occupied_lanes)
                    if alternative_path:
                        robot.path = alternative_path
                        robot.status = "moving"
                        robot.progress = 0
                        log_action(self.gui, f"{robot.id} (P:{robot.priority}) rerouted after waiting")
                    else:
                        self.waiting_cooldown[robot.id] = self.waiting_cooldown.get(robot.id, 0) + 1

        # Handle deadlock (existing logic)
        for robot in robots:
            if robot.status == "waiting" and self.waiting_cooldown.get(robot.id, 0) >= 3:
                adjacent_vertices = [
                    end for start, end, _ in self.nav_graph.lanes
                    if start == robot.pos_idx and end not in self.occupied_vertices
                ]
                if adjacent_vertices:
                    random_vertex = random.choice(adjacent_vertices)
                    robot.path = [random_vertex] + self.find_path(random_vertex, robot.goal_idx)
                    robot.pos_idx = random_vertex
                    robot.status = "moving"
                    self.waiting_cooldown[robot.id] = 0
                    log_action(self.gui, f"{robot.id} (P:{robot.priority}) randomly moved to resolve deadlock")