"""Rotas da API da app do motorista — montadas em /api/app/v1/."""
from django.urls import path

from . import views

app_name = "app_api"

urlpatterns = [
    # Auth (OTP → token)
    path("auth/request-code", views.request_code, name="request_code"),
    path("auth/verify-code", views.verify_code, name="verify_code"),
    path("auth/logout", views.logout, name="logout"),
    # Perfil
    path("me", views.me, name="me"),
    # Faturas
    path("invoices", views.invoices, name="invoices"),
    path("invoices/<int:pk>", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/pdf", views.invoice_pdf, name="invoice_pdf"),
    # Descontos
    path("discounts", views.discounts, name="discounts"),
    # Reclamações
    path("complaints", views.complaints, name="complaints"),
]
