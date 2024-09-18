import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
import random
from territorial.services.game import Game
from territorial.consumers import SquareConsumer
from tqdm import tqdm
from loguru import logger

GAME_STATES_FILE = "game_states.json"


def generate_game_states(num_states=50):
    game_states = []

    for _ in tqdm(range(num_states), desc="Generating game states"):
        # Randomly choose game dimensions
        width = random.randint(100, 1000)
        height = random.randint(100, 1000)
        n_players = random.randint(2, 250)

        logger.debug(f"Creating game with dimensions: {width}x{height}, {n_players} players")
        game = Game(width=width, height=height, num_squares=n_players)

        # Randomly progress the game state
        play_until_remaining = random.randint(1, n_players)
        players_to_remove = n_players - play_until_remaining
        current_time = 0

        # Initialize last update times
        last_update = {key: 0 for key in SquareConsumer.UPDATE_INTERVALS.keys()}

        # Map update types to their corresponding game methods
        update_methods = {
            "attack_movements": game.update_attack_movements,
            "resources": game.update_resources,
            "centers_of_mass": game.update_centers_of_mass,
            "new_attack_movements": game.get_new_attack_movements,
            "square_areas": game.update_square_areas,
            "neighbors": game.update_neighbors,
        }
        eliminated = 0
        with tqdm(total=players_to_remove, desc="Simulating game", leave=False) as pbar:
            while len(game.state.squares) > play_until_remaining:
                current_time += 0.1  # Increment by 100ms each iteration

                # Check which updates should occur based on their intervals
                for update_type, interval in SquareConsumer.UPDATE_INTERVALS.items():
                    if current_time - last_update[update_type] >= interval:
                        if update_type in update_methods:
                            update_methods[update_type]()
                            last_update[update_type] = current_time
                if len(game.state.squares) < n_players - eliminated:
                    new_eliminated = n_players - eliminated - len(game.state.squares)
                    eliminated += new_eliminated
                    pbar.update(new_eliminated)
        # Final updates to ensure consistency
        game.update_square_areas()
        game.update_neighbors()
        logger.info(f"Game simulation completed. Final time: {current_time:.2f}")

        game_states.append(game.state.model_dump())

    return game_states


def save_game_states(game_states, filename=os.path.join(os.path.dirname(__file__), GAME_STATES_FILE)):
    logger.info(f"Saving {len(game_states)} game states to {filename}")
    with open(filename, "w") as f:
        f.write(json.dumps(game_states))
    logger.success(f"Game states saved successfully to {filename}")


if __name__ == "__main__":
    logger.info("Starting generation of 50 diverse game states...")
    states = generate_game_states(50)
    save_game_states(states)
    logger.success(f"50 game states have been generated and saved to '{GAME_STATES_FILE}'")

    # Print some statistics about the generated states
    widths = [state["width"] for state in states]
    heights = [state["height"] for state in states]
    num_squares = [len(state["squares"]) for state in states]
    num_attacks = [len(state["attack_movements"]) for state in states]

    logger.info("Statistics of generated game states:")
    logger.info(f"Width range: {min(widths)} to {max(widths)}")
    logger.info(f"Height range: {min(heights)} to {max(heights)}")
    logger.info(f"Number of squares range: {min(num_squares)} to {max(num_squares)}")
    logger.info(f"Number of active attacks range: {min(num_attacks)} to {max(num_attacks)}")
