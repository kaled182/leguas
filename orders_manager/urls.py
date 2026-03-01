from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    # Dashboard
    path("", views.orders_dashboard, name="dashboard"),
    path("dashboard/", views.orders_dashboard, name="orders_dashboard"),
    # Lista e CRUD
    path("list/", views.order_list, name="order_list"),
    path("map/", views.orders_map, name="orders_map"),
    path("<int:pk>/", views.order_detail, name="order_detail"),
    path("create/", views.order_create, name="order_create"),
    path("<int:pk>/edit/", views.order_edit, name="order_edit"),
    # Ações
    path(
        "<int:pk>/assign-driver/",
        views.order_assign_driver,
        name="order_assign_driver",
    ),
    path(
        "<int:pk>/change-status/",
        views.order_change_status,
        name="order_change_status",
    ),
    path(
        "<int:pk>/report-incident/",
        views.order_report_incident,
        name="order_report_incident",
    ),
]
