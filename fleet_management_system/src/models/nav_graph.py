import json

class NavGraph:
    def __init__(self, file_path):
        """
        Initializes the navigation graph by loading data from a JSON file.

        :param file_path: Path to the JSON file containing the navigation graph.
        """
        try:
            with open(file_path, "r") as f:
                data = json.load(f)  # Load JSON data from file
            
            self.levels = data.get("levels", {})  # Extract levels from the JSON data

            # Ensure the JSON file contains at least one level
            if not self.levels:
                raise ValueError("No levels found in nav_graph")

            # Get the first level's key (assuming a single-level structure)
            level_key = next(iter(self.levels), None)
            if not level_key:
                raise ValueError("No valid level key in nav_graph")

            # Extract vertices (points) and lanes (connections) from the level
            level = self.levels[level_key]
            self.vertices = level.get("vertices", [])
            self.lanes = level.get("lanes", [])

            # Ensure both vertices and lanes exist
            if not self.vertices or not self.lanes:
                raise ValueError("Vertices or lanes missing in nav_graph")

        except (json.JSONDecodeError, IOError, ValueError) as e:
            # Handle invalid JSON format, file errors, or missing data
            raise ValueError(f"Invalid nav_graph file {file_path}: {str(e)}")

    def get_vertex_coords(self, idx):
        """
        Returns the (x, y) coordinates of a vertex if it exists.
        
        :param idx: Index of the vertex.
        :return: Tuple (x, y) representing the vertex coordinates, or (0, 0) if invalid index.
        """
        if 0 <= idx < len(self.vertices):
            return self.vertices[idx][0], self.vertices[idx][1]
        return 0, 0  # Default to (0,0) if the index is out of bounds

    def get_vertex_name(self, idx):
        """
        Returns the name of the vertex if it has one; otherwise, returns a default name.

        :param idx: Index of the vertex.
        :return: Name of the vertex or a default name like "V{idx}".
        """
        if 0 <= idx < len(self.vertices) and len(self.vertices[idx]) > 2:
            return self.vertices[idx][2].get("name", f"V{idx}")
        return f"V{idx}"  # Default to "V{idx}" if no name is provided

    def is_charger(self, idx):
        """
        Checks if the given vertex is a charging station.

        :param idx: Index of the vertex.
        :return: True if the vertex is a charger, otherwise False.
        """
        if 0 <= idx < len(self.vertices) and len(self.vertices[idx]) > 2:
            return self.vertices[idx][2].get("is_charger", False)
        return False  # Default to False if the index is invalid or the property is missing
