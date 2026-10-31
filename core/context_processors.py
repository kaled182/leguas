from pathlib import Path

from django.conf import settings

from .navigation import build_menu
from .permissions import is_gestao

_app_css = Path(settings.BASE_DIR) / "static/brand/app.css"
# Muda em cada build: o Caddy guarda os estáticos em cache por 30 dias.
ASSET_VERSION = int(_app_css.stat().st_mtime) if _app_css.exists() else 0


def user_access(request):
    user = getattr(request, "user", None)
    return {
        "is_gestao": bool(user and is_gestao(user)),
        "asset_version": ASSET_VERSION,
    }


def navigation(request):
    if not hasattr(request, "user"):
        return {"menu_groups": []}
    from dashboard_leguas.views_attention import attention_count
    from drivers_app.context_processors import drivers_counts

    counts = dict(drivers_counts(request))
    user = request.user
    if user.is_authenticated and user.is_staff:
        counts["attention_count"] = attention_count(request)
    return {"menu_groups": build_menu(request, counts)}
