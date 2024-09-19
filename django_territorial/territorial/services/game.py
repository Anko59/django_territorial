import numpy as np
from loguru import logger
from territorial.models import GameState, Square, AttackMovement
from territorial.services.map import Map
from scipy.signal import convolve2d
from collections import Counter


class Game:
    def __init__(self, width: int = 600, height: int = 400, num_squares: int = 200):
        self.state: GameState = GameState(
            width=width,
            height=height,
            grid=np.zeros((height, width), dtype=np.uint32),
            num_squares=num_squares,
            squares=[],
            color_grid=np.zeros((height, width, 4), dtype=np.uint8),
        )
        self.map = Map(width, height)
        self.state.grid[~self.map.get_accessibility_mask()] = -1
        self.state.squares = [self.create_random_square(i) for i in range(self.state.num_squares)]
        self.id_squares_map = {square.id: square for square in self.state.squares}

        self.neighbors = np.array([])

    def create_random_square(self, square_id: int) -> Square:
        color = np.random.randint(0, 256, (1, 4), dtype=np.uint8)
        color[0, 3] = 125  # Set alpha to 125

        # Create a mask of accessible positions
        accessible_mask = self.state.grid != -1

        # Get the indices of accessible positions
        accessible_indices = np.argwhere(accessible_mask)

        # Randomly choose a starting position from accessible positions
        start_y, start_x = accessible_indices[np.random.randint(len(accessible_indices))]

        square = Square(
            id=square_id + 1,
            color=color,
        )
        self.state.grid[start_y, start_x] = square.id
        square.update_center_of_mass(self.state.grid)
        return square

    def get_square_from_id(self, square_id: int) -> Square | None:
        if square_id in self.id_squares_map:
            return self.id_squares_map[square_id]
        return None

    def capture_pixels(self, pixels: np.ndarray, square: Square):
        self.state.grid[pixels[:, 0], pixels[:, 1]] = square.id
        self.state.color_grid[pixels[:, 0], pixels[:, 1]] = square.color

    def _update_attack_movement(self, attack_movement: AttackMovement) -> None:
        square = self.get_square_from_id(attack_movement.source)
        if square is None:
            logger.error(f"Square with id {attack_movement.source} not found")
            return
        target = self.get_square_from_id(attack_movement.target)
        next_pixels = attack_movement.get_next_pixels(self.state.grid)
        if len(next_pixels) == 0:
            square.resources += attack_movement.investment
            self.state.attack_movements.remove(attack_movement)
            return
        self.capture_pixels(next_pixels, square)
        attack_movement.border_pixels = next_pixels
        square_cost, target_cost = attack_movement.get_next_pixels_costs(next_pixels, target)
        attack_movement.investment -= square_cost
        if target is not None:
            target.resources -= target_cost
        if attack_movement.investment <= 0:
            self.state.attack_movements.remove(attack_movement)
            return

    def update_attack_movements(self) -> list[tuple[int, int, str]]:
        for attack_movement in self.state.attack_movements:
            if not attack_movement.is_started:
                attack_movement.start(self.state.grid)
            self._update_attack_movement(attack_movement)

    def handle_movement_collisions(self, new_movement: AttackMovement) -> None:
        for movement in self.state.attack_movements:
            if movement.source == new_movement.source and movement.target == new_movement.target:
                movement.investment += new_movement.investment
                return
            if movement.source == new_movement.target and movement.target == new_movement.source:
                min_investment = min(new_movement.investment, movement.investment)
                new_movement.investment -= min_investment
                movement.investment -= min_investment
                if new_movement.investment > 0:
                    self.state.attack_movements.append(new_movement)
                if movement.investment <= 0:
                    self.state.attack_movements.remove(movement)
                return
        self.state.attack_movements.append(new_movement)

    def get_neighbors(self, square_id: int) -> np.ndarray:
        if self.neighbors.size == 0:
            return np.array([])
        targets = self.neighbors[np.any(self.neighbors == square_id, axis=1)]
        return np.unique(targets[targets != square_id])

    def update_resources(self) -> None:
        for square in self.state.squares:
            square.update_resources()

    def get_new_attack_movements(self) -> None:
        for square in self.state.squares:
            square_neighbors = self.get_neighbors(square.id)
            new_movement = square.get_new_attack_movement(set(square_neighbors))
            if new_movement:
                self.handle_movement_collisions(new_movement)

    def update_centers_of_mass(self) -> None:
        for square in self.state.squares:
            square.update_center_of_mass(self.state.grid)

    def update_square_areas(self) -> None:
        flatten_grid = self.state.grid.flatten()
        value_counts = dict(Counter(flatten_grid))

        for square in self.state.squares:
            if square.id not in value_counts.keys():
                self.state.squares.remove(square)
            else:
                square.area = value_counts[square.id]

    def get_color_grid(self) -> np.ndarray:
        return self.state.color_grid

    def find_all_possible_targets(self) -> np.ndarray:
        grid = self.state.grid

        kernels = [
            np.array([[0, 1, 0], [0, 0, 0], [0, 0, 0]]),  # up
            np.array([[0, 0, 0], [0, 0, 1], [0, 0, 0]]),  # right
        ]

        # List to collect all pairs
        all_pairs = []

        # Perform convolution for each direction
        for kernel in kernels:
            convolved = convolve2d(grid, kernel, mode="same", boundary="fill", fillvalue=0)

            # Find indices where convolution has non-zero elements
            mask = convolved != 0
            source_ids = grid[mask]
            target_ids = convolved[mask]

            # Collect pairs and sort them for uniqueness
            pairs = np.column_stack((source_ids, target_ids))
            pairs = np.unique(pairs, axis=0)
            pairs = np.sort(pairs, axis=1)
            all_pairs.append(pairs)

        # Stack all pairs and find unique ones
        all_pairs = np.vstack(all_pairs)
        unique_pairs = np.unique(all_pairs, axis=0)

        # Filter out unaccessible positions
        unique_pairs = unique_pairs[(unique_pairs[:, 0] != -1) & (unique_pairs[:, 1] != -1)]

        return unique_pairs

    def update_neighbors(self) -> None:
        self.neighbors = self.find_all_possible_targets()
