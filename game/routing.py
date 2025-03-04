# game/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/lobby/(?P<lobby_id>\d+)/$', consumers.LobbyConsumer.as_asgi()),
    re_path(r'^ws/game/(?P<game_id>\d+)/$', consumers.GameConsumer.as_asgi()),
]
