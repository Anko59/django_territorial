import numpy as np
from loguru import logger
from scipy.ndimage import zoom
import os
import pickle
import hashlib

from enum import Enum
from dataclasses import dataclass


class BiomeType(Enum):
    OCEAN = 0
    TUNDRA = 1
    TAIGA = 2
    TEMPERATE_GRASSLAND = 3
    TEMPERATE_FOREST = 4
    TEMPERATE_RAINFOREST = 5
    TROPICAL_SAVANNA = 6
    TROPICAL_FOREST = 7
    TROPICAL_RAINFOREST = 8
    DESERT = 9
    MOUNTAIN = 10
    ICE = 11
    COLD_DESERT = 12
    HOT_DESERT = 13


@dataclass
class BiomeThresholds:
    min_temp: float
    max_temp: float
    min_rainfall: float
    max_rainfall: float
    min_elevation: float
    max_elevation: float


class Biome:
    def __init__(self, biome_type: BiomeType, color: np.ndarray, thresholds: BiomeThresholds, livability: float, traversability: float):
        self.type = biome_type
        self.color = color
        self.thresholds = thresholds
        self.livability = livability
        self.traversability = traversability

    @classmethod
    def get_biomes(cls):
        return [
            cls(BiomeType.OCEAN, np.array([0, 0, 128, 255]), BiomeThresholds(-np.inf, np.inf, -np.inf, np.inf, -np.inf, 0), 0.0, 0.2),
            cls(BiomeType.ICE, np.array([255, 255, 255, 255]), BiomeThresholds(-np.inf, -10, -np.inf, np.inf, 0, np.inf), 0.1, 0.3),
            cls(BiomeType.TUNDRA, np.array([224, 224, 224, 255]), BiomeThresholds(-10, 0, 0, np.inf, 0, 3000), 0.2, 0.6),
            cls(BiomeType.COLD_DESERT, np.array([200, 200, 170, 255]), BiomeThresholds(-10, 20, 0, 1, 0, 3000), 0.3, 0.7),
            cls(BiomeType.TAIGA, np.array([95, 115, 62, 255]), BiomeThresholds(0, 5, 1, np.inf, 0, 3000), 0.4, 0.5),
            cls(BiomeType.TEMPERATE_GRASSLAND, np.array([167, 197, 107, 255]), BiomeThresholds(5, 20, 1, 2, 0, 3000), 0.8, 0.9),
            cls(BiomeType.TEMPERATE_FOREST, np.array([76, 112, 43, 255]), BiomeThresholds(5, 20, 2, 4, 0, 3000), 0.9, 0.7),
            cls(BiomeType.TEMPERATE_RAINFOREST, np.array([68, 100, 18, 255]), BiomeThresholds(5, 20, 4, np.inf, 0, 3000), 0.7, 0.6),
            cls(BiomeType.TROPICAL_SAVANNA, np.array([177, 209, 110, 255]), BiomeThresholds(20, np.inf, 1, 4, 0, 3000), 0.6, 0.8),
            cls(BiomeType.TROPICAL_FOREST, np.array([66, 123, 25, 255]), BiomeThresholds(20, np.inf, 4, 6, 0, 3000), 0.5, 0.5),
            cls(BiomeType.TROPICAL_RAINFOREST, np.array([0, 100, 0, 255]), BiomeThresholds(20, np.inf, 6, np.inf, 0, 3000), 0.4, 0.3),
            cls(BiomeType.HOT_DESERT, np.array([238, 218, 130, 255]), BiomeThresholds(20, np.inf, 0, 1, 0, 3000), 0.2, 0.8),
            cls(
                BiomeType.MOUNTAIN,
                np.array([128, 128, 128, 255]),
                BiomeThresholds(-np.inf, np.inf, -np.inf, np.inf, 3000, np.inf),
                0.3,
                0.2,
            ),
        ]

    @classmethod
    def get_biome(cls, elevation: float, rainfall: float, temperature: float) -> "Biome":
        if elevation <= 0:
            return next(biome for biome in cls.get_biomes() if biome.type == BiomeType.OCEAN)

        matching_biomes = [
            biome
            for biome in cls.get_biomes()
            if (
                biome.thresholds.min_elevation <= elevation < biome.thresholds.max_elevation
                and biome.thresholds.min_rainfall <= rainfall < biome.thresholds.max_rainfall
                and biome.thresholds.min_temp <= temperature < biome.thresholds.max_temp
            )
        ]

        if matching_biomes:
            return matching_biomes[0]
        else:
            # Fallback to the most suitable biome based on elevation
            if elevation >= 3000:
                return next(biome for biome in cls.get_biomes() if biome.type == BiomeType.MOUNTAIN)
            elif temperature < -10:
                return next(biome for biome in cls.get_biomes() if biome.type == BiomeType.ICE)
            elif temperature < 20:
                return next(biome for biome in cls.get_biomes() if biome.type == BiomeType.COLD_DESERT)
            else:
                return next(biome for biome in cls.get_biomes() if biome.type == BiomeType.HOT_DESERT)


def resize_map(map: np.ndarray, new_width: int, new_height: int) -> np.ndarray:
    zoom_factors = (new_height / map.shape[0], new_width / map.shape[1])
    return zoom(map, zoom_factors, order=1)


