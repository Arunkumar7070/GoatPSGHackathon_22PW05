# src/models/nav_graph.py
import json

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