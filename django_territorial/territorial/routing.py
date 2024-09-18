from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/square/$", consumers.SquareConsumer.as_asgi()),
]
