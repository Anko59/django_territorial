from pydantic import BaseModel
from pydantic import PlainSerializer, BeforeValidator
from functools import partial
from loguru import logger

from typing import Annotated
import random
from scipy.spatial import cKDTree
import numpy as np
import pandas as pd
from scipy.signal import convolve2d

import os
from territorial.services.map import WorldMap


GAME_WIDTH = 1200
GAME_HEIGHT = 800


class NumpyArray:
    """Numpy array type"""

    @staticmethod
    def validate(value, dtype):
        return np.array(value, dtype=dtype)

    @staticmethod
    def serialize(value):
        return value.tolist()

    def __class_getitem__(cls, item):
        validate = partial(cls.validate, dtype=item)
        return Annotated[np.ndarray, PlainSerializer(cls.serialize), BeforeValidator(validate)]


class AttackMovement(BaseModel):
    source: int
    target: int
    investment: int
    border_pixels: NumpyArray[int] | None = None
    is_started: bool = False

    @classmethod
    def from_boat(cls, boat: "Boat", target: int):
        self = cls(source=boat.source, target=target, investment=boat.investment)
        self.border_pixels = np.array([boat.pos]).astype(int)
        self.is_started = True
        return self

    def start(self, grid: np.ndarray):
        self.border_pixels = self.find_start_pixels(grid)
        self.is_started = True

    def find_start_pixels(self, grid: np.ndarray) -> np.ndarray:
        own = grid == self.source
        target = grid == self.target
        kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
        adjacent = convolve2d(own, kernel, mode="same", boundary="fill")
        result = np.logical_and(target, adjacent > 0)
        indices = np.argwhere(result)
        return indices

    def get_next_pixels(self, grid: np.ndarray) -> np.ndarray:
        offsets = np.array([[0, 0], [-1, 0], [1, 0], [0, -1], [0, 1]])
        bordering_pixels = np.unique(np.array([self.border_pixels + offset for offset in offsets]).reshape(-1, 2), axis=0)
        valid_pixels = np.all(np.logical_and(bordering_pixels >= 0, bordering_pixels < grid.shape), axis=1)
        bordering_pixels = bordering_pixels[valid_pixels]
        bordering_pixels = bordering_pixels[grid[bordering_pixels[:, 0], bordering_pixels[:, 1]] == self.target]
        return bordering_pixels

    def get_next_pixels_costs(self, next_pixels: np.ndarray, target: "Square", traversability_map: np.ndarray) -> tuple[int, int]:
        num_pixels = len(next_pixels)
        traversability_score = np.mean(traversability_map[next_pixels[:, 0], next_pixels[:, 1]])
        if target is None:
            return int(num_pixels * (1 + (1 - traversability_score))), num_pixels
        # Base cost calculation
        base_cost = num_pixels * (target.resources / target.area)
        base_cost *= 1 + (1 - traversability_score)
        base_cost = base_cost

        # Adjust cost based on target's resource ratio
        resource_ratio = target.resources / (target.max_resources + 1)
        cost_multiplier = 1 + resource_ratio

        # Calculate costs for source and target
        source_cost = int(2 * base_cost * cost_multiplier)
        target_cost = int(base_cost * cost_multiplier)

        # Ensure costs don't exceed limits
        source_cost = min(source_cost, self.investment)
        target_cost = min(target_cost, target.resources)

        # Ensure source cost is always twice the target cost
        if source_cost < 2 * target_cost:
            target_cost = source_cost // 2
        elif source_cost > 2 * target_cost:
            source_cost = 2 * target_cost

        if source_cost < num_pixels:
            source_cost = num_pixels

        return source_cost, target_cost

    class Config:
        arbitrary_types_allowed = True


# When loading the data:
cities = pd.read_csv(os.path.join(os.path.dirname(__file__), "services/world_cities.csv"))
cities = cities[cities["population"] > 100000]

# Create a KD-tree
coords = cities[["lat", "lng"]].values
tree = cKDTree(coords)


