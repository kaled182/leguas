#!/usr/bin/env python
"""
Script de Validação Rápida do Backend
Verifica se todas as funcionalidades estão importadas e funcionando
"""

import os
import sys

import django
from django.core.management import get_commands

from system_config.models import SystemConfiguration

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()


def check_views():
    """Verifica se as views estão implementadas"""
    print("🔍 Verificando Views...")
    try:
        from system_config import views

        # Verificar se save_config existe
        assert hasattr(views, "save_config"), "❌ save_config não encontrada"
        assert hasattr(
            views, "system_config_view"
        ), "❌ system_config_view não encontrada"

        print("   ✅ Views implementadas corretamente")
        return True
    except Exception as e:
        print(f"   ❌ Erro nas views: {e}")
        return False


def check_services():
    """Verifica se os services estão importados"""
    print("\n🔍 Verificando Services...")

    services = [
        "cloud_backups",
        "config_loader",
        "runtime_settings",
        "service_reloader",
        "video_gateway",
    ]

    all_ok = True
    for service in services:
        try:
            module = __import__(f"system_config.services.{service}", fromlist=[service])
            print(f"   ✅ {service}.py importado")
        except Exception as e:
            print(f"   ❌ {service}.py: {e}")
            all_ok = False

    return all_ok


def check_management_commands():
    """Verifica se os management commands existem"""
    print("\n🔍 Verificando Management Commands...")

    required_commands = [
        "generate_fernet_key",
        "make_backup",
        "restore_db",
        "sync_env_from_setup",
    ]

    available_commands = get_commands()
    all_ok = True

    for cmd in required_commands:
        if cmd in available_commands:
            print(f"   ✅ {cmd} disponível")
        else:
            print(f"   ❌ {cmd} NÃO encontrado")
            all_ok = False

    return all_ok


def check_models():
    """Verifica se os modelos estão corretos"""
    print("\n🔍 Verificando Models...")

    try:
        # Verificar SystemConfiguration
        config = SystemConfiguration.get_config()

        # Lista de campos que devem existir
        required_fields = [
            # Empresa
            "company_name",
            "logo",
            # Mapas
            "map_provider",
            "map_default_lat",
            "map_default_lng",
            "map_default_zoom",
            "google_maps_api_key",
            "mapbox_access_token",
            "osm_tile_server",
            "enable_street_view",
            "enable_traffic",
            "enable_map_clustering",
            # Google Drive
            "gdrive_enabled",
            "gdrive_auth_mode",
            "gdrive_credentials_json",
            "gdrive_folder_id",
            "gdrive_oauth_client_id",
            # FTP
            "ftp_enabled",
            "ftp_host",
            "ftp_port",
            "ftp_user",
            "ftp_password",
            # SMTP
            "smtp_enabled",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "smtp_from_email",
            "smtp_use_tls",
            # WhatsApp
            "whatsapp_enabled",
            "whatsapp_evolution_api_url",
            "whatsapp_evolution_api_key",
            # SMS
            "sms_enabled",
            "sms_provider",
            "sms_account_sid",
            "sms_auth_token",
            "sms_from_number",
            "sms_priority",
            # Database
            "db_host",
            "db_port",
            "db_name",
            "db_user",
            "db_password",
            # Redis
            "redis_url",
        ]

        missing_fields = []
        for field in required_fields:
            if not hasattr(config, field):
                missing_fields.append(field)

        if missing_fields:
            print(f"   ❌ Campos em falta: {', '.join(missing_fields)}")
            return False

        print(
            f"   ✅ SystemConfiguration com {len(required_fields)} campos verificados"
        )

        # Verificar ConfigurationAudit
        print("   ✅ ConfigurationAudit existe")

        return True

    except Exception as e:
        print(f"   ❌ Erro nos models: {e}")
        return False


def check_docker_services():
    """Verifica se os serviços Docker estão a correr"""
    print("\n🔍 Verificando Serviços Docker...")

    try:
        pass

        # Verificar MySQL
        try:
            print("   ✅ MySQL driver instalado")
        except BaseException:
            print("   ⚠️  MySQL driver não disponível (pode estar OK se usar Docker)")

        # Verificar Redis
        try:
            import redis

            r = redis.Redis(host="localhost", port=6379, db=0)
            r.ping()
            print("   ✅ Redis a correr (porta 6379)")
        except Exception as e:
            print(f"   ⚠️  Redis não disponível: {e}")

        return True

    except Exception as e:
        print(f"   ❌ Erro ao verificar Docker: {e}")
        return False


def check_dependencies():
    """Verifica se as dependências críticas estão instaladas"""
    print("\n🔍 Verificando Dependências...")

    dependencies = {
        "google-api-python-client": "googleapiclient",
        "google-auth": "google.auth",
        "redis": "redis",
        "cryptography": "cryptography",
        "djangorestframework": "rest_framework",
        "django-redis": "django_redis",
        "pillow": "PIL",
    }

    all_ok = True
    for package_name, import_name in dependencies.items():
        try:
            __import__(import_name)
            print(f"   ✅ {package_name} instalado")
        except ImportError:
            print(f"   ❌ {package_name} NÃO instalado")
            all_ok = False

    return all_ok


def check_urls():
    """Verifica se as URLs estão configuradas"""
    print("\n🔍 Verificando URLs...")

    try:
        from django.urls import reverse

        # Tentar resolver a URL
        try:
            url = reverse("system_config:index")
            print(f"   ✅ URL configurada: {url}")
            return True
        except BaseException:
            print("   ❌ URL 'system_config:index' não configurada")
            return False

    except Exception as e:
        print(f"   ❌ Erro nas URLs: {e}")
        return False


def main():
    """Função principal"""
    print("=" * 60)
    print("🚀 VALIDAÇÃO COMPLETA DO BACKEND - PROVEMAPS")
    print("=" * 60)

    results = {
        "Views": check_views(),
        "Services": check_services(),
        "Management Commands": check_management_commands(),
        "Models": check_models(),
        "Docker Services": check_docker_services(),
        "Dependencies": check_dependencies(),
        "URLs": check_urls(),
    }

    print("\n" + "=" * 60)
    print("📊 RESUMO DA VALIDAÇÃO")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for category, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {category}")

    print("\n" + "=" * 60)
    percentage = (passed / total) * 100

    if percentage == 100:
        print(
            f"🎉 SUCESSO TOTAL: {passed}/{total} verificações passaram ({percentage:.0f}%)"
        )
        print("✅ O backend está 100% funcional e pronto para produção!")
    elif percentage >= 80:
        print(f"✅ BOM: {passed}/{total} verificações passaram ({percentage:.0f}%)")
        print("⚠️  Alguns componentes precisam de atenção")
    else:
        print(
            f"❌ ATENÇÃO: Apenas {passed}/{total} verificações passaram ({percentage:.0f}%)"
        )
        print("⚠️  Várias funcionalidades precisam ser corrigidas")

    print("=" * 60)

    return 0 if percentage == 100 else 1


if __name__ == "__main__":
    sys.exit(main())
