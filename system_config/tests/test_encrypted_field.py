from cryptography.fernet import Fernet
from django.db import connection
from django.test import TestCase

from system_config.fields import UndecryptableSecret
from system_config.models import SystemConfiguration


class UndecryptableSecretTests(TestCase):
    """Token encriptado com uma chave Fernet que já não está em FERNET_KEYS."""

    def setUp(self):
        self.token = Fernet(Fernet.generate_key()).encrypt(b"x" * 140).decode()  # 268 chars
        cfg = SystemConfiguration.get_config()
        cfg.ocr_gemini_api_key = "chave-boa"
        cfg.save()
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE system_config_systemconfiguration SET whatsapp_evolution_api_key=%s WHERE id=1",
                [self.token],
            )

    def test_le_como_falso_para_os_fallbacks(self):
        cfg = SystemConfiguration.get_config()
        self.assertIsInstance(cfg.whatsapp_evolution_api_key, UndecryptableSecret)
        self.assertFalse(cfg.whatsapp_evolution_api_key)
        self.assertEqual((cfg.whatsapp_evolution_api_key or "fallback"), "fallback")
        self.assertEqual(cfg.ocr_gemini_api_key, "chave-boa", "os legíveis continuam iguais")

    def test_save_completo_nao_parte_e_preserva_o_token(self):
        cfg = SystemConfiguration.get_config()
        cfg.company_name = "Léguas"
        cfg.save()
        with connection.cursor() as cur:
            cur.execute("SELECT whatsapp_evolution_api_key FROM system_config_systemconfiguration WHERE id=1")
            self.assertEqual(cur.fetchone()[0], self.token)
        self.assertEqual(SystemConfiguration.get_config().ocr_gemini_api_key, "chave-boa")

    def test_regravar_com_valor_novo_substitui(self):
        cfg = SystemConfiguration.get_config()
        cfg.whatsapp_evolution_api_key = "token-novo"
        cfg.save()
        self.assertEqual(SystemConfiguration.get_config().whatsapp_evolution_api_key, "token-novo")
