from .navigation import build_menu
from .permissions import is_gestao


def user_access(request):
    user = getattr(request, "user", None)
    return {"is_gestao": bool(user and is_gestao(user))}


def navigation(request):
    if not hasattr(request, "user"):
        return {"menu_groups": []}
    from drivers_app.context_processors import drivers_counts

    return {"menu_groups": build_menu(request, drivers_counts(request))}
