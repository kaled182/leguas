from django.urls import path

from . import views, views_admin

app_name = "pudo_network"

urlpatterns = [
    # Portal do lojista (sessão própria)
    path("", views.pudo_dashboard, name="dashboard"),
    path("login/", views.pudo_login, name="login"),
    path("logout/", views.pudo_logout, name="logout"),
    path("rececao/", views.pudo_reception, name="reception"),
    path("stock/", views.pudo_stock, name="stock"),
    path("pacote/<int:pk>/", views.pudo_pickup, name="pickup"),
    path("extrato/", views.pudo_billing, name="billing"),
    path("rececao-offline/", views.pudo_scan_offline, name="scan_offline"),

    # Gestão interna (staff) — padrão visual do dashboard
    path("gestao/", views_admin.gestao_list, name="gestao_list"),
    path("gestao/novo/", views_admin.gestao_create, name="gestao_create"),
    path("gestao/<int:pk>/", views_admin.gestao_detail, name="gestao_detail"),
    path("gestao/<int:pk>/editar/", views_admin.gestao_edit, name="gestao_edit"),
    path("gestao/<int:pk>/acesso/", views_admin.gestao_access, name="gestao_access"),
]
