import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.conf import settings
from .models import Lobby, Oyuncu

class LobbyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        ws://.../ws/lobby/<lobby_id>/ şeklinde route edeceğiz.
        Örneğin: re_path(r'^ws/lobby/(?P<lobby_id>\d+)/$', LobbyConsumer)
        """
        # URL pattern’inden parametre alalım:
        self.lobby_id = self.scope['url_route']['kwargs']['lobby_id']
        self.lobby_group_name = f"lobby_{self.lobby_id}"

        # Lobby var mı? (Senkron-async bridging => database query)
        # NOTE: Django ORM çağrılarını synchronous code'a çevirip yapıyoruz.
        # "channels.db" => database_sync_to_async ile saracağız.
        # Basitçe: accept() edelim, user check
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
        else:
            # Join group
            await self.channel_layer.group_add(
                self.lobby_group_name,
                self.channel_name
            )
            await self.accept()
            await self.send_lobby_state()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.lobby_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get("action")
        user = self.scope["user"]
        if action == "TEAM_SELECT":
            await self.handle_team_select(user, data)
        elif action == "READY_TOGGLE":
            await self.handle_ready_toggle(user, data)
        elif action == "START_GAME":
            await self.handle_start_game(user)
        # vs. ek aksiyon

    async def handle_team_select(self, user, data):
        team = data.get("team")
        # Lobby yi al
        lobby_obj = await self.get_lobby_or_none()
        if not lobby_obj:
            return
        # user katılımcı mı
        if user not in lobby_obj.participants.all():
            return
        # Zaten hangi takımda ise...
        if user in lobby_obj.red_team.all() or user in lobby_obj.blue_team.all():
            return
        # Logic
        if team == "red":
            # Basit limit => aradaki fark 1 den fazla olmasın
            red_count = lobby_obj.red_team.count()
            blue_count = lobby_obj.blue_team.count()
            if abs((red_count+1) - blue_count) > 1:
                # Reddedelim
                return
            # Ekle
            lobby_obj.red_team.add(user)
        elif team == "blue":
            red_count = lobby_obj.red_team.count()
            blue_count = lobby_obj.blue_team.count()
            if abs(red_count - (blue_count+1)) > 1:
                # Reddedelim
                return
            lobby_obj.blue_team.add(user)
        # Kaydet
        lobby_obj.save()

        # Tetikle => broadcast
        await self.send_lobby_state()

    async def handle_ready_toggle(self, user, data):
        lobby_obj = await self.get_lobby_or_none()
        if not lobby_obj:
            return
        if user not in lobby_obj.participants.all():
            return

        # Toggle
        if user in lobby_obj.ready_players.all():
            lobby_obj.ready_players.remove(user)
        else:
            lobby_obj.ready_players.add(user)
        lobby_obj.save()

        await self.send_lobby_state()

    async def handle_start_game(self, user):
        lobby_obj = await self.get_lobby_or_none()
        if not lobby_obj:
            return
        # Yalnızca host => start
        if user != lobby_obj.host:
            return
        # All Ready => check
        non_host = lobby_obj.participants.exclude(id=lobby_obj.host.id)
        all_ready = True
        for p in non_host:
            if p not in lobby_obj.ready_players.all():
                all_ready = False
                break
        if not all_ready:
            return
        # Oyun başlat => Bir link e yönlendirme?
        # Burada group_send ile client'a 'redirect' gibi event yollayabiliriz.
        await self.channel_layer.group_send(
            self.lobby_group_name,
            {
                "type": "game_started",
                "message": "Game has been started!",
                "lobby_id": lobby_obj.id
            }
        )

    async def game_started(self, event):
        # Tüm clientlara iletir
        await self.send(text_data=json.dumps({
            "type": "GAME_STARTED",
            "message": event["message"],
            "lobby_id": event["lobby_id"]
        }))

    async def send_lobby_state(self):
        """
        Mevcut lobi durumunu group'a broadcast.
        """
        lobby_obj = await self.get_lobby_or_none()
        if not lobby_obj:
            return
        # participants
        participants = []
        for p in lobby_obj.participants.all():
            participants.append({
                "id": p.id,
                "username": p.username,
                "is_ready": (p in lobby_obj.ready_players.all()),
            })
        red_count = lobby_obj.red_team.count()
        blue_count = lobby_obj.blue_team.count()
        # host => is_host
        # Bu consumer => user is self.scope['user']
        user = self.scope['user']
        is_host = (user == lobby_obj.host)

        # Non-host lar da ready mi?
        non_host = lobby_obj.participants.exclude(id=lobby_obj.host.id)
        all_ready = True
        for p in non_host:
            if p not in lobby_obj.ready_players.all():
                all_ready = False
                break

        payload = {
            "type": "lobby_update",
            "lobby_id": lobby_obj.id,
            "participants": participants,
            "red_count": red_count,
            "blue_count": blue_count,
            "is_host": is_host,
            "all_ready": all_ready,
        }
        # group_send
        await self.channel_layer.group_send(
            self.lobby_group_name,
            {
                "type": "broadcast_lobby_state",
                "payload": payload
            }
        )

    async def broadcast_lobby_state(self, event):
        """
        group_send ile gelen event => Bunu clientlara .send() yaparız
        """
        payload = event["payload"]
        await self.send(text_data=json.dumps(payload))

    # DB fetch
    from channels.db import database_sync_to_async
    @database_sync_to_async
    def get_lobby_or_none(self):
        try:
            return Lobby.objects.get(id=self.lobby_id)
        except Lobby.DoesNotExist:
            return None


#GameConsumer
class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # ...
        await self.accept()

    
