from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    # Zonas Postais
    path("zones/", views.zone_list, name="zone-list"),
    path("zones/create/", views.zone_create, name="zone-create"),
    path("zones/import/", views.zone_import_csv, name="zone-import"),
    path("zones/map/", views.zones_map, name="zones-map"),
    path("zones/<int:pk>/", views.zone_detail, name="zone-detail"),
    path("zones/<int:pk>/edit/", views.zone_edit, name="zone-edit"),
    path(
        "zones/<int:pk>/toggle-status/",
        views.zone_toggle_status,
        name="zone-toggle-status",
    ),
    # Tarifas
    path("tariffs/", views.tariff_list, name="tariff-list"),
    path("tariffs/create/", views.tariff_create, name="tariff-create"),
    path("tariffs/import/", views.tariff_import_csv, name="tariff-import"),
    path("tariffs/<int:pk>/", views.tariff_detail, name="tariff-detail"),
    path("tariffs/<int:pk>/edit/", views.tariff_edit, name="tariff-edit"),
    path(
        "tariffs/<int:pk>/toggle-status/",
        views.tariff_toggle_status,
        name="tariff-toggle-status",
    ),
    # Calculadora
    path("calculator/", views.price_calculator, name="price-calculator"),
]
