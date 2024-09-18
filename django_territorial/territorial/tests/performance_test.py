import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
import zlib
import time
import json
from functools import wraps
import numpy as np
from territorial.services.game import Game
from territorial.consumers import SquareConsumer
from territorial.models import GridUpdateMessage, GameState
from tqdm import tqdm
from loguru import logger

GAME_STATES_FILE = "game_states.json"


def load_game_states():
    with open(os.path.join(os.path.dirname(__file__), GAME_STATES_FILE), "r") as f:
        game_states_data = json.load(f)
    return [GameState(**data) for data in game_states_data]


def cpu_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.process_time()
        result = func(*args, **kwargs)
        end = time.process_time()
        return end - start, result

    return wrapper


class GamePerformanceTester:
    def __init__(self, game: Game):
        self.game = game
        self.performance_results = {}

    @cpu_time
    def timed_execution(self, func):
        return func()

    def measure_tasks(self):
        tasks = [
            ("update_attack_movements", self.game.update_attack_movements),
            ("update_resources", self.game.update_resources),
            ("update_centers_of_mass", self.game.update_centers_of_mass),
            ("get_new_attack_movements", self.game.get_new_attack_movements),
            ("update_square_areas", self.game.update_square_areas),
            ("update_neighbors", self.game.update_neighbors),
            ("send_grid_update", self.send_grid_update),
        ]

        for task_name, method in tasks:
            cpu_time, _ = self.timed_execution(method)
            self.performance_results[task_name] = cpu_time

        return self.performance_results

    def send_grid_update(self):
        color_grid = self.game.get_color_grid()
        flat_grid = color_grid.flatten().astype(np.uint8).tobytes()
        compressed_grid = zlib.compress(flat_grid)
        grid_update = GridUpdateMessage(grid=compressed_grid.hex())  # noqa


def run_performance_test(game_state):
    game = Game()
    game.state = game_state
    game.id_squares_map = {square.id: square for square in game.state.squares}
    tester = GamePerformanceTester(game)
    return tester.measure_tasks()


def main():
    logger.info("Starting performance tests")

    game_states = load_game_states()
    if not game_states:
        logger.error("No game states loaded. Exiting.")
        return

    all_results = []

    logger.info("Running performance tests:")
    for i, game_state in enumerate(tqdm(game_states, desc="Processing game states", unit="state")):
        results = run_performance_test(game_state)
        all_results.append(results)

    # Calculate average results
    avg_results = {}
    for task in all_results[0].keys():
        avg_results[task] = np.mean([result[task] for result in all_results])

    # Sort tasks by weighted execution time
    avg_results = sorted(avg_results.items(), key=lambda x: x[1], reverse=True)

    weights = SquareConsumer.UPDATE_INTERVALS
    weighted_avg_results = {task: time * 1 / (weights[task.split("_", 1)[1]]) for task, time in avg_results}
    total_weighted_time = sum(weighted_avg_results.values())
    weighted_avg_results = sorted(weighted_avg_results.items(), key=lambda x: x[1], reverse=True)

    # Prepare results for saving
    output = {
        "total_weighted_time": total_weighted_time,
        "weighted_average_results": weighted_avg_results,
        "average_results": avg_results,
        "raw_results": all_results,
        "updates_intervals": weights,
    }

    # Save results to a file
    results_dir = "performance_results"
    os.makedirs(results_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = os.path.join(results_dir, f"backend_performance_{timestamp}.json")

    try:
        with open(filename, "w") as f:
            json.dump(output, f, indent=2)
            logger.info(f"Performance results saved to {filename}")
    except Exception as e:
        logger.exception(f"Error saving performance results: {e}")

    # Print summary
    logger.info("Performance Summary (sorted by weighted execution time):")
    for task, _time in weighted_avg_results:
        logger.info(f"{task}: {_time:.6f}")


if __name__ == "__main__":
    main()
