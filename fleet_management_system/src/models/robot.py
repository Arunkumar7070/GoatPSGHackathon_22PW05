# src/models/robot.py
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