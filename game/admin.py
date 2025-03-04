from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ProxyUser, Kelime, YasakliKelime, Game, Team, Round
from game.models import FriendRequest

FriendRequest.objects.all()


# ProxyUser modelini, auth altında "Users" olarak admin paneline kaydediyoruz.
admin.site.register(ProxyUser, UserAdmin)

@admin.register(Kelime)
class KelimeAdmin(admin.ModelAdmin):
    list_display = ('ana_kelime',)

@admin.register(YasakliKelime)
class YasakliKelimeAdmin(admin.ModelAdmin):
    list_display = ('kelime', 'ana_kelime')

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'current_round', 'total_rounds', 'created_at')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'game', 'score')

@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('id', 'game', 'explainer', 'start_time', 'pas_kullanilan', 'word')


