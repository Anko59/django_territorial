from channels.generic.websocket import AsyncWebsocketConsumer
import asyncio
from loguru import logger
import traceback
import time
import zlib

import numpy as np
from territorial.models import InitialState, SquareInfoMessage, SquareInfo, GridUpdateMessage
from territorial.services.game import Game
from collections import defaultdict


class SquareConsumer(AsyncWebsocketConsumer):
    UPDATE_INTERVALS = {
        "attack_movements": 0.05,
        "resources": 0.1,
        "centers_of_mass": 2.0,
        "new_attack_movements": 0.5,
        "square_info": 0.5,
        "square_areas": 1.0,
        "grid_update": 0.2,
        "neighbors": 2.0,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execution_times = defaultdict(list)
        self.LOG_INTERVAL = 60  # Log average execution times every 60 seconds

    async def connect(self):
        await self.accept()
        logger.info("WebSocket connection established")
        self.game = Game()
        await self.send_initial_state()
        self.tasks = self.create_background_tasks()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket connection closed with code: {close_code}")
        for task in self.tasks:
            task.cancel()

    def create_background_tasks(self):
        tasks = [
            asyncio.create_task(self.update_loop("update_attack_movements")),
            asyncio.create_task(self.update_loop("update_resources")),
            asyncio.create_task(self.update_loop("update_centers_of_mass")),
            asyncio.create_task(self.update_loop("get_new_attack_movements")),
            asyncio.create_task(self.update_loop("update_square_areas")),
            asyncio.create_task(self.update_loop("update_neighbors")),
            asyncio.create_task(self.send_grid_update()),
            asyncio.create_task(self.send_square_info()),
            asyncio.create_task(self.log_average_execution_times()),
        ]
        return tasks

    async def update_loop(self, method_name):
        while True:
            try:
                await self.timed_execution(method_name, getattr(self.game, method_name))
                await asyncio.sleep(self.UPDATE_INTERVALS[method_name.split("_", 1)[1]])
            except Exception as e:
                self.log_error(method_name, e)
                break

    async def send_grid_update(self):
        while True:
            try:
                await self.timed_execution("send_grid_update", self._send_grid_update)
            except Exception as e:
                self.log_error("send_grid_update", e)
            await asyncio.sleep(self.UPDATE_INTERVALS["grid_update"])

    async def send_square_info(self):
        while True:
            try:
                await self.timed_execution("send_square_info", self._send_square_info)
            except Exception as e:
                self.log_error("send_square_info", e)
            await asyncio.sleep(self.UPDATE_INTERVALS["square_info"])

    async def send_initial_state(self):
        try:
            await self.timed_execution("send_initial_state", self._send_initial_state)
            logger.info("Initial state sent successfully")
        except Exception as e:
            self.log_error("send_initial_state", e)

    async def timed_execution(self, name, func):
        start_time = time.time()
        await func() if asyncio.iscoroutinefunction(func) else func()
        execution_time = time.time() - start_time
        self.execution_times[name].append(execution_time)

    def log_error(self, method_name, error):
        logger.error(f"Error in {method_name}: {str(error)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")

    async def log_average_execution_times(self):
        while True:
            await asyncio.sleep(self.LOG_INTERVAL)
            log_message = "Average execution times:\n"
            for name, times in self.execution_times.items():
                if times:
                    total_time = sum(times)
                    log_message += f"{name}: {total_time:.4f} seconds\n"
                    # Clear the times after logging
                    self.execution_times[name] = []
            logger.info(log_message)

    async def _send_square_info(self):
        square_info = [
            SquareInfo(id=square.id, resources=square.resources, center_of_mass=square.center_of_mass) for square in self.game.state.squares
        ]
        message = SquareInfoMessage(square_info=square_info)
        await self.send(text_data=message.model_dump_json())

    async def _send_initial_state(self):
        initial_state = InitialState(
            width=self.game.state.width,
            height=self.game.state.height,
            cells=[
                (x, y, self.game.state.grid[y][x])
                for y in range(self.game.state.height)
                for x in range(self.game.state.width)
                if self.game.state.grid[y][x] != 0
            ],
        )
        await self.send(text_data=initial_state.model_dump_json())

    async def _send_grid_update(self):
        color_grid = self.game.get_color_grid()
        flat_grid = color_grid.flatten().astype(np.uint8).tobytes()
        compressed_grid = zlib.compress(flat_grid)
        grid_update = GridUpdateMessage(grid=compressed_grid.hex())
        await self.send(text_data=grid_update.model_dump_json())
