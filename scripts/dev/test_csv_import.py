#!/usr/bin/env python3
"""
Script de teste para funcionalidade de Import CSV (Zonas e Tarifas)
"""

import os
import sys
from io import StringIO

import django
from django.contrib.auth import get_user_model
from django.test import Client

from core.models import Partner
from pricing.models import PartnerTariff, PostalZone

# Configuração do Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")


django.setup()


User = get_user_model()

# ========== CONFIGURAÇÃO ==========


def setup_test_user():
    """Cria ou obtém usuário de teste"""
    user, created = User.objects.get_or_create(
        username="admin",
        defaults={
            "email": "admin@example.com",
            "is_staff": True,
            "is_superuser": True,
        },
    )
    if created:
        user.set_password("admin")
        user.save()
        print("✅ Usuário de teste criado")
    else:
        print("✅ Usuário de teste já existe")
    return user


def create_test_csv_zones():
    """Cria CSV de exemplo para zonas"""
    csv_content = """name,code,postal_code_pattern,region,center_latitude,center_longitude,is_urban,average_delivery_time_hours,is_active,notes
Lisboa Centro,LIS-CENTRO,^11\\d{2},LISBOA,38.736946,-9.142685,true,24,true,Zona central de Lisboa
Lisboa Norte,LIS-NORTE,^17\\d{2},LISBOA,38.758095,-9.155464,false,48,true,Zona norte de Lisboa
Porto Centro,PRT-CENTRO,^40\\d{2},NORTE,41.147374,-8.610826,true,24,true,Centro do Porto
Porto Sul,PRT-SUL,^44\\d{2},NORTE,41.137984,-8.617353,false,48,true,Zona sul do Porto
Faro Centro,FAR-CENTRO,^80\\d{2},ALGARVE,37.019356,-7.930833,true,72,true,Centro de Faro"""

    return csv_content


def create_test_csv_tariffs():
    """Cria CSV de exemplo para tarifas"""
    # Primeiro precisamos garantir que temos um parceiro
    partner, created = Partner.objects.get_or_create(
        name="Paack Portugal",
        defaults={
            "nif": "PT123456789",
            "contact_email": "portugal@paack.co",
            "contact_phone": "+351 210 123 456",
            "is_active": True,
        },
    )
    if created:
        print(f"✅ Parceiro '{partner.name}' criado para testes")

    csv_content = """partner_name,zone_code,base_price,success_bonus,failure_penalty,late_delivery_penalty,weekend_multiplier,express_multiplier,valid_from,valid_until,is_active,notes
Paack Portugal,LIS-CENTRO,2.50,0.50,1.00,0.75,1.2,1.5,2024-01-01,,true,Tarifa para Lisboa Centro
Paack Portugal,LIS-NORTE,2.00,0.40,1.00,0.75,1.2,1.5,2024-01-01,,true,Tarifa para Lisboa Norte
Paack Portugal,PRT-CENTRO,3.00,0.60,1.50,1.00,1.3,1.6,2024-01-01,,true,Tarifa para Porto Centro"""

    return csv_content


# ========== TESTES ==========


def test_zone_import_page():
    """Testa carregamento da página de import de zonas"""
    print("\n[1/6] Testando página de import de zonas...")
    client = Client()
    user = setup_test_user()
    client.force_login(user)

    response = client.get("/pricing/zones/import/")

    if response.status_code == 200:
        print(f"✅ Página de import de zonas carregou: HTTP {response.status_code}")
        if b"Importar Zonas Postais via CSV" in response.content:
            print("✅ Título correto encontrado")
        if b"Formato do CSV" in response.content:
            print("✅ Instruções encontradas")
        return True
    else:
        print(f"❌ Erro ao carregar página: HTTP {response.status_code}")
        return False


def test_zone_import_upload():
    """Testa upload e preview de CSV de zonas"""
    print("\n[2/6] Testando upload de CSV de zonas...")
    client = Client()
    user = setup_test_user()
    client.force_login(user)

    # Cria arquivo CSV temporário
    csv_content = create_test_csv_zones()
    csv_file = StringIO(csv_content)
    csv_file.name = "zones_test.csv"

    # Simula upload
    from django.core.files.uploadedfile import SimpleUploadedFile

    uploaded_file = SimpleUploadedFile(
        "zones_test.csv", csv_content.encode("utf-8"), content_type="text/csv"
    )

    response = client.post("/pricing/zones/import/", {"csv_file": uploaded_file})

    if response.status_code == 200:
        print(f"✅ Upload processado: HTTP {response.status_code}")
        if b"visualiza" in response.content.lower():
            print("✅ Preview gerado com sucesso")
            return True
        else:
            print("⚠️ Upload processado mas preview não encontrado")
            return False
    else:
        print(f"❌ Erro no upload: HTTP {response.status_code}")
        return False


