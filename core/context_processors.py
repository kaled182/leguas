from .permissions import is_gestao


def user_access(request):
    user = getattr(request, "user", None)
    return {"is_gestao": bool(user and is_gestao(user))}
