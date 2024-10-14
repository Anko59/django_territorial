from channels.generic.websocket import AsyncWebsocketConsumer
import asyncio
from loguru import logger
import traceback
import time
import zlib

import numpy as np
from territorial.models import MapMessage, SquareInfoMessage, SquareInfo, GridUpdateMessage, BoatMessage, GAME_WIDTH, GAME_HEIGHT
from territorial.services.game import Game
from collections import defaultdict


class SquareConsumer(AsyncWebsocketConsumer):
    UPDATE_INTERVALS = {
        "attack_movements": 0.1,
        "resources": 0.1,
        "centers_of_mass": 2.0,
        "new_attack_movements": 2.0,
        "square_info": 0.5,
        "square_areas": 1.0,
        "grid_update": 0.2,
        "neighbors": 5.0,
        "boats": 0.1,
    }

    game = Game(GAME_WIDTH, GAME_HEIGHT)
    tasks = []
    connected_clients = set()
    execution_times = defaultdict(list)
    LOG_INTERVAL = 60

    @classmethod
    def initialize_game(cls):
        if not cls.tasks:
            cls.tasks = cls.create_background_tasks()

    @classmethod
    def create_background_tasks(cls):
        tasks = [
            asyncio.create_task(cls.update_loop("update_attack_movements")),
            asyncio.create_task(cls.update_loop("update_resources")),
            asyncio.create_task(cls.update_loop("update_centers_of_mass")),
            asyncio.create_task(cls.update_loop("get_new_attack_movements")),
            asyncio.create_task(cls.update_loop("update_square_areas")),
            asyncio.create_task(cls.update_loop("update_neighbors")),
            asyncio.create_task(cls.update_loop("update_boats")),
            asyncio.create_task(cls.send_grid_update()),
            asyncio.create_task(cls.send_square_info()),
            asyncio.create_task(cls.send_boats()),
            asyncio.create_task(cls.log_average_execution_times()),
        ]
        return tasks

    async def connect(self):
        await self.accept()
        logger.info("WebSocket connection established")
        self.connected_clients.add(self)
        self.initialize_game()
        await self.send_map()

    @classmethod
    async def update_loop(cls, method_name):
        while True:
            try:
                await cls.timed_execution(method_name, getattr(cls.game, method_name))
                await asyncio.sleep(cls.UPDATE_INTERVALS[method_name.split("_", 1)[1]])
            except Exception as e:
                cls.log_error(method_name, e)
                break

    @classmethod
    async def send_grid_update(cls):
        while True:
            try:
                await cls.timed_execution("send_grid_update", cls._send_grid_update)
            except Exception as e:
                cls.log_error("send_grid_update", e)
            await asyncio.sleep(cls.UPDATE_INTERVALS["grid_update"])

    @classmethod
    async def send_square_info(cls):
        while True:
            try:
                await cls.timed_execution("send_square_info", cls._send_square_info)
            except Exception as e:
                cls.log_error("send_square_info", e)
            await asyncio.sleep(cls.UPDATE_INTERVALS["square_info"])

    async def send_map(self):
        try:
            await self.timed_execution("send_map", self._send_map)
            logger.info("Map sent successfully")
        except Exception as e:
            self.log_error("send_map", e)

    @classmethod
    async def send_boats(cls):
        while True:
            try:
                await cls.timed_execution("send_boats", cls._send_boats)
            except Exception as e:
                cls.log_error("send_boats", e)
            await asyncio.sleep(cls.UPDATE_INTERVALS["boats"])

    @classmethod
    async def timed_execution(cls, name, func):
        start_time = time.time()
        await func() if asyncio.iscoroutinefunction(func) else func()
        execution_time = time.time() - start_time
        cls.execution_times[name].append(execution_time)

    @classmethod
    def log_error(cls, method_name, error):
        logger.error(f"Error in {method_name}: {str(error)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")

    @classmethod
    async def log_average_execution_times(cls):
        while True:
            await asyncio.sleep(cls.LOG_INTERVAL)
            log_message = "Average execution times:\n"
            for name, times in cls.execution_times.items():
                if times:
                    total_time = sum(times)
                    log_message += f"{name}: {total_time:.4f} seconds\n"
                    # Clear the times after logging
                    cls.execution_times[name] = []
            logger.info(log_message)

    @classmethod
    async def _send_square_info(cls):
        square_info = [SquareInfo.from_square(square) for square in cls.game.state.squares]
        message = SquareInfoMessage(square_info=square_info)
        await cls.broadcast(message.model_dump_json())

    async def _send_map(self):
        color_grid = self.game.map.color_map
        flat_grid = color_grid.flatten().astype(np.uint8).tobytes()
        compressed_grid = zlib.compress(flat_grid)
        map_message = MapMessage(grid=compressed_grid.hex())
        await self.send(text_data=map_message.model_dump_json())

    @classmethod
    async def _send_grid_update(cls):
        color_grid = cls.game.get_color_grid()
        flat_grid = color_grid.flatten().astype(np.uint8).tobytes()
        compressed_grid = zlib.compress(flat_grid)
        grid_update = GridUpdateMessage(grid=compressed_grid.hex())
        await cls.broadcast(grid_update.model_dump_json())

    @classmethod
    async def _send_boats(cls):
        boat_message = BoatMessage(boats=[boat for boat in cls.game.state.boats])
        await cls.broadcast(boat_message.model_dump_json())

    @classmethod
    async def broadcast(cls, message):
        clients_to_remove = set()
        for client in cls.connected_clients:
            try:
                await client.send(text_data=message)
            except Exception as e:
                logger.error(f"Error sending message to client: {str(e)}")
                clients_to_remove.add(client)

        # Remove disconnected clients
        cls.connected_clients -= clients_to_remove
        if clients_to_remove:
            logger.info(f"Removed {len(clients_to_remove)} disconnected client(s)")
