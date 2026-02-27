from django.urls import path
from . import views_geoapi

urlpatterns = [
    path('validate-addresses/', views_geoapi.validate_addresses, name='validate_addresses'),
]
