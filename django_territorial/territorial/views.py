from territorial.models import GAME_WIDTH, GAME_HEIGHT
from django.shortcuts import render
from channels.db import database_sync_to_async


@database_sync_to_async
def async_render(*args, **kwargs):
    return render(*args, **kwargs)


async def home_view(request):
    context = {
        "GAME_WIDTH": GAME_WIDTH,
        "GAME_HEIGHT": GAME_HEIGHT,
    }
    return await async_render(request, "index.html", context)
