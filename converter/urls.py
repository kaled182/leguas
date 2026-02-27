from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.converter_view, name='converter'),
    path('', include('converter.urls_geoapi')),
]

