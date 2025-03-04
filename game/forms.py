from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()  # AUTH_USER_MODEL = 'game.Oyuncu'
        fields = ("username", "email", "password1", "password2")
