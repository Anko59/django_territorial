from pydantic import BaseModel
from pydantic import PlainSerializer, BeforeValidator
from functools import partial

from typing import Annotated
import random
import numpy as np
from scipy.signal import convolve2d


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

    def get_next_pixels_costs(self, next_pixels: np.ndarray, target: "Square") -> tuple[int, int]:
        num_pixels = len(next_pixels)
        if target is None:
            return num_pixels, num_pixels
        # Base cost calculation
        base_cost = num_pixels * (target.resources / target.area)

        # Adjust cost based on target's resource ratio
        resource_ratio = target.resources / target.max_resources
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


class Square(BaseModel):
    id: int
    color: NumpyArray[int]
    resources: int = 1000
    base_interest_rate: float = 0.01
    max_resources_multiplier: float = 10.0
    area: int = 1
    center_of_mass: tuple[float, float] = (0.0, 0.0)
    bonus_interval: int = 50
    update_counter: int = 0

    @property
    def max_resources(self) -> int:
        return max(int(self.area * self.max_resources_multiplier), 2000)

    @property
    def interest_rate(self) -> float:
        size_factor = min(self.area / 100, 1)
        resource_factor = max(1 - (self.resources / self.max_resources), 0)
        return self.base_interest_rate * (1 + size_factor) * resource_factor

    def update_resources(self):
        self.resources = min(int(self.resources * (1 + self.interest_rate)), self.max_resources)
        self.update_counter += 1
        if self.update_counter % self.bonus_interval == 0:
            self.resources = min(int(self.resources + self.area / 2), self.max_resources)

    def get_new_attack_movement(self, neighbor_ids: set[int]) -> AttackMovement | None:
        if neighbor_ids and random.random() < 0.1:
            investment = int(random.uniform(0.01, 0.9) * self.resources)
            target = random.choice(list(neighbor_ids))
            attack_movement = AttackMovement(source=self.id, target=target, investment=investment)
            self.resources -= investment
            return attack_movement

    def update_center_of_mass(self, grid: np.ndarray) -> tuple[float, float]:
        own = grid == self.id
        indices = np.argwhere(own)
        self.center_of_mass = (np.mean(indices[:, 0]), np.mean(indices[:, 1]))

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

    class Config:
        arbitrary_types_allowed = True


class SquareInfo(BaseModel):
    id: int
    resources: int
    center_of_mass: tuple[float, float]


class SquareInfoMessage(BaseModel):
    type: str = "square_info"
    square_info: list[SquareInfo]


class GridUpdateMessage(BaseModel):
    type: str = "grid_update"
    grid: str


class MapMessage(BaseModel):
    type: str = "map"
    grid: str
