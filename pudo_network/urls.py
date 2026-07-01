from django.urls import path

from . import views

app_name = "pudo_network"

urlpatterns = [
    path("", views.pudo_dashboard, name="dashboard"),
    path("login/", views.pudo_login, name="login"),
    path("logout/", views.pudo_logout, name="logout"),
    path("rececao/", views.pudo_reception, name="reception"),
    path("stock/", views.pudo_stock, name="stock"),
    path("pacote/<int:pk>/", views.pudo_pickup, name="pickup"),
    path("extrato/", views.pudo_billing, name="billing"),
]
