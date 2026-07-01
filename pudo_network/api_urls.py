"""Rotas da API PUDO para a app do estafeta — montadas em /api/app/v1/pudo/."""
from django.urls import path

from . import api

app_name = "pudo_api"

urlpatterns = [
    path("handshake", api.handshake, name="handshake"),
]
