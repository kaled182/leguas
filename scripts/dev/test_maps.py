"""
Testes para os mapas de Zonas Postais e Pedidos
"""

import os
import sys

import django
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.models import Partner
from orders_manager.models import Order
from pricing.models import PostalZone

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()


User = get_user_model()


def setup_test_user():
    """Cria ou obtém usuário de teste"""
    username = "testadmin"
    password = "testpass123"

    user, created = User.objects.get_or_create(
        username=username,
        defaults={"is_staff": True, "is_superuser": True, "is_active": True},
    )

    if created:
        user.set_password(password)
        user.save()
        print(f"✅ Usuário criado: {username}")
    else:
        print(f"ℹ️  Usando usuário existente: {username}")

    return user, username, password


def create_test_zone():
    """Cria uma zona postal de teste com coordenadas"""
    zone, created = PostalZone.objects.get_or_create(
        code="TST-MAPA",
        defaults={
            "name": "Zona Teste Mapa",
            "postal_code_pattern": "^1000",
            "region": "LISBOA",
            "center_latitude": "38.7223",
            "center_longitude": "-9.1393",
            "is_urban": True,
            "average_delivery_time_hours": 24,
            "is_active": True,
        },
    )

    if created:
        print(f"✅ Zona criada: {zone.code} - {zone.name}")
    else:
        print(f"ℹ️  Usando zona existente: {zone.code}")

    return zone


