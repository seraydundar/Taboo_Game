from django.contrib import admin
from django.urls import path
from game import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.welcome_view, name="welcome"),  # Root URL welcome_view'a yönlendiriyor.
    path('home/', views.home_view, name="home"),
    path('accounts/login/', views.login_view, name='login'),
    path('register/', views.register_view, name="register"),
    path('lobby/<int:lobby_id>/', views.lobby_view, name='lobby'),
    path('poll_lobby/<int:lobby_id>/', views.poll_lobby, name='poll_lobby'),
    path('new_lobby/', views.new_lobby, name="new_lobby"),
    path('leave_lobby/<int:lobby_id>/', views.leave_game, name="leave_lobby"),
    path('select_team/<int:lobby_id>/', views.select_team, name='select_team'),
    path('start_game/<int:lobby_id>/', views.start_game, name="start_game"),
    path('game_view/<int:lobby_id>/', views.game_view, name='game_view'),
    path('login/', views.login_view, name="login"),
    path('mark_ready/', views.mark_ready, name="mark_ready"),
    path('toggle_ready/<int:lobby_id>/', views.toggle_ready, name="toggle_ready"),
    path('logout/', views.custom_logout, name="logout"),
    
    # Arkadaşlık ve bildirim yolları
    path('add_friend/', views.add_friend, name="add_friend"),
    path('accept_request/<int:request_id>/', views.accept_request, name='accept_request'),
    path('reject_request/<int:request_id>/', views.reject_request, name='reject_request'),
    path('notifications/', views.notifications_view, name="notifications"),
    
    # Oyun ekranları
    path('explainer_screen/<int:lobby_id>/', views.explainer_screen, name='explainer_screen'),
    path('teammate_screen/<int:lobby_id>/', views.teammate_screen, name='teammate_screen'),
    path('opponent_screen/<int:lobby_id>/', views.opponent_screen, name='opponent_screen'),
    
    # Oyundan çıkma ve lobiye davet
    path('leave_game/<int:lobby_id>/', views.leave_game, name='leave_game'),
    path('invite_lobby/<int:lobby_id>/', views.invite_lobby, name='invite_lobby'),
    path('end_round/<int:lobby_id>/', views.end_round, name='end_round'),
    path('poll_game_state/<int:lobby_id>/', views.poll_game_state, name='poll_game_state'),
    path('round_intermission/<int:lobby_id>/', views.round_intermission, name='round_intermission'),
    path('toggle_round_ready/<int:lobby_id>/', views.toggle_round_ready, name='toggle_round_ready'),
    path('poll_round_ready/<int:lobby_id>/', views.poll_round_ready, name='poll_round_ready'),
    path('game_over/', views.game_over, name='game_over'),
    
]




