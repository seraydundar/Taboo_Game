from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.conf import settings



class Oyuncu(AbstractUser):
    puan = models.IntegerField(default=0)
    friends = models.ManyToManyField('self', symmetrical=True, blank=True)
    objects = UserManager()
    is_ready = models.BooleanField(default=False)  # Ready flag
    
    def __str__(self):
        return self.username

class ProxyUser(Oyuncu):
    class Meta:
        proxy = True
        app_label = 'auth'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

class Game(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    current_round = models.PositiveIntegerField(default=1)
    total_rounds = models.PositiveIntegerField(default=3)
    
    def __str__(self):
        return f"Game {self.id} - Round {self.current_round}/{self.total_rounds}"

class Team(models.Model):
    TEAM_CHOICES = (
        ('red', 'Kırmızı'),
        ('blue', 'Mavi'),
    )
    name = models.CharField(max_length=10, choices=TEAM_CHOICES)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='teams')
    score = models.IntegerField(default=0)
    players = models.ManyToManyField(Oyuncu, related_name='teams')
    
    def __str__(self):
        return f"{self.get_name_display()} Team for Game {self.game.id}"

class Round(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='rounds')
    explainer = models.ForeignKey(Oyuncu, on_delete=models.SET_NULL, null=True, related_name='explained_rounds')
    start_time = models.DateTimeField(null=True, blank=True)
    pas_kullanilan = models.PositiveIntegerField(default=0)
    word = models.CharField(max_length=100, null=True, blank=True)
    forbidden_words = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"Round {self.id} of Game {self.game.id}"

class Kelime(models.Model):
    ana_kelime = models.CharField(max_length=100)
    
    def __str__(self):
        return self.ana_kelime

class YasakliKelime(models.Model):
    kelime = models.CharField(max_length=100)
    ana_kelime = models.ForeignKey(Kelime, related_name='yasakli_kelimeler', on_delete=models.CASCADE)
    
    def __str__(self):
        return self.kelime

class FriendRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Bekliyor'),
        ('accepted', 'Kabul Edildi'),
        ('rejected', 'Reddedildi'),
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    lobby_invite = models.ForeignKey('Lobby', null=True, blank=True, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"

class Lobby(models.Model):
    game_started = models.BooleanField(default=False)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_lobbies")
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="lobbies", blank=True)
    red_team = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="red_lobbies", blank=True)
    blue_team = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="blue_lobbies", blank=True)
    current_word = models.ForeignKey("Kelime", null=True, blank=True, on_delete=models.SET_NULL)
    ready_players = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="ready_in_lobbies", blank=True)
    current_explainer = models.ForeignKey('Oyuncu', on_delete=models.SET_NULL, null=True, blank=True, related_name="current_explainer_lobbies")
    explainer_history = models.JSONField(default=list, blank=True)
    explainer_queue = models.JSONField(default=list, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    round_end = models.DateTimeField(null=True, blank=True)
    round_ready_players = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="round_ready_in_lobbies", blank=True)
    red_score = models.IntegerField(default=0)
    blue_score = models.IntegerField(default=0)
    label_assignments = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"Lobby hosted by {self.host.username} (Red: {self.red_team.count()}, Blue: {self.blue_team.count()})"