def test_tariff_import_page():
    """Testa carregamento da página de import de tarifas"""
    print("\n[3/6] Testando página de import de tarifas...")
    client = Client()
    user = setup_test_user()
    client.force_login(user)

    response = client.get("/pricing/tariffs/import/")

    if response.status_code == 200:
        print(f"✅ Página de import de tarifas carregou: HTTP {response.status_code}")
        if b"Importar Tarifas via CSV" in response.content:
            print("✅ Título correto encontrado")
        return True
    else:
        print(f"❌ Erro ao carregar página: HTTP {response.status_code}")
        return False


def test_zone_list_import_button():
    """Testa se botão de importar está na lista de zonas"""
    print("\n[4/6] Testando botão 'Importar CSV' na lista de zonas...")
    client = Client()
    user = setup_test_user()
    client.force_login(user)

    response = client.get("/pricing/zones/")

    if response.status_code == 200:
        print(f"✅ Lista de zonas carregou: HTTP {response.status_code}")
        if (
            b"/pricing/zones/import/" in response.content
            or b"Importar CSV" in response.content
        ):
            print("✅ Botão 'Importar CSV' encontrado")
            return True
        else:
            print("⚠️ Botão 'Importar CSV' NÃO encontrado na lista")
            # Debug: Imprimir parte do HTML
            content_str = response.content.decode("utf-8")
            if "import" in content_str.lower():
                print(f"   🔍 Palavra 'import' encontrada no HTML")
            return False
    else:
        print(f"❌ Erro ao carregar lista: HTTP {response.status_code}")
        return False


def test_tariff_list_import_button():
    """Testa se botão de importar está na lista de tarifas"""
    print("\n[5/6] Testando botão 'Importar CSV' na lista de tarifas...")
    client = Client()
    user = setup_test_user()
    client.force_login(user)

    response = client.get("/pricing/tariffs/")

    if response.status_code == 200:
        print(f"✅ Lista de tarifas carregou: HTTP {response.status_code}")
        if (
            b"/pricing/tariffs/import/" in response.content
            or b"Importar CSV" in response.content
        ):
            print("✅ Botão 'Importar CSV' encontrado")
            return True
        else:
            print("⚠️ Botão 'Importar CSV' NÃO encontrado na lista")
            return False
    else:
        print(f"❌ Erro ao carregar lista: HTTP {response.status_code}")
        return False


def test_urls_registration():
    """Testa se as URLs de import estão registradas"""
    print("\n[6/6] Testando registro de URLs...")
    from django.urls import reverse

    try:
        url1 = reverse("pricing:zone-import")
        print(f"✅ URL zone-import registrada: {url1}")
    except BaseException:
        print("❌ URL pricing:zone-import NÃO encontrada")
        return False

    try:
        url2 = reverse("pricing:tariff-import")
        print(f"✅ URL tariff-import registrada: {url2}")
    except BaseException:
        print("❌ URL pricing:tariff-import NÃO encontrada")
        return False

    return True


# ========== MAIN ==========


def main():
    """Executa todos os testes"""
    print("=" * 70)
    print("TESTE: Import CSV - Zonas e Tarifas")
    print("=" * 70)

    results = []

    results.append(("URLs Registration", test_urls_registration()))
    results.append(("Zone Import Page", test_zone_import_page()))
    results.append(("Zone Import Upload", test_zone_import_upload()))
    results.append(("Tariff Import Page", test_tariff_import_page()))
    results.append(("Zone List Import Button", test_zone_list_import_button()))
    results.append(("Tariff List Import Button", test_tariff_list_import_button()))

    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES")
    print("=" * 70)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name:.<50} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print("=" * 70)
    print(f"Total: {passed + failed} | Passou: {passed} | Falhou: {failed}")
    print("=" * 70)

    # Estatísticas dos modelos
    print("\n📊 ESTATÍSTICAS:")
    print(f"  - Zonas Postais no DB: {PostalZone.objects.count()}")
    print(f"  - Tarifas no DB: {PartnerTariff.objects.count()}")
    print(f"  - Parceiros no DB: {Partner.objects.count()}")

    if failed == 0:
        print("\n🎉 Todos os testes passaram!")
        return 0
    else:
        print(f"\n⚠️ {failed} teste(s) falharam")
        return 1


if __name__ == "__main__":
    sys.exit(main())