class WorldMap:
    def __init__(self, width: int, height: int, seed: int = 42):
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else np.random.randint(0, 1000000)
        self.cache_key = self._generate_cache_key()
        self.cache_dir = os.path.join(os.path.dirname(__file__), "map_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        cached_data = self._load_cached_data()
        if cached_data:
            logger.info("Loaded data from cache.")
            (
                self.elevation_map,
                self.rainfall_map,
                self.lon_grid,
                self.lat_grid,
                self.temperature_map,
                self.color_map,
                self.traversability_map,
                self.livability_map,
            ) = cached_data
        else:
            self.elevation_map = self.load_map("world_elevation.pkl")
            self.rainfall_map = self.load_map("world_rainfall.pkl")
            self.lon_grid = self.load_map("world_lon.pkl")
            self.lat_grid = self.load_map("world_lat.pkl")
            self.temperature_map = self.generate_temperature_map()
            self.color_map, self.traversability_map, self.livability_map = self.get_game_maps()
            self._save_cached_data()

        self.biomes = Biome.get_biomes()
        self.water_mask = self.elevation_map <= 0
        self.mountain_mask = self.elevation_map >= 3000
        self.accessibility_mask = (self.elevation_map > 0) & (self.elevation_map < 2000)

    def _generate_cache_key(self) -> str:
        key = f"{self.width}_{self.height}_{self.seed}"
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cache_file_path(self) -> str:
        return os.path.join(self.cache_dir, f"{self.cache_key}.pkl")

    def _load_cached_data(self) -> tuple[np.ndarray, ...] | None:
        cache_file = self._get_cache_file_path()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Error loading cached data: {e}")
        return None

    def _save_cached_data(self):
        cache_file = self._get_cache_file_path()
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(
                    (
                        self.elevation_map,
                        self.rainfall_map,
                        self.lon_grid,
                        self.lat_grid,
                        self.temperature_map,
                        self.color_map,
                        self.traversability_map,
                        self.livability_map,
                    ),
                    f,
                )
        except Exception as e:
            print(f"Error saving cached data: {e}")

    def apply_gall_peters_projection(self, map_data):
        height, width = map_data.shape
        projected_map = np.zeros((height, width))

        for y in range(height):
            # Calculate latitude in radians
            lat = np.pi * (y / height - 0.5)

            # Calculate the y-coordinate in the projected space
            y_proj = int((np.sin(lat) + 1) * height / 2)

            if 0 <= y_proj < height:
                for x in range(width):
                    # Simply copy the x-coordinate
                    projected_map[y_proj, x] = map_data[y, x]

        # Interpolate missing values
        for y in range(height):
            if np.all(projected_map[y] == 0):
                above = y - 1
                below = y + 1
                while above >= 0 and np.all(projected_map[above] == 0):
                    above -= 1
                while below < height and np.all(projected_map[below] == 0):
                    below += 1
                if above >= 0 and below < height:
                    projected_map[y] = (projected_map[above] + projected_map[below]) / 2

        return projected_map

    def load_map(self, file_path: str) -> np.ndarray:
        try:
            with open(os.path.join(os.path.dirname(__file__), file_path), "rb") as f:
                map = pickle.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"The map file {file_path} was not found.")

        # Resize the map to the desired dimensions
        # map = map[400:, :] # remove Antarctica
        map = self.apply_gall_peters_projection(map)
        map = resize_map(map, self.width, self.height)
        map = map[::-1, :]  # Flip vertically
        return map

    def generate_temperature_map(self) -> np.ndarray:
        # Constants for temperature calculation
        max_temp = 40  # Maximum temperature at equator
        min_temp = -15  # Minimum temperature at poles
        temp_range = max_temp - min_temp
        lapse_rate = 0.006  # Temperature decrease per meter of elevation

        # Normalize latitude to range [-1, 1]
        normalized_lat = self.lat_grid / 90.0

        # Calculate base temperature based on latitude
        base_temp = max_temp - temp_range * np.abs(normalized_lat)

        # Adjust temperature based on elevation
        temp_map = base_temp - np.maximum(0, self.elevation_map) * lapse_rate
        return temp_map

    def get_biome(self, x: int, y: int) -> Biome:
        elevation = self.elevation_map[y][x]
        rainfall = self.rainfall_map[y][x]
        if np.isnan(rainfall):
            rainfall = 0
        temperature = self.temperature_map[y][x]

        return Biome.get_biome(elevation, rainfall, temperature)

    def get_game_maps(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        color_map = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        traversability_map = np.zeros((self.height, self.width), dtype=np.float32)
        livability_map = np.zeros((self.height, self.width), dtype=np.float32)

        for y in range(self.height):
            for x in range(self.width):
                biome = self.get_biome(x, y)
                color = biome.color.copy()
                traversability_map[y][x] = biome.traversability
                livability_map[y][x] = biome.livability

                # Apply elevation shading
                elevation = self.elevation_map[y][x]
                if elevation > 0:
                    shade = min(1, max(0, elevation / 5000))
                    color[:3] = color[:3] * (1 - shade) + np.array([255, 255, 255]) * shade

                color_map[y][x] = color.astype(np.uint8)

        return color_map, traversability_map, livability_map
