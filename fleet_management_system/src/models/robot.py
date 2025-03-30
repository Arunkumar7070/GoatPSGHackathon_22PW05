class Robot:
    def __init__(self, id, pos_idx, color, priority):
        self.id = id
        self.pos_idx = pos_idx
        self.previous_pos_idx = None  # Track the previous position
        self.goal_idx = None
        self.path = []
        self.color = color
        self.priority = priority
        self.status = "idle"
        self.progress = 0