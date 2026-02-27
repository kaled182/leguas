"""
URLs para autenticação customizada.
"""

from django.urls import path
from .views import (
    authenticate_view, logout_view,
)

app_name = 'customauth'

urlpatterns = [
    # Autenticação geral
    path('', authenticate_view, name='authenticate'),
    path('authenticate/', authenticate_view, name='authenticate'),
    path('login/', authenticate_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
]