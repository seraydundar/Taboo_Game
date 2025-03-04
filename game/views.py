import random
import time
import requests  # app_endpoint için
from functools import wraps
from django.utils import timezone
from datetime import timedelta
import re
from game import views

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings

from django.contrib.auth.decorators import login_required

from .forms import CustomUserCreationForm
from .models import (
    FriendRequest, Lobby, Kelime, YasakliKelime, Team, Game, 
    Oyuncu
)


# 1. UTILITY & DECORATOR FONKSİYONLARI


def app_endpoint():
    endpoint_url = "http://127.0.0.1:8000/app_update/"
    try:
        requests.get(endpoint_url, timeout=0.5)
    except Exception as e:
        print("app_endpoint error:", e)

def update_app(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        app_endpoint()
        return response
    return _wrapped_view


# 2. KULLANICI YÖNETİMİ (AUTHENTICATION)


@update_app
def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Lütfen formdaki hataları düzeltiniz.")
    else:
        form = CustomUserCreationForm()
    return render(request, "game/register.html", {"form": form})


@update_app
def welcome_view(request):
    if request.user.is_authenticated:
        return redirect("home")  # Giriş yapmışsa direkt home_view'a yönlendir.
    return render(request, "game/welcome.html")  # Giriş yapmamışsa welcome sayfasını göster.



@update_app
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Kullanıcı adı veya şifre hatalı!")
    else:
        form = AuthenticationForm(request)
    return render(request, "game/login.html", {"form": form})

@update_app
def custom_logout(request):
    logout(request)
    return redirect('home')


# 3. LOBİ (ODA) KONTROLLERİ


@update_app
def home_view(request):
    if not request.user.is_authenticated:
        return redirect("welcome")
    lobbies = Lobby.objects.filter(participants=request.user)
    if lobbies.exists():
        lobby = lobbies.first()
        return render(request, "game/home_single_lobby.html", {"lobby": lobby})
    else:
        return render(request, "game/home_no_lobby.html")


@update_app
def new_lobby(request):
    if request.user.lobbies.exists():
        messages.error(request, "Zaten bir lobiye sahipsiniz veya katıldınız. Yeni bir lobi açamazsınız.")
        return redirect('home')
    lobby = Lobby.objects.create(host=request.user)
    lobby.participants.add(request.user)
    lobby.current_explainer = None
    lobby.explainer_history = []
    messages.info(request, "Yeni lobi oluşturuldu.")
    return redirect('lobby', lobby_id=lobby.id)

@update_app
def lobby_view(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    if request.user not in lobby.participants.all():
        messages.error(request, "Bu lobiye erişim izniniz yok.")
        return redirect('home')
    team_selected = (request.user in lobby.red_team.all() or request.user in lobby.blue_team.all())
    context = {
        "lobby": lobby,
        "participants": lobby.participants.all(),
        "all_friends": [friend.username for friend in request.user.friends.all()],
        "team_selected": team_selected,
        "red_score": lobby.red_score,
        "blue_score": lobby.blue_score,
    }
    return render(request, "game/lobby.html", context)

@update_app
def leave_game(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    
    # Kullanıcıyı lobi ile ilişkili tüm many-to-many alanlardan çıkarıyoruz.
    if request.user in lobby.participants.all():
        lobby.participants.remove(request.user)
    if request.user in lobby.red_team.all():
        lobby.red_team.remove(request.user)
    if request.user in lobby.blue_team.all():
        lobby.blue_team.remove(request.user)
    if request.user in lobby.ready_players.all():
        lobby.ready_players.remove(request.user)
    if request.user in lobby.round_ready_players.all():
        lobby.round_ready_players.remove(request.user)
    
    lobby.save()
    
    messages.info(request, "Lobiden çıktınız.")
    # Kullanıcıyı çıkış yaptırıp welcome sayfasına yönlendiriyoruz.
    logout(request)
    return redirect("welcome")


@update_app
def select_team(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    if request.user not in lobby.participants.all():
        messages.error(request, "Bu lobiye dahil değilsiniz.")
        return redirect('home')
    if request.user in lobby.red_team.all() or request.user in lobby.blue_team.all():
        messages.info(request, "Zaten bir takım seçtiniz.")
        return redirect('lobby', lobby_id=lobby.id)
    if request.method == 'POST':
        team_choice = request.POST.get('team')
        if team_choice not in ['red', 'blue']:
            messages.error(request, "Geçersiz takım seçimi.")
            return render(request, "game/select_team.html", {"lobby": lobby})
        red_count = lobby.red_team.count()
        blue_count = lobby.blue_team.count()
        if team_choice == 'red':
            new_red = red_count + 1
            if abs(new_red - blue_count) > 1:
                messages.error(request, "Kırmızı takım dolu. Fark en fazla 1 olabilir.")
                return render(request, "game/select_team.html", {"lobby": lobby})
            else:
                lobby.red_team.add(request.user)
                messages.success(request, "Kırmızı takıma katıldınız.")
        elif team_choice == 'blue':
            new_blue = blue_count + 1
            if abs(new_blue - red_count) > 1:
                messages.error(request, "Mavi takım dolu. Fark en fazla 1 olabilir.")
                return render(request, "game/select_team.html", {"lobby": lobby})
            else:
                lobby.blue_team.add(request.user)
                messages.success(request, "Mavi takıma katıldınız.")
        return redirect('lobby', lobby_id=lobby.id)
    else:
        return render(request, "game/select_team.html", {"lobby": lobby})


# 4. OYUN (GAME) KONTROLLERİ


def get_random_kelime(current_word=None):
    kelimeler = list(Kelime.objects.all())
    if not kelimeler:
        return None
    if current_word and len(kelimeler) > 1:
        kelimeler = [k for k in kelimeler if k.id != current_word.id]
    return random.choice(kelimeler)

@update_app
def start_game(request, lobby_id):
    """
    Start the game:
      - Mark the requester as ready.
      - Ensure all players (non-host) are ready; if not, return an error.
      - If current_word is empty, assign a random word.
      - Randomly choose a starting explainer from participants (this becomes current_explainer) and reset explainer_history.
      - Set round_end and clear round_ready_players.
    """
    lobby = get_object_or_404(Lobby, id=lobby_id)
    lobby.ready_players.add(request.user)
    lobby.save()
    participants = list(lobby.participants.all())
    non_host = [p for p in participants if p != lobby.host]
    if non_host and not all(p in lobby.ready_players.all() for p in non_host):
        return JsonResponse({'error': 'Tüm oyuncular hazır değil!'}, status=400)
    if not lobby.current_word:
        new_k = get_random_kelime()
        if new_k:
            lobby.current_word = new_k
            lobby.save()
    if participants:
        chosen = random.choice(participants)
        lobby.current_explainer = chosen
        lobby.explainer_history = []  
        lobby.save()
    else:
        return JsonResponse({'error': 'Oyuncu yok!'}, status=400)
    set_round_end(lobby, 60)
    lobby.round_ready_players.clear()
    lobby.save()
    return JsonResponse({'redirect': f'/round_intermission/{lobby.id}/'})

def get_next_explainer(lobby):
    """
    Returns the next eligible explainer according to these conditions:
      - If current_explainer is in the red team, next must be a blue team player.
      - If current_explainer is in the blue team, next must be a red team player.
      - A player can serve only once (tracked in explainer_history).
      - If no eligible candidate exists, return None.
    """
    current = lobby.current_explainer
    if current in lobby.red_team.all():
        candidate_team = list(lobby.blue_team.all())
    else:
        candidate_team = list(lobby.red_team.all())
    history = lobby.explainer_history if lobby.explainer_history is not None else []
    available = [player for player in candidate_team if player.id not in history]
    if available:
        available.sort(key=lambda p: p.id)
        return available[0]
    return None

def handle_round_end(request, lobby):
    now = timezone.now()
    if lobby.round_end and now >= lobby.round_end:
        
        if lobby.explainer_history is None:
            lobby.explainer_history = []
        
        if lobby.current_explainer and lobby.current_explainer.id not in lobby.explainer_history:
            lobby.explainer_history.append(lobby.current_explainer.id)
        next_explainer = get_next_explainer(lobby)
        if next_explainer is None:
            lobby.save()
            return redirect("game_over")
        else:
            lobby.current_explainer = next_explainer
        lobby.round_ready_players.clear()
        lobby.round_end = None
        lobby.save()
        return redirect("round_intermission", lobby_id=lobby.id)
    return None


def set_round_end(lobby, duration=60):
    lobby.round_end = timezone.now() + timedelta(seconds=duration)
    lobby.save()

@update_app
def game_view(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    if request.user not in lobby.participants.all():
        messages.error(request, "Bu lobiye erişim izniniz yok.")
        return redirect('home')
    res = handle_round_end(request, lobby)
    if res:
        return res
    explainer = lobby.current_explainer
    user_is_explainer = (request.user == explainer)
    user_in_red = (request.user in lobby.red_team.all())
    user_in_blue = (request.user in lobby.blue_team.all())
    explainer_in_red = (explainer in lobby.red_team.all())
    if not lobby.current_word:
        new_k = get_random_kelime()
        if new_k:
            lobby.current_word = new_k
            lobby.save()
        else:
            messages.warning(request, "Veritabanında hiç Kelime yok!")
    if request.method == 'POST':
        if user_is_explainer:
            new_k = None
            if 'pas' in request.POST:
                new_k = get_random_kelime(current_word=lobby.current_word)
                messages.info(request, "Pas kullanıldı, yeni kelime getirildi.")
            elif 'dogru' in request.POST:
                messages.success(request, "Doğru cevap! +5 puan")
                if user_in_red:
                    lobby.red_score += 5
                else:
                    lobby.blue_score += 5
                new_k = get_random_kelime(current_word=lobby.current_word)
            if new_k:
                lobby.current_word = new_k
            lobby.save()
            return redirect('game_view', lobby_id=lobby_id)
        else:
            guess_text = request.POST.get('guess', '').strip().lower()
            if guess_text:
                same_team = ((user_in_red and explainer_in_red) or (user_in_blue and not explainer_in_red))
                if same_team:
                    current_word_obj = lobby.current_word
                    if current_word_obj:
                        actual_word = current_word_obj.ana_kelime.strip().lower()
                        if guess_text == actual_word:
                            messages.success(request, "Doğru tahmin! +5 puan")
                            if user_in_red:
                                lobby.red_score += 5
                            else:
                                lobby.blue_score += 5
                            new_k = get_random_kelime(current_word=lobby.current_word)
                            if new_k:
                                lobby.current_word = new_k
                            lobby.save()
                            return redirect('game_view', lobby_id=lobby_id)
                        else:
                            messages.error(request, "Yanlış tahmin!")
                    else:
                        messages.error(request, "Geçerli kelime bulunamadı!")
                else:
                    messages.error(request, "Tahmin hakkınız yok! (Aynı takımda olmalısınız)")
            if 'tabu' in request.POST and not user_is_explainer:
                messages.warning(request, "Tabu! Anlatıcı takımı -10 puan.")
                if explainer_in_red:
                    lobby.red_score -= 10
                else:
                    lobby.blue_score -= 10
                new_k = get_random_kelime(current_word=lobby.current_word)
                if new_k:
                    lobby.current_word = new_k
                else:
                    messages.error(request, "Yeni kelime bulunamadı!")
                lobby.save()
                return redirect('game_view', lobby_id=lobby_id)
    current_word_obj = lobby.current_word
    forbidden_list = current_word_obj.yasakli_kelimeler.all() if current_word_obj else []
    context = {
        "lobby": lobby,
        "red_score": lobby.red_score,
        "blue_score": lobby.blue_score,
        "round_end": lobby.round_end.isoformat() if lobby.round_end else None,
    }
    if user_is_explainer:
        context["word"] = current_word_obj.ana_kelime if current_word_obj else "Kelime Yok"
        context["forbidden_words"] = [y.kelime for y in forbidden_list]
        return render(request, "game/explainer_screen.html", context)
    else:
        same_team = (user_in_red and explainer_in_red) or (user_in_blue and not explainer_in_red)
        if same_team:
            return render(request, "game/teammate_screen.html", context)
        else:
            context["word"] = current_word_obj.ana_kelime if current_word_obj else "Kelime Yok"
            context["forbidden_words"] = [y.kelime for y in forbidden_list]
            return render(request, "game/opponent_screen.html", context)

@update_app
def end_round(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    res = handle_round_end(request, lobby)
    if res:
        return res
    messages.info(request, "Round sona erdi!")
    return redirect('lobby', lobby_id=lobby_id)

def poll_game_state(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    now = timezone.now()
    if not lobby.round_end or now >= lobby.round_end:
        return JsonResponse({
            "status": "round_ended",
            "redirect": f"/round_intermission/{lobby.id}/"
        })
    current_word_obj = lobby.current_word
    forbidden_words = []
    if current_word_obj:
        forbidden_words = [y.kelime for y in current_word_obj.yasakli_kelimeler.all()]
    data = {
        "status": "ongoing",
        "word": current_word_obj.ana_kelime if current_word_obj else "Kelime Yok",
        "forbidden_words": forbidden_words,
        "red_score": lobby.red_score,
        "blue_score": lobby.blue_score,
        "round_end": lobby.round_end.isoformat() if lobby.round_end else None,
    }
    return JsonResponse(data)

def get_next_explainer(lobby):
    """
    Returns the next eligible explainer:
      - Next must be from the opposite team of the current explainer.
      - A player can serve only once (tracked in explainer_history).
      - If no eligible candidate exists, return None.
    """
    current = lobby.current_explainer
    if current in lobby.red_team.all():
        candidate_team = list(lobby.blue_team.all())
    else:
        candidate_team = list(lobby.red_team.all())
    history = lobby.explainer_history if lobby.explainer_history is not None else []
    available = [player for player in candidate_team if player.id not in history]
    if available:
        available.sort(key=lambda p: p.id)
        return available[0]
    return None

def handle_round_end(request, lobby):
    """
    When a round ends:
      - If round_end has passed, add current_explainer to explainer_history.
      - Choose the next eligible explainer.
      - If no eligible candidate exists, redirect to game_over.
      - Clear round_ready_players and round_end, then redirect to round_intermission.
    """
    now = timezone.now()
    if lobby.round_end and now >= lobby.round_end:
        if lobby.explainer_history is None:
            lobby.explainer_history = []
        if lobby.current_explainer and lobby.current_explainer.id not in lobby.explainer_history:
            lobby.explainer_history.append(lobby.current_explainer.id)
        next_explainer = get_next_explainer(lobby)
        if next_explainer is None:
            lobby.save()
            return redirect("game_over")
        else:
            lobby.current_explainer = next_explainer
        lobby.round_ready_players.clear()
        lobby.round_end = None
        lobby.save()
        return redirect("round_intermission", lobby_id=lobby.id)
    return None

@update_app
def round_intermission(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
   
    res = handle_round_end(request, lobby)
    if res:
        return res
    
    lobby.round_ready_players.clear()
    lobby.save()
    next_explainer = get_next_explainer(lobby)
    context = {
        "lobby": lobby,
        "current_explainer": lobby.current_explainer.username if lobby.current_explainer else "Bilinmiyor",
        "next_explainer": next_explainer.username if next_explainer else "Oyun Sonu",
        
        "ready_count": lobby.round_ready_players.count(),
        "total_players": lobby.participants.count(),
        "is_host": (request.user == lobby.host),
    }
    return render(request, "game/round_intermission.html", context)


@update_app
def toggle_round_ready(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    if request.user not in lobby.red_team.all() and request.user not in lobby.blue_team.all():
        return JsonResponse({'error': 'Lütfen önce bir takım seçin.'}, status=400)
    if request.method == "POST":
        if request.user not in lobby.round_ready_players.all():
            lobby.round_ready_players.add(request.user)
            lobby.save()
        ready_count = lobby.round_ready_players.count()
        total = lobby.participants.count()
        if ready_count == total:
            set_round_end(lobby, 60)
            lobby.save()
            return JsonResponse({
                "status": "all_ready",
                "ready_count": ready_count,
                "redirect": f"/game_view/{lobby_id}/"
            })
        return JsonResponse({
            "status": "waiting",
            "ready_count": ready_count
        })
    return JsonResponse({"error": "Invalid request"}, status=400)

@update_app
def poll_round_ready(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    ready_count = lobby.round_ready_players.count()
    total = lobby.participants.count()
    all_ready = (ready_count == total)
    data = {
         "ready_count": ready_count,
         "total": total,
         "all_ready": all_ready,
    }
    return JsonResponse(data)

@update_app
def explainer_screen(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    res = handle_round_end(request, lobby)
    if res:
        return res
    if lobby.current_explainer != request.user:
        messages.error(request, "Bu sayfaya erişim izniniz yok.")
        return redirect('lobby', lobby_id=lobby.id)
    current_word_obj = lobby.current_word
    forbidden_list = current_word_obj.yasakli_kelimeler.all() if current_word_obj else []
    context = {
        "lobby": lobby,
        "word": current_word_obj.ana_kelime if current_word_obj else "Kelime Yok",
        "forbidden_words": [y.kelime for y in forbidden_list],
        "red_score": lobby.red_score,
        "blue_score": lobby.blue_score,
        "round_end": lobby.round_end,
    }
    return render(request, "game/explainer_screen.html", context)

@update_app
def teammate_screen(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    return render(request, "game/teammate_screen.html", {
        "lobby": lobby,
        "red_score": lobby.red_score,
        "blue_score": lobby.blue_score,
        "round_end": lobby.round_end,
    })

@update_app
def opponent_screen(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    current_word_obj = lobby.current_word
    forbidden_list = current_word_obj.yasakli_kelimeler.all() if current_word_obj else []
    return render(request, "game/opponent_screen.html", {
        "lobby": lobby,
        "word": current_word_obj.ana_kelime if current_word_obj else "Kelime Yok",
        "forbidden_words": [y.kelime for y in forbidden_list],
        "red_score": lobby.red_score,
        "blue_score": lobby.blue_score,
        "round_end": lobby.round_end,
    })

@update_app
def leave_game(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    if request.user in lobby.participants.all():
        lobby.participants.remove(request.user)
    if request.user in lobby.red_team.all():
        lobby.red_team.remove(request.user)
    if request.user in lobby.blue_team.all():
        lobby.blue_team.remove(request.user)
    if request.user in lobby.ready_players.all():
        lobby.ready_players.remove(request.user)
    if lobby.participants.count() == 0:
        lobby.delete()
        messages.info(request, "Oyundan çıktınız. Lobi boş kaldığı için silindi.")
    else:
        messages.info(request, "Oyundan çıktınız.")
    return redirect('home')


# 5. SOSYAL İŞLEMLER (ARKADAŞLIK & BİLDİRİMLER)


@update_app
def accept_request(request, request_id):
    if request.method == 'POST':
        friend_req = get_object_or_404(FriendRequest, id=request_id, receiver=request.user)
        if friend_req.status == 'pending':
            friend_req.status = 'accepted'
            friend_req.save()
            if friend_req.lobby_invite:
                lobby = friend_req.lobby_invite
                lobby.participants.add(request.user)
                messages.success(request, f"Lobiye katıldınız (Lobi ID: {lobby.id}).")
            else:
                request.user.friends.add(friend_req.sender)
                friend_req.sender.friends.add(request.user)
                messages.success(request, f"{friend_req.sender.username} ile artık arkadaşsınız.")
    return redirect('home')

@update_app
def reject_request(request, request_id):
    if request.method == 'POST':
        friend_req = get_object_or_404(FriendRequest, id=request_id, receiver=request.user)
        friend_req.status = 'rejected'
        friend_req.save()
        messages.info(request, f"{friend_req.sender.username} isteğini reddettiniz.")
    return redirect('home')

@update_app
def add_friend(request):
    if request.method == 'POST':
        friend_username = request.POST.get('friend_username')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            receiver = User.objects.get(username=friend_username)
            if receiver == request.user:
                messages.error(request, "Kendinize istek gönderemezsiniz.")
                return redirect('home')
            existing_req = FriendRequest.objects.filter(
                sender=request.user,
                receiver=receiver,
                status='pending',
                lobby_invite__isnull=True
            ).first()
            if existing_req:
                messages.error(request, "Zaten bu kullanıcıya istek gönderdiniz.")
                return redirect('home')
            FriendRequest.objects.create(sender=request.user, receiver=receiver)
            messages.success(request, f"{friend_username} adlı kullanıcıya arkadaşlık isteği gönderildi.")
        except User.DoesNotExist:
            messages.error(request, "Böyle bir kullanıcı bulunamadı.")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"message": f"{friend_username} adlı kullanıcıya isteğiniz gönderildi."})
        return redirect('home')
    return redirect('home')

@update_app
def notifications_view(request):
    pending_requests = FriendRequest.objects.filter(receiver=request.user, status='pending')
    notifications = []
    for req in pending_requests:
        if req.lobby_invite:
            msg = f"{req.sender.username} seni Lobi #{req.lobby_invite.id}'e davet etti."
        else:
            msg = f"{req.sender.username} sana arkadaşlık isteği gönderdi."
        notifications.append({
            "sender": req.sender.username,
            "friend_request_id": req.id,
            "message": msg
        })
    return JsonResponse({"notifications": notifications})

@update_app
def mark_ready(request):
    if request.method == 'POST':
        request.user.is_ready = True
        request.user.save()
        return JsonResponse({'status': 'ready'})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@update_app
def game_over(request):
    lobby_id = request.GET.get("lobby_id")
    if not lobby_id:
        return render(request, "game/game_over.html", {
            "red_score": 0,
            "blue_score": 0,
            "winner": "Bilinmiyor"
        })

    lobby = get_object_or_404(Lobby, id=lobby_id)
    red_score = lobby.red_score,
    blue_score = lobby.blue_score, 

    if red_score == 0 and blue_score == 0:
        winner = "Bilinmiyor"
    elif red_score > blue_score:
        winner = "Kırmızı Takım"
    elif blue_score > red_score:
        winner = "Mavi Takım"
    else:
        winner = "Berabere"

    return render(request, "game/game_over.html", {
        "red_score": red_score,
        "blue_score": blue_score,
        "winner": winner
    })


@update_app
def toggle_ready(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    
    if request.user not in lobby.red_team.all() and request.user not in lobby.blue_team.all():
        return JsonResponse({'error': 'Lütfen önce bir takım seçin.'}, status=400)
    
    if request.user in lobby.ready_players.all():
        lobby.ready_players.remove(request.user)
        is_ready = False
    else:
        lobby.ready_players.add(request.user)
        is_ready = True

    
    participants = list(lobby.participants.all())
    all_ready = all(player in lobby.ready_players.all() for player in participants)
    if all_ready:
        
        redirects = {}
        for player in participants:
            if player == lobby.current_explainer:
                redirects[player.username] = f"/explainer_screen/{lobby.id}/"
            else:
                if (player in lobby.red_team.all() and lobby.current_explainer in lobby.red_team.all()) or \
                   (player in lobby.blue_team.all() and lobby.current_explainer in lobby.blue_team.all()):
                    redirects[player.username] = f"/teammate_screen/{lobby.id}/"
                else:
                    redirects[player.username] = f"/opponent_screen/{lobby.id}/"
        return JsonResponse({
            'status': 'all_ready',
            'redirects': redirects
        })
    if is_ready:
        return JsonResponse({
            'status': 'waiting_room',
            'redirect': f'/waiting_room/{lobby.id}/'
        })
    return JsonResponse({
        'status': 'waiting',
        'ready_state': is_ready
    })


@update_app
def poll_lobby(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    participants = list(lobby.participants.all())
    all_ready = all(player in lobby.ready_players.all() for player in participants)
    participants_data = [{
        "id": p.id,
        "username": p.username,
        "is_ready": (p in lobby.ready_players.all())
    } for p in participants]

    data = {
        "host_username": lobby.host.username,
        "is_host": (request.user == lobby.host),
        "participants": participants_data,
        "red_count": lobby.red_team.count(),
        "blue_count": lobby.blue_team.count(),
        "all_ready": all_ready
    }
    
    if all_ready:
        data["redirect"] = f"/round_intermission/{lobby.id}/"
        data["status"] = "all_ready"
    
    return JsonResponse(data, safe=False)


@update_app
def invite_lobby(request, lobby_id):
    lobby = get_object_or_404(Lobby, id=lobby_id)
    if request.user not in lobby.participants.all():
        messages.error(request, "Bu lobiye erişim izniniz yok.")
        return redirect('home')
    if request.method == 'POST':
        friend_username = request.POST.get('username')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            friend_user = User.objects.get(username=friend_username)
        except User.DoesNotExist:
            messages.error(request, "Böyle bir kullanıcı bulunamadı.")
            return redirect('lobby', lobby_id=lobby_id)
        if friend_user not in request.user.friends.all():
            messages.error(request, "Bu kullanıcı senin arkadaşın değil. Önce arkadaş ekle.")
            return redirect('lobby', lobby_id=lobby_id)
        existing_req = FriendRequest.objects.filter(
            sender=request.user,
            receiver=friend_user,
            status='pending',
            lobby_invite=lobby
        ).first()
        if existing_req:
            messages.error(request, "Bu kullanıcıya bu lobi için zaten davet gönderdiniz.")
            return redirect('lobby', lobby_id=lobby_id)
        FriendRequest.objects.create(
            sender=request.user,
            receiver=friend_user,
            status='pending',
            lobby_invite=lobby
        )
        messages.success(request, f"{friend_user.username} adlı kullanıcıya lobi daveti gönderildi.")
        return redirect('lobby', lobby_id=lobby_id)
    return redirect('lobby', lobby_id=lobby_id)


