"""
Views para autenticação customizada de motoristas.

Este módulo contém:
- authenticate_view: Login de motoristas e gestores
- logout_view: Logout de motoristas e gestores
"""

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.db.models import Q
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from .models import DriverAccess
from django.core.paginator import Paginator
from django.utils import timezone
import openpyxl
from openpyxl.utils import get_column_letter
from geopy.geocoders import Nominatim
import folium
import re


@csrf_protect
@never_cache
def authenticate_view(request):
    """
    View para autenticação de gestores e motoristas.
    
    - Gestores: Login via username/email e senha (Django User)
    - Motoristas: Login via email/NIF e senha (DriverAccess)
    """
    if request.method == "GET":
        return render(request, "customauth/login.html")

    email_or_nif = request.POST.get("email_or_nif", "").strip()
    password = request.POST.get("password", "")
    
    if not email_or_nif or not password:
        messages.error(request, "Preencha todos os campos obrigatórios.")
        return render(request, "customauth/login.html")

    User = get_user_model()
    user = None

    # Tentar autenticar como gestor (Django User)
    user = authenticate(request, username=email_or_nif, password=password)
    if not user:
        try:
            user_obj = User.objects.get(email=email_or_nif)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

    if user and user.is_staff:
        login(request, user)
        messages.success(request, f"Bem-vindo, {user.first_name or user.username}!")
        return redirect("paack_dashboard:dashboard_paack")

    # Tentar autenticar como motorista (DriverAccess)
    try:
        driver = DriverAccess.objects.get(Q(email=email_or_nif) | Q(nif=email_or_nif))
        if driver.check_password(password):
            # Criar sessão customizada para motorista
            request.session["driver_access_id"] = driver.id
            request.session["driver_name"] = driver.full_name
            request.session["is_driver_authenticated"] = True
            
            messages.success(request, f"Bem-vindo, {driver.first_name}!")
            return redirect("drivers_app:driver_dashboard")
        else:
            messages.error(request, "Credenciais inválidas.")
    except DriverAccess.DoesNotExist:
        messages.error(request, "Credenciais inválidas.")

    return render(request, "customauth/login.html")


def logout_view(request):
    """
    View para logout de gestores e motoristas.
    
    Remove todas as sessões e redireciona para o login.
    """
    # Logout do Django (gestor)
    logout(request)
    
    # Limpar sessão do motorista
    request.session.pop("driver_access_id", None)
    request.session.pop("driver_name", None)
    request.session.pop("is_driver_authenticated", None)
    request.session.pop("driver_id", None)  # Compatibilidade com versão antiga
    
    messages.success(request, "Você foi desconectado com sucesso.")
    return redirect("customauth:authenticate")



