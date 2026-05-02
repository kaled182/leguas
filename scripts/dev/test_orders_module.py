"""
Script de teste para verificar o módulo Orders Manager
"""

import os
import sys

import django
from django.contrib.auth import get_user_model
from django.test import Client

from orders_manager.models import Order

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()


User = get_user_model()


def test_orders_module():
    """Testa as principais funcionalidades do módulo Orders"""

    print("=" * 80)
    print("TESTE DO MÓDULO ORDERS MANAGER")
    print("=" * 80)

    # Criar cliente de teste
    client = Client()

    # 1. Criar usuário de teste (ou usar existente)
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

    # 2. Testar Dashboard
    print("\n2. Testando Dashboard de Pedidos (/orders/)...")
    try:
        response = client.get("/orders/")
        if response.status_code == 200:
            print(
                f"   ✓ Dashboard carregou com sucesso (Status: {response.status_code})"
            )
        else:
            print(f"   ✗ Dashboard falhou (Status: {response.status_code})")
            if response.status_code == 500:
                print(f"   Erro: {response.content[:500]}")
            return False
    except Exception as e:
        print(f"   ✗ Erro ao carregar dashboard: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 3. Testar Lista de Pedidos
    print("\n3. Testando Lista de Pedidos (/orders/list/)...")
    try:
        response = client.get("/orders/list/")
        if response.status_code == 200:
            order_count = Order.objects.count()
            print(f"   ✓ Lista carregou com sucesso (Status: {response.status_code})")
            print(f"   ℹ Total de pedidos no banco: {order_count}")
        else:
            print(f"   ✗ Lista falhou (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"   ✗ Erro ao carregar lista: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 4. Testar Página de Criação
    print("\n4. Testando Página de Criação (/orders/create/)...")
    try:
        response = client.get("/orders/create/")
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

    # 5. Testar Detalhe (se houver pedidos)
    print("\n5. Testando Página de Detalhe...")
    try:
        order = Order.objects.first()
        if order:
            response = client.get(f"/orders/{order.pk}/")
            if response.status_code == 200:
                print(
                    f"   ✓ Página de detalhe carregou com sucesso (Status: {response.status_code})"
                )
                print(f"   ℹ Pedido testado: {order.external_reference}")
            else:
                print(f"   ✗ Página de detalhe falhou (Status: {response.status_code})")
                return False
        else:
            print("   ⊘ Nenhum pedido encontrado para testar detalhes")
    except Exception as e:
        print(f"   ✗ Erro ao carregar detalhe: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 6. Verificar URLs no sistema
    print("\n6. Verificando configuração de URLs...")
    try:
        from django.urls import resolve

        urls_to_test = [
            "/orders/",
            "/orders/list/",
            "/orders/create/",
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

    # 7. Verificar Models
    print("\n7. Verificando Models...")
    try:
        from orders_manager.models import OrderIncident, OrderStatusHistory

        # Verificar campos do OrderStatusHistory
        history_fields = [f.name for f in OrderStatusHistory._meta.get_fields()]
        required_history_fields = ["status", "changed_by", "changed_at"]
        for field in required_history_fields:
            if field in history_fields:
                print(f"   ✓ OrderStatusHistory tem campo '{field}'")
            else:
                print(f"   ✗ OrderStatusHistory faltando campo '{field}'")
                return False

        # Verificar campos do OrderIncident
        incident_fields = [f.name for f in OrderIncident._meta.get_fields()]
        required_incident_fields = ["created_by", "created_at"]
        for field in required_incident_fields:
            if field in incident_fields:
                print(f"   ✓ OrderIncident tem campo '{field}'")
            else:
                print(f"   ✗ OrderIncident faltando campo '{field}'")
                return False

    except Exception as e:
        print(f"   ✗ Erro ao verificar models: {e}")
        import traceback

        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = test_orders_module()
    sys.exit(0 if success else 1)
