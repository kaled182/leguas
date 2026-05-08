"""
URLs para autenticação customizada.
"""

from django.urls import path

from .views import (
    authenticate_view,
    logout_view,
)
from . import driver_auth_views, empresa_auth_views

app_name = "customauth"

urlpatterns = [
    # Autenticação geral (admin/staff)
    path("", authenticate_view, name="authenticate"),
    path("authenticate/", authenticate_view, name="authenticate"),
    path("login/", authenticate_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # ─── Login dedicado do motorista (Fase 1.4) ───
    path("driver/", driver_auth_views.driver_login, name="driver_login"),
    path("driver/login/", driver_auth_views.driver_login, name="driver_login_alias"),
    path("driver/logout/", driver_auth_views.driver_logout, name="driver_logout"),
    path(
        "driver/credentials/<int:driver_id>/",
        driver_auth_views.admin_driver_credentials,
        name="admin_driver_credentials",
    ),

    # ─── Login dedicado da empresa parceira (Fase 2C) ───
    path("empresa/", empresa_auth_views.empresa_login, name="empresa_login"),
    path("empresa/login/", empresa_auth_views.empresa_login, name="empresa_login_alias"),
    path("empresa/logout/", empresa_auth_views.empresa_logout, name="empresa_logout"),
    path(
        "empresa/credentials/<int:empresa_id>/",
        empresa_auth_views.admin_empresa_credentials,
        name="admin_empresa_credentials",
    ),
]
