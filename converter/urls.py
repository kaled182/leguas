from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.converter_view, name="converter"),
    path("", include("converter.urls_geoapi")),
]
