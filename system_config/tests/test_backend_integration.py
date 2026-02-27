"""
Testes de integração para validar que toda lógica do backend está funcionando
"""
import os
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from system_config.models import SystemConfiguration, ConfigurationAudit
from system_config.services.config_loader import ConfigLoader
from system_config.services.runtime_settings import RuntimeSettings

User = get_user_model()


class BackendIntegrationTest(TestCase):
    """Testes de integração do backend"""
    
    def setUp(self):
        """Setup inicial dos testes"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.client.login(username='testuser', password='testpass123')
        self.config = SystemConfiguration.get_config()
    
    def test_save_all_text_fields(self):
        """Testa se todos os campos de texto são salvos corretamente"""
        test_data = {
            # Empresa
            'company_name': 'Test Company Ltd',
            
            # Mapas - Básicos
            'map_provider': 'google',
            'map_default_lat': '38.7223',
            'map_default_lng': '-9.1393',
            'map_default_zoom': '12',
            'map_type': 'roadmap',
            'map_language': 'pt',
            'map_theme': 'light',
            'map_styles': '[]',
            
            # Mapas - APIs
            'google_maps_api_key': 'AIzaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
            'mapbox_access_token': 'pk.eyXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
            'mapbox_style': 'mapbox://styles/mapbox/streets-v11',
            'mapbox_custom_style': '',
            'esri_api_key': 'AAPKXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXx',
            'esri_basemap': 'arcgis-streets',
            'osm_tile_server': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            
            # Google Drive
            'gdrive_auth_mode': 'service_account',
            'gdrive_credentials_json': '{"type": "service_account"}',
            'gdrive_folder_id': '1ABC123XYZ',
            'gdrive_shared_drive_id': '',
            'gdrive_oauth_client_id': '',
            'gdrive_oauth_client_secret': '',
            'gdrive_oauth_refresh_token': '',
            'gdrive_oauth_user_email': '',
            
            # FTP
            'ftp_host': 'ftp.example.com',
            'ftp_port': '21',
            'ftp_user': 'ftpuser',
            'ftp_password': 'ftppass123',
            'ftp_directory': '/backups',
            
            # SMTP
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': '587',
            'smtp_security': 'STARTTLS',
            'smtp_user': 'noreply@example.com',
            'smtp_password': 'smtppass123',
            'smtp_auth_mode': 'password',
            'smtp_oauth_client_id': '',
            'smtp_oauth_client_secret': '',
            'smtp_oauth_refresh_token': '',
            'smtp_from_name': 'Léguas Franzinas',
            'smtp_from_email': 'noreply@leguasfranzinas.pt',
            'smtp_test_recipient': 'test@example.com',
            
            # WhatsApp
            'whatsapp_evolution_api_url': 'https://api.evolution.com',
            'whatsapp_evolution_api_key': 'evo_XXXXXXXXXXXXXXXXXXX',
            'whatsapp_instance_name': 'leguas_instance',
            
            # SMS
            'sms_provider': 'twilio',
            'sms_provider_rank': 'twilio,aws_sns,infobip',
            'sms_account_sid': 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            'sms_auth_token': 'your_auth_token_here',
            'sms_api_key': '',
            'sms_api_url': '',
            'sms_from_number': '+351910000000',
            'sms_test_recipient': '+351960000000',
            'sms_test_message': 'Teste de SMS',
            'sms_priority': 'high',
            'sms_aws_region': 'eu-west-1',
            'sms_aws_access_key_id': '',
            'sms_aws_secret_access_key': '',
            'sms_infobip_base_url': '',
            
            # Database
            'db_host': 'localhost',
            'db_port': '3306',
            'db_name': 'leguas_db',
            'db_user': 'leguas_user',
            'db_password': 'db_password',
            
            # Redis
            'redis_url': 'redis://localhost:6379/0',
        }
        
        # Fazer POST para salvar configurações
        response = self.client.post('/system-config/save/', test_data)
        
        # Verificar redirecionamento
        self.assertEqual(response.status_code, 302)
        
        # Recarregar configuração do banco
        config = SystemConfiguration.get_config()
        
        # Verificar se todos os campos foram salvos
        for field_name, expected_value in test_data.items():
            actual_value = getattr(config, field_name, None)
            self.assertEqual(
                str(actual_value) if actual_value else '',
                expected_value,
                f"Campo {field_name} não foi salvo corretamente"
            )
    
    def test_save_all_boolean_fields(self):
        """Testa se todos os campos booleanos são salvos corretamente"""
        test_data = {
            'company_name': 'Test Company',
            'gdrive_enabled': 'on',
            'ftp_enabled': 'on',
            'smtp_enabled': 'on',
            'smtp_use_tls': 'on',
            'whatsapp_enabled': 'on',
            'sms_enabled': 'on',
            'enable_street_view': 'on',
            'enable_traffic': 'on',
            'enable_map_clustering': 'on',
            'enable_drawing_tools': 'on',
            'enable_fullscreen': 'on',
            'mapbox_enable_3d': 'on',
        }
        
        response = self.client.post('/system-config/save/', test_data)
        self.assertEqual(response.status_code, 302)
        
        # Recarregar configuração
        config = SystemConfiguration.get_config()
        
        # Verificar todos os booleanos
        boolean_fields = [
            'gdrive_enabled', 'ftp_enabled', 'smtp_enabled', 'smtp_use_tls',
            'whatsapp_enabled', 'sms_enabled', 'enable_street_view', 
            'enable_traffic', 'enable_map_clustering', 'enable_drawing_tools',
            'enable_fullscreen', 'mapbox_enable_3d'
        ]
        
        for field_name in boolean_fields:
            self.assertTrue(
                getattr(config, field_name),
                f"Campo booleano {field_name} não foi salvo como True"
            )
    
    def test_config_loader_service(self):
        """Testa se o serviço ConfigLoader funciona"""
        # Configurar alguns valores
        self.config.company_name = "Test Company"
        self.config.google_maps_api_key = "test_api_key"
        self.config.save()
        
        # Testar ConfigLoader
        loader = ConfigLoader()
        config_data = loader.get_all_config()
        
        self.assertEqual(config_data.get('company_name'), "Test Company")
        self.assertEqual(config_data.get('google_maps_api_key'), "test_api_key")
    
    def test_runtime_settings_service(self):
        """Testa se o serviço RuntimeSettings funciona"""
        # Configurar valores
        self.config.map_provider = 'google'
        self.config.google_maps_api_key = 'test_key'
        self.config.save()
        
        # Testar RuntimeSettings
        runtime = RuntimeSettings()
        map_config = runtime.get_map_settings()
        
        self.assertIsNotNone(map_config)
        self.assertEqual(map_config.get('provider'), 'google')
    
    def test_audit_trail_creation(self):
        """Testa se o audit trail é criado ao salvar configurações"""
        initial_audit_count = ConfigurationAudit.objects.count()
        
        test_data = {
            'company_name': 'Updated Company Name',
        }
        
        response = self.client.post('/system-config/save/', test_data)
        self.assertEqual(response.status_code, 302)
        
        # Verificar se audit foi criado
        final_audit_count = ConfigurationAudit.objects.count()
        self.assertGreater(final_audit_count, initial_audit_count)
        
        # Verificar último audit
        last_audit = ConfigurationAudit.objects.latest('timestamp')
        self.assertEqual(last_audit.user, self.user)
        self.assertEqual(last_audit.action, 'BULK_UPDATE')
    
    def test_encrypted_fields(self):
        """Testa se campos encriptados funcionam corretamente"""
        # Campos que devem ser encriptados
        sensitive_data = {
            'company_name': 'Test',
            'smtp_password': 'super_secret_password',
            'ftp_password': 'ftp_secret_password',
            'sms_auth_token': 'sms_secret_token',
            'db_password': 'db_secret_password',
        }
        
        response = self.client.post('/system-config/save/', sensitive_data)
        self.assertEqual(response.status_code, 302)
        
        # Recarregar e verificar que pode desencriptar
        config = SystemConfiguration.get_config()
        
        # Os campos devem retornar o valor original ao aceder
        self.assertEqual(config.smtp_password, 'super_secret_password')
        self.assertEqual(config.ftp_password, 'ftp_secret_password')
        self.assertEqual(config.sms_auth_token, 'sms_secret_token')
        self.assertEqual(config.db_password, 'db_secret_password')
    
    def test_configuration_singleton(self):
        """Testa se o padrão singleton está funcionando"""
        config1 = SystemConfiguration.get_config()
        config2 = SystemConfiguration.get_config()
        
        self.assertEqual(config1.id, config2.id)
        self.assertEqual(SystemConfiguration.objects.count(), 1)


class ManagementCommandsTest(TestCase):
    """Testes para management commands"""
    
    def test_generate_fernet_key_command(self):
        """Testa se o comando generate_fernet_key existe"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('generate_fernet_key', stdout=out)
        output = out.getvalue()
        
        # Deve gerar uma chave Fernet válida
        self.assertIn('Fernet Key gerada:', output)
    
    def test_sync_env_command_exists(self):
        """Testa se o comando sync_env_from_setup existe"""
        from django.core.management import get_commands
        
        commands = get_commands()
        self.assertIn('sync_env_from_setup', commands)
    
    def test_backup_command_exists(self):
        """Testa se o comando make_backup existe"""
        from django.core.management import get_commands
        
        commands = get_commands()
        self.assertIn('make_backup', commands)
    
    def test_restore_command_exists(self):
        """Testa se o comando restore_db existe"""
        from django.core.management import get_commands
        
        commands = get_commands()
        self.assertIn('restore_db', commands)


class ServicesTest(TestCase):
    """Testes para serviços do sistema"""
    
    def test_cloud_backups_service_exists(self):
        """Testa se o serviço cloud_backups existe"""
        from system_config.services.cloud_backups import GoogleDriveBackup
        
        # Deve poder instanciar
        backup_service = GoogleDriveBackup()
        self.assertIsNotNone(backup_service)
    
    def test_service_reloader_exists(self):
        """Testa se o serviço service_reloader existe"""
        from system_config.services.service_reloader import ServiceReloader
        
        # Deve poder instanciar
        reloader = ServiceReloader()
        self.assertIsNotNone(reloader)
    
    def test_video_gateway_exists(self):
        """Testa se o serviço video_gateway existe"""
        from system_config.services.video_gateway import VideoGateway
        
        # Deve poder instanciar
        video_service = VideoGateway()
        self.assertIsNotNone(video_service)