class Square(BaseModel):
    id: int
    color: NumpyArray[int]
    name: str
    start_x: int
    start_y: int
    resources: int = 1000
    base_interest_rate: float = 0.01
    max_resources_multiplier: int = 100
    area: int = 1
    average_land_value: float = 1.0
    center_of_mass: tuple[float, float] = (0.0, 0.0)
    bonus_interval: int = 50
    update_counter: int = 0

    @staticmethod
    def find_closest_city(lat, lon):
        distance, index = tree.query([lat, lon], k=1)
        return cities.iloc[index]

    @classmethod
    def create_random(cls, id: int, map: WorldMap) -> "Square":
        color = np.random.randint(0, 256, (1, 4), dtype=np.uint8)
        color[0, 3] = 175  # Set alpha to 125
        accessible_mask = map.accessibility_mask
        accessible_indices = np.argwhere(accessible_mask)
        start_y, start_x = accessible_indices[np.random.randint(len(accessible_indices))]
        coords = map.lat_grid[start_y, start_x], map.lon_grid[start_y, start_x]
        name = cls.find_closest_city(*coords)["city"]
        square = cls(
            id=id,
            color=color,
            name=name,
            start_x=start_x,
            start_y=start_y,
        )
        logger.info(f"Created square {square.name} at {square.start_x}, {square.start_y}, or {coords[0]}, {coords[1]}")
        return square

    @property
    def max_resources(self) -> int:
        try:
            area = int(self.area * self.average_land_value)
            return max(int(area * self.max_resources_multiplier), 2000)
        except Exception as e:
            logger.error(
                f"Error calculating max_resources for square {self.id}, area: {self.area}, avg_land_value: {self.average_land_value}"
            )
            raise e

    @property
    def interest_rate(self) -> float:
        resource_factor = max(1 - (self.resources / self.max_resources) ** 2, 0)
        return self.base_interest_rate * resource_factor

    def update_resources(self):
        self.resources = min(int(self.resources * (1 + self.interest_rate) + 1), self.max_resources)
        self.update_counter += 1
        if self.update_counter % self.bonus_interval == 0:
            self.resources = min(int(self.resources + int(self.area * self.average_land_value) / 2), self.max_resources)

    def get_target(self, targets: set[int]) -> tuple[int | None, int | None]:
        if not targets:
            return None, None
        if not random.random() < 0.3:
            return None, None
        target = random.choice(list(targets))
        investmnet = int(random.uniform(0.01, 0.3) * self.resources)
        return target, investmnet

    def update_center_of_mass(self, grid: np.ndarray, reduction_factor: int = 1) -> tuple[float, float]:
        own = grid == self.id
        indices = np.argwhere(own)
        self.center_of_mass = (np.mean(indices[:, 0]) * reduction_factor, np.mean(indices[:, 1]) * reduction_factor)

    class Config:
        arbitrary_types_allowed = True


class Boat(BaseModel):
    source: int
    investment: int
    pos: tuple[float, float]
    speed: tuple[float, float]
    color: NumpyArray[int]

    def update_pos(self):
        self.pos = (self.pos[0] + self.speed[0], self.pos[1] + self.speed[1])

    @staticmethod
    def find_coastline(square_id: int, grid: np.ndarray) -> tuple[float, float] | None:
        own = grid == square_id
        target = grid == -1
        kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]])
        adjacent = convolve2d(own, kernel, mode="same", boundary="fill")
        result = np.logical_and(target, adjacent > 0)
        indices = np.argwhere(result)
        return indices

    @classmethod
    def from_square(cls, square: Square, investment: int, grid: np.ndarray) -> "Boat":
        square.resources -= investment
        coastline = cls.find_coastline(square.id, grid)
        if coastline is None or len(coastline) == 0:
            return None
        target = random.choice(coastline)

        # Calculate direction opposite to the center of mass
        center_y, center_x = square.center_of_mass
        direction_y = target[0] - center_y
        direction_x = target[1] - center_x

        # Normalize the direction vector
        magnitude = (direction_y**2 + direction_x**2) ** 0.5
        if magnitude == 0:
            return None  # Avoid division by zero

        normalized_y = direction_y / magnitude
        normalized_x = direction_x / magnitude

        # Set speed in the calculated direction
        total_speed = 2
        speed = (normalized_y * total_speed, normalized_x * total_speed)
        return cls(source=square.id, investment=investment, pos=target, speed=speed, color=square.color)

    class Config:
        arbitrary_types_allowed = True


class GameState(BaseModel):
    width: int
    height: int
    grid: NumpyArray[int]
    color_grid: NumpyArray[int]
    num_squares: int
    squares: list[Square]
    attack_movements: list[AttackMovement] = []
    boats: list[Boat] = []

    class Config:
        arbitrary_types_allowed = True


class SquareInfo(BaseModel):
    id: int
    name: str
    resources: int
    center_of_mass: tuple[float, float]
    area: int
    max_resources: int
    average_land_value: float
    interest_rate: float

    @classmethod
    def from_square(cls, square: Square):
        return cls(
            id=square.id,
            name=square.name,
            resources=square.resources,
            center_of_mass=square.center_of_mass,
            area=square.area,
            max_resources=square.max_resources,
            average_land_value=square.average_land_value,
            interest_rate=square.interest_rate,
        )


class SquareInfoMessage(BaseModel):
    type: str = "square_info"
    square_info: list[SquareInfo]


class GridUpdateMessage(BaseModel):
    type: str = "grid_update"
    grid: str


class MapMessage(BaseModel):
    type: str = "map"
    grid: str


class BoatMessage(BaseModel):
    type: str = "boat"
    boats: list[Boat]
