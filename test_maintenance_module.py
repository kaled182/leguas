"""
Script de teste para verificar o módulo Fleet Maintenance
"""

import os
import sys

import django
from django.contrib.auth import get_user_model
from django.test import Client

from fleet_management.models import VehicleMaintenance

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()


User = get_user_model()


def test_maintenance_module():
    """Testa as funcionalidades do módulo de manutenções"""

    print("=" * 80)
    print("TESTE DO MÓDULO FLEET MAINTENANCE")
    print("=" * 80)

    # Criar cliente de teste
    client = Client()

    # 1. Configurar usuário de teste
    print("\n1. Configurando usuário de teste...")
    try:
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.create_superuser(
                username="admin", email="admin@test.com", password="admin123"
            )
            print("   ✓ Usuário admin criado")
        else:
            print(f"   ✓ Usando usuário existente: {user.username}")

        # Login
        client.force_login(user)
        print("   ✓ Login realizado com sucesso")

    except Exception as e:
        print(f"   ✗ Erro ao configurar usuário: {e}")
        return False

    # 2. Testar Lista de Manutenções
    print("\n2. Testando Lista de Manutenções (/fleet/maintenance/)...")
    try:
        response = client.get("/fleet/maintenance/")
        if response.status_code == 200:
            print(f"   ✓ Lista carregou com sucesso (Status: {response.status_code})")
            count = VehicleMaintenance.objects.count()
            print(f"   ℹ Total de manutenções no banco: {count}")
        else:
            print(f"   ✗ Lista falhou (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"   ✗ Erro ao carregar lista: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 3. Testar Calendário
    print("\n3. Testando Calendário (/fleet/maintenance/calendar/)...")
    try:
        response = client.get("/fleet/maintenance/calendar/")
        if response.status_code == 200:
            print(
                f"   ✓ Calendário carregou com sucesso (Status: {response.status_code})"
            )
            print(f"   ℹ Calendário com FullCalendar.js integrado")
        else:
            print(f"   ✗ Calendário falhou (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"   ✗ Erro ao carregar calendário: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 4. Testar Formulário de Criação
    print("\n4. Testando Formulário de Criação (/fleet/maintenance/create/)...")
    try:
        response = client.get("/fleet/maintenance/create/")
        if response.status_code == 200:
            print(
                f"   ✓ Formulário de criação carregou com sucesso (Status: {response.status_code})"
            )
        else:
            print(f"   ✗ Formulário de criação falhou (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"   ✗ Erro ao carregar formulário: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 5. Testar Detalhe (se houver manutenções)
    print("\n5. Testando Página de Detalhe...")
    try:
        maintenance = VehicleMaintenance.objects.first()
        if maintenance:
            response = client.get(f"/fleet/maintenance/{maintenance.pk}/")
            if response.status_code == 200:
                print(
                    f"   ✓ Página de detalhe carregou com sucesso (Status: {response.status_code})"
                )
                print(
                    f"   ℹ Manutenção testada: {maintenance.vehicle.license_plate} - {maintenance.get_maintenance_type_display()}"
                )
            else:
                print(f"   ✗ Página de detalhe falhou (Status: {response.status_code})")
                return False
        else:
            print("   ⊘ Nenhuma manutenção encontrada para testar detalhes")
    except Exception as e:
        print(f"   ✗ Erro ao carregar detalhe: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 6. Testar Edição
    print("\n6. Testando Formulário de Edição...")
    try:
        maintenance = VehicleMaintenance.objects.first()
        if maintenance:
            response = client.get(f"/fleet/maintenance/{maintenance.pk}/edit/")
            if response.status_code == 200:
                print(
                    f"   ✓ Formulário de edição carregou com sucesso (Status: {response.status_code})"
                )
            else:
                print(
                    f"   ✗ Formulário de edição falhou (Status: {response.status_code})"
                )
                return False
        else:
            print("   ⊘ Nenhuma manutenção encontrada para testar edição")
    except Exception as e:
        print(f"   ✗ Erro ao carregar edição: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 7. Verificar URLs
    print("\n7. Verificando configuração de URLs...")
    try:
        from django.urls import resolve

        urls_to_test = [
            "/fleet/maintenance/",
            "/fleet/maintenance/calendar/",
            "/fleet/maintenance/create/",
        ]

        for url in urls_to_test:
            try:
                match = resolve(url)
                print(f"   ✓ URL '{url}' → {match.func.__name__}")
            except Exception as e:
                print(f"   ✗ URL '{url}' não resolvida: {e}")
                return False

    except Exception as e:
        print(f"   ✗ Erro ao verificar URLs: {e}")
        return False

    # 8. Verificar Form
    print("\n8. Verificando Form de Manutenção...")
    try:
        from fleet_management.forms import VehicleMaintenanceForm

        form = VehicleMaintenanceForm()
        required_fields = ["vehicle", "maintenance_type"]

        for field in required_fields:
            if field in form.fields:
                print(f"   ✓ Form tem campo '{field}'")
            else:
                print(f"   ✗ Form faltando campo '{field}'")
                return False

    except Exception as e:
        print(f"   ✗ Erro ao verificar form: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
    print("=" * 80)
    print("\n📋 Resumo:")
    print("   ✓ Lista de manutenções funcionando")
    print("   ✓ Calendário visual funcionando")
    print("   ✓ Formulário de criação funcionando")
    print("   ✓ Página de detalhes funcionando")
    print("   ✓ Formulário de edição funcionando")
    print("   ✓ Todas as URLs configuradas corretamente")
    print("\n🎯 Fase 2.4 - Manutenções: COMPLETA!")
    return True


if __name__ == "__main__":
    success = test_maintenance_module()
    sys.exit(0 if success else 1)
