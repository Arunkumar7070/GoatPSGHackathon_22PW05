import random
import heapq
from src.utils.helpers import log_action, notify_user

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
       