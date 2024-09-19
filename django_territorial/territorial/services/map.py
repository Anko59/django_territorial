import numpy as np
from opensimplex import OpenSimplex


class Map:
    def __init__(self, width: int, height: int, seed: int = None):
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else np.random.randint(0, 1000000)
        self.noise_generator = OpenSimplex(seed=self.seed)
        self.elevation_map = self.generate_elevation_map()

    def generate_elevation_map(self) -> np.ndarray:
        elevation = np.zeros((self.height, self.width))
        scale = 0.007  # Adjust this to change the "zoom" of the noise

        for y in range(self.height):
            for x in range(self.width):
                elevation[y][x] = self.noise_generator.noise2(x * scale, y * scale)

        # Normalize to 0-1 range
        elevation = (elevation - elevation.min()) / (elevation.max() - elevation.min())
        return elevation

    def get_elevation_at(self, x: int, y: int) -> float:
        return self.elevation_map[y][x]

    def get_color_map(self) -> np.ndarray:
        color_map = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Define color gradients (RGB)
        deep_water = np.array([0, 0, 128, 255])
        shallow_water = np.array([0, 128, 255, 255])
        beach = np.array([240, 240, 64, 255])
        grass = np.array([32, 160, 0, 255])
        forest = np.array([0, 96, 0, 255])
        rock = np.array([128, 128, 128, 255])
        snow = np.array([255, 255, 255, 255])

        for y in range(self.height):
            for x in range(self.width):
                e = self.elevation_map[y][x]
                if e < 0.2:
                    color = deep_water + (shallow_water - deep_water) * (e / 0.2)
                elif e < 0.3:
                    color = shallow_water + (beach - shallow_water) * ((e - 0.2) / 0.1)
                elif e < 0.6:
                    color = beach + (grass - beach) * ((e - 0.3) / 0.3)
                elif e < 0.7:
                    color = grass + (forest - grass) * ((e - 0.6) / 0.1)
                elif e < 0.9:
                    color = forest + (rock - forest) * ((e - 0.7) / 0.2)
                else:
                    color = rock + (snow - rock) * ((e - 0.9) / 0.1)

                color_map[y][x] = color.astype(np.uint8)

        return color_map

    def get_accessibility_mask(self) -> np.ndarray:
        return (self.elevation_map > 0.3) & (self.elevation_map < 0.9)
