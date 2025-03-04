def friend_list(request):
    if request.user.is_authenticated:
        friend_usernames = [friend.username for friend in request.user.friends.all()]
        return {'all_friends': friend_usernames}
    return {}


def notifications(request):
    if request.user.is_authenticated:
        from .models import FriendRequest
        pending_requests = FriendRequest.objects.filter(receiver=request.user, status='pending')
        return {'pending_requests': pending_requests}
    return {'pending_requests': []}

