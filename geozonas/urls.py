from django.urls import path

from . import views

app_name = "geozonas"

urlpatterns = [
    path("api/zonas/export/", views.api_zonas_export, name="api-zonas-export"),
]
