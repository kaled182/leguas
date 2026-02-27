#!/usr/bin/env python
"""
Script para configurar Typebot rapidamente
"""
import os
import sys
import django
import secrets

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from system_config.models import SystemConfiguration

def configure_typebot():
    """Configura Typebot com valores padrão"""
    config = SystemConfiguration.get_config()
    
    print("📝 Configurando Typebot...")
    
    # Configurações básicas
    config.typebot_enabled = True
    config.typebot_builder_url = "http://localhost:8081"
    config.typebot_viewer_url = "http://localhost:8082"
    
    # Credenciais admin (ajuste conforme necessário)
    config.typebot_admin_email = "admin@leguasfranzinas.pt"
    config.typebot_admin_password = "admin123"  # ALTERAR EM PRODUÇÃO!
    
    # Gerar encryption secret
    config.typebot_encryption_secret = secrets.token_hex(32)
    print(f"🔐 Encryption secret gerado: {config.typebot_encryption_secret}")
    
    # Database URL (ajuste conforme docker-compose)
    config.typebot_database_url = "postgresql://typebot:typebot@leguas_typebot_db:5432/typebot"
    
    # Configurações de segurança
    config.typebot_disable_signup = True
    config.typebot_default_workspace_plan = "free"
    
    # Salvar
    config.save()
    
    print("✅ Typebot configurado com sucesso!")
    print("\nConfigurações aplicadas:")
    print(f"  • Enabled: {config.typebot_enabled}")
    print(f"  • Builder URL: {config.typebot_builder_url}")
    print(f"  • Viewer URL: {config.typebot_viewer_url}")
    print(f"  • Admin Email: {config.typebot_admin_email}")
    print(f"  • Database: {config.typebot_database_url}")
    print(f"  • Disable Signup: {config.typebot_disable_signup}")
    print(f"  • Workspace Plan: {config.typebot_default_workspace_plan}")
    print("\n🌐 Acesse: http://localhost:8000/system/ para ver as configurações")

if __name__ == '__main__':
    configure_typebot()