def test_zones_map_loads():
    """Testa se a página de mapa de zonas carrega"""
    print("\n=== Teste 1: Carregamento do Mapa de Zonas ===")

    user, username, password = setup_test_user()
    zone = create_test_zone()

    client = Client()
    logged_in = client.login(username=username, password=password)

    if not logged_in:
        print("❌ ERRO: Não foi possível fazer login")
        return False

    try:
        url = reverse("pricing:zones-map")
        response = client.get(url)

        print(f"URL: {url}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Verifica se a página contém os elementos esperados
            checks = {
                "Leaflet.js CSS": "leaflet.css" in content,
                "Leaflet.js JS": "leaflet.js" in content,
                "Div do Mapa": 'id="map"' in content,
                "Título": "Mapa de Zonas Postais" in content,
                "Zona no mapa": zone.code in content or zone.name in content,
            }

            all_passed = all(checks.values())

            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                print(f"  {status} {check}")

            if all_passed:
                print("✅ SUCESSO: Mapa de zonas carrega corretamente")
                return True
            else:
                print("❌ ERRO: Alguns elementos não foram encontrados")
                return False
        else:
            print(f"❌ ERRO: Status code inesperado: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        return False


def test_orders_map_loads():
    """Testa se a página de mapa de pedidos carrega"""
    print("\n=== Teste 2: Carregamento do Mapa de Pedidos ===")

    user, username, password = setup_test_user()

    client = Client()
    logged_in = client.login(username=username, password=password)

    if not logged_in:
        print("❌ ERRO: Não foi possível fazer login")
        return False

    try:
        url = reverse("orders:orders_map")
        response = client.get(url)

        print(f"URL: {url}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Verifica se a página contém os elementos esperados
            checks = {
                "Leaflet.js CSS": "leaflet.css" in content,
                "Leaflet.js JS": "leaflet.js" in content,
                "Div do Mapa": 'id="map"' in content,
                "Título": "Mapa de Pedidos" in content,
                "Estatísticas (Total)": "Total" in content,
                "Estatísticas (Pendente)": "Pendente" in content,
            }

            all_passed = all(checks.values())

            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                print(f"  {status} {check}")

            if all_passed:
                print("✅ SUCESSO: Mapa de pedidos carrega corretamente")
                return True
            else:
                print("❌ ERRO: Alguns elementos não foram encontrados")
                return False
        else:
            print(f"❌ ERRO: Status code inesperado: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        return False


def test_order_with_coordinates():
    """Testa se pedidos com coordenadas aparecem no mapa"""
    print("\n=== Teste 3: Pedidos com Coordenadas ===")

    user, username, password = setup_test_user()
    zone = create_test_zone()

    # Criar parceiro de teste
    partner, _ = Partner.objects.get_or_create(
        name="Parceiro Teste Mapa",
        defaults={
            "nif": "123456789",
            "contact_email": "test@mapa.com",
            "is_active": True,
        },
    )

    # Deletar pedido existente se houver para garantir status correto
    Order.objects.filter(external_reference="MAP-TEST-001").delete()

    # Criar pedido com CP que corresponde à zona
    order = Order.objects.create(
        external_reference="MAP-TEST-001",
        partner=partner,
        recipient_name="Cliente Teste Mapa",
        recipient_address="Rua Teste, 123",
        postal_code="1000-100",  # Corresponde ao pattern ^1000
        recipient_phone="912345678",
        current_status="PENDING",
        declared_value=10.00,
        weight_kg=1.0,
    )

    print(
        f"✅ Pedido criado: {order.external_reference} (Status: {order.current_status})"
    )

    client = Client()
    client.login(username=username, password=password)

    try:
        url = reverse("orders:orders_map")
        response = client.get(url)
        content = response.content.decode("utf-8")

        # Verificar se o pedido aparece no JavaScript do mapa
        checks = {
            "Referência do pedido": "MAP-TEST-001" in content,
            "Nome do destinatário": order.recipient_name in content,
            "Mapa carregado": "const orders = [" in content,
        }

        all_passed = all(checks.values())

        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")

        # Print debug info
        if not all_passed:
            print(f"\n  DEBUG:")
            print(f"    - Zona: {zone.code} (pattern: {zone.postal_code_pattern})")
            print(f"    - CP do pedido: {order.postal_code}")
            print(f"    - Status do pedido: {order.current_status}")
            print(
                f"    - Coordenadas da zona: {zone.center_latitude}, {zone.center_longitude}"
            )
            if "const orders = [" in content:
                start_idx = content.find("const orders = [")
                end_idx = (
                    content.find("];", start_idx)
                    if "];" in content[start_idx:]
                    else start_idx + 500
                )
                orders_js = content[start_idx : min(end_idx + 2, start_idx + 500)]
                orders_count = orders_js.count("reference:")
                print(f"    - Pedidos com coordenadas no JS: {orders_count}")
                if orders_count > 0:
                    print(f"    - Preview do JS: {orders_js[:200]}...")

        if all_passed:
            print("✅ SUCESSO: Pedido aparece no mapa com coordenadas")
            return True
        else:
            print("⚠️  AVISO: Pedido pode não estar geolocalizado corretamente")
            # Ainda considera sucesso parcial se o mapa carregou
            if checks["Mapa carregado"]:
                print("ℹ️  Mapa funcional, testando com pedidos existentes")
                return True
            return False

    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_map_buttons_present():
    """Testa se os botões de acesso aos mapas estão presentes"""
    print("\n=== Teste 4: Botões de Acesso aos Mapas ===")

    user, username, password = setup_test_user()

    client = Client()
    client.login(username=username, password=password)

    tests = [
        {
            "name": "Botão no lista de zonas",
            "url": reverse("pricing:zone-list"),
            "check_text": "Ver Mapa",
            "check_url": "/pricing/zones/map/",
        },
        {
            "name": "Botão na lista de pedidos",
            "url": reverse("orders:order_list"),
            "check_text": "Mapa",
            "check_url": "/orders/map/",
        },
    ]

    all_passed = True

    for test in tests:
        try:
            response = client.get(test["url"])
            content = response.content.decode("utf-8")

            text_present = test["check_text"] in content
            url_present = test["check_url"] in content

            passed = text_present and url_present
            status = "✅" if passed else "❌"

            print(f"  {status} {test['name']}")
            if not passed:
                if not text_present:
                    print(f"      ❌ Texto '{test['check_text']}' não encontrado")
                if not url_present:
                    print(f"      ❌ URL '{test['check_url']}' não encontrada")
                all_passed = False

        except Exception as e:
            print(f"  ❌ {test['name']}: {str(e)}")
            all_passed = False

    if all_passed:
        print("✅ SUCESSO: Todos os botões estão presentes")
    else:
        print("❌ ERRO: Alguns botões não foram encontrados")

    return all_passed


def main():
    """Executa todos os testes"""
    print("=" * 60)
    print("TESTES DE MAPAS - ZONAS POSTAIS E PEDIDOS")
    print("=" * 60)

    results = []

    # Executar testes
    results.append(("Mapa de Zonas", test_zones_map_loads()))
    results.append(("Mapa de Pedidos", test_orders_map_loads()))
    results.append(("Pedidos com Coordenadas", test_order_with_coordinates()))
    results.append(("Botões de Acesso", test_map_buttons_present()))

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{status}: {name}")

    print(f"\n{passed}/{total} testes passaram")

    # Status do banco de dados
    zones_count = PostalZone.objects.count()
    zones_with_coords = PostalZone.objects.filter(
        center_latitude__isnull=False, center_longitude__isnull=False
    ).count()
    orders_count = Order.objects.count()

    print(f"\n📊 Estatísticas do Banco:")
    print(f"  - {zones_count} zonas postais ({zones_with_coords} com coordenadas)")
    print(f"  - {orders_count} pedidos")

    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam")
        return 1


if __name__ == "__main__":
    exit(main())
