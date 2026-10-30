from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render

from .permissions import is_gestao, is_portal, is_public, operator_can_access


class PermissionMiddleware:
    """Nega por omissão. PERMISSIONS_ENFORCE=0 desliga esta verificação."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.PERMISSIONS_ENFORCE and not self._allowed(request):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            return render(request, "403.html", status=403)
        return self.get_response(request)

    def _allowed(self, request):
        path = request.path
        if is_public(path):
            return True
        user = request.user
        if is_gestao(user):
            return True
        if user.is_authenticated and user.is_staff:
            return operator_can_access(path)
        return is_portal(path)
