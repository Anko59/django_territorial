import numpy as np
from loguru import logger
from territorial.models import GameState, Square, AttackMovement, Boat
from territorial.services.map import WorldMap
from scipy.signal import convolve2d
from collections import Counter


class Game:
    def __init__(self, width: int, height: int, num_squares: int = 250):
        self.state: GameState = GameState(
            width=width,
            height=height,
            grid=np.zeros((height, width), dtype=np.uint32),
            num_squares=num_squares,
            squares=[],
            color_grid=np.zeros((height, width, 4), dtype=np.uint8),
        )
        self.map = WorldMap(width, height)
        self.state.grid[self.map.water_mask] = -1
        self.state.grid[self.map.mountain_mask] = -2
        self.state.squares = [self.create_random_square(i + 1) for i in range(self.state.num_squares)]
        self.id_squares_map = {square.id: square for square in self.state.squares}
        self.max_area = 1
        self.neighbors = np.array([])

    def create_random_square(self, square_id: int) -> Square:
        square = Square.create_random(square_id, self.map)
        y_range = range(max(0, square.start_y - 5), min(self.state.height, square.start_y + 4))
        x_range = range(max(0, square.start_x - 5), min(self.state.width, square.start_x + 4))

        # Set the 5x5 area (or as much of it as fits within the grid)
        for y in y_range:
            for x in x_range:
                if self.state.grid[y, x] != -1:  # Check if the position is accessible
                    self.state.grid[y, x] = square.id
                    self.state.color_grid[y, x] = square.color

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
        square_cost, target_cost = attack_movement.get_next_pixels_costs(next_pixels, target, self.map.traversability_map)
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

    def update_boats(self) -> None:
        for boat in self.state.boats:
            boat.update_pos()
            try:
                if int(boat.pos[1]) < 0:
                    boat.pos = (boat.pos[0], self.state.width - 1)
                elif int(boat.pos[1]) >= self.state.width:
                    boat.pos = (boat.pos[0], 0)
                if boat.pos[0] < 0 or boat.pos[0] >= self.state.height:
                    self.state.boats.remove(boat)
                    continue
                boat_collision = self.state.grid[int(boat.pos[0]), int(boat.pos[1])]
            except ValueError as e:
                logger.error(f"Error while updating boats: {e}")
                logger.error(f"Boat pos: {boat.pos}")
                logger.error(f"Boat speed: {boat.speed}")
                self.state.boats.remove(boat)
                continue
            if boat_collision == -1:
                continue
            self.state.boats.remove(boat)
            if boat_collision == boat.source:
                self.get_square_from_id(boat.source).resources += boat.investment
            else:
                new_movement = AttackMovement.from_boat(boat, boat_collision)
                self.handle_movement_collisions(new_movement)

    def get_new_attack_movements(self) -> None:
        for square in self.state.squares:
            square_neighbors = self.get_neighbors(square.id)
            target, investment = square.get_target(set(square_neighbors))
            if target is not None:
                if target == -1:
                    boat = Boat.from_square(square, investment, self.state.grid)
                    if boat is not None:
                        self.state.boats.append(boat)
                    continue
                new_movement = AttackMovement(source=square.id, target=target, investment=investment)
                square.resources -= investment

                self.handle_movement_collisions(new_movement)

    def update_centers_of_mass(self) -> None:
        reduction_factor = 5
        grid = self.state.grid[::reduction_factor, ::reduction_factor]
        for square in self.state.squares:
            square.update_center_of_mass(grid, reduction_factor)

    def kill_square(self, square: Square) -> None:
        self.state.squares.remove(square)
        self.state.color_grid[self.state.grid == square.id, :] = np.array([0, 0, 0, 0])
        self.state.grid[self.state.grid == square.id] = 0
        for attack_movement in self.state.attack_movements:
            if attack_movement.target == square.id:
                attack_movement.target = 0

    def update_square_areas(self) -> None:
        flatten_grid = self.state.grid.flatten()
        value_counts = dict(Counter(flatten_grid))

        for square in self.state.squares:
            if square.id not in value_counts.keys():
                self.kill_square(square)
                continue
            square_area = value_counts[square.id]
            if square_area > self.max_area:
                self.max_area = square_area
            if square_area < 10 or square_area < self.max_area / 100:
                self.kill_square(square)
                continue
            square.area = square_area
            square_avg_land_value = np.mean(self.map.livability_map[self.state.grid == square.id])
            square.average_land_value = float(square_avg_land_value)

    def get_color_grid(self) -> np.ndarray:
        return self.state.color_grid

    def find_all_possible_targets(self) -> np.ndarray:
        reduction_factor = 2
        grid = self.state.grid[::reduction_factor, ::reduction_factor]

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
        unique_pairs = unique_pairs[(unique_pairs[:, 0] != -2) & (unique_pairs[:, 1] != -2)]

        return unique_pairs

    def update_neighbors(self) -> None:
        self.neighbors = self.find_all_possible_targets()
