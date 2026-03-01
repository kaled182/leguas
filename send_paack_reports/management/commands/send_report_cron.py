import logging
from pathlib import Path

import environ
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from send_paack_reports.views import generate_report_text

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Executa envio de relatório se estiver no horário correto (para uso em cron)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Força o envio mesmo fora do horário",
        )
        parser.add_argument(
            "--start-hour",
            type=int,
            default=8,
            help="Hora de início dos envios (padrão: 8h)",
        )
        parser.add_argument(
            "--end-hour",
            type=int,
            default=20,
            help="Hora de fim dos envios (padrão: 20h)",
        )
        parser.add_argument(
            "--test-mode",
            action="store_true",
            help="Modo de teste - apenas mostra o que seria enviado",
        )

    def handle(self, *args, **options):
        self.start_hour = options["start_hour"]
        self.end_hour = options["end_hour"]
        self.test_mode = options["test_mode"]

        current_time = timezone.localtime(timezone.now())
        current_hour = current_time.hour
        current_minute = current_time.minute

        # Verificar se está no horário correto (xx:00 ou xx:30)
        is_correct_minute = current_minute in [0, 30]
        is_working_hours = self.start_hour <= current_hour < self.end_hour

        self.stdout.write(f"🕐 Hora atual: {current_time.strftime('%H:%M:%S')}")

        if self.test_mode:
            self.stdout.write(
                self.style.WARNING("🧪 MODO DE TESTE - Nenhum relatório será enviado")
            )

        if not options["force"]:
            if not is_working_hours:
                self.stdout.write(
                    f"⏰ Fora do horário de trabalho ({self.start_hour}h-{self.end_hour}h)"
                )
                return

            if not is_correct_minute:
                self.stdout.write(
                    f"⏱️ Aguardando horário correto (xx:00 ou xx:30). Atual: {current_minute} min"
                )
                return

        try:
            self.stdout.write("📤 Executando envio de relatório...")

            # Gerar relatório (inclui sincronização automática)
            report_text = generate_report_text(include_sync_info=True)

            if self.test_mode:
                self.stdout.write("📋 Relatório que seria enviado:")
                self.stdout.write(self.style.SUCCESS(report_text))
                self.stdout.write("✅ Teste concluído com sucesso!")
                return

            # Enviar relatório
            result = self._send_report(report_text)

            if result["success"]:
                status_code = result.get("status_code", "N/A")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Relatório enviado com sucesso! (HTTP {status_code})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Erro ao enviar: {result['error']}")
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro inesperado: {str(e)}"))

    def _send_report(self, report_text):
        """
        Envia o relatório via API.

        Returns:
            dict: Resultado da operação
        """
        try:
            # Configuração do ambiente
            BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
            env = environ.Env()
            environ.Env.read_env(BASE_DIR / ".env")

            # Carrega a chave da API
            api_key = env("AUTHENTICATION_API_KEY")

            url = "http://45.160.176.150:9090/message/sendText/leguasreports"

            payload = {
                "number": "120363418429414442@g.us",
                "textMessage": {"text": report_text},
            }
            headers = {"apikey": api_key, "Content-Type": "application/json"}

            response = requests.post(url, json=payload, headers=headers, timeout=30)

            # Aceitar qualquer código de sucesso (2xx)
            if 200 <= response.status_code < 300:
                return {
                    "success": True,
                    "api_response": response.text,
                    "status_code": response.status_code,
                }
            else:
                return {
                    "success": False,
                    "error": f"Erro HTTP {response.status_code}: {response.text}",
                }

        except Exception as e:
            return {"success": False, "error": str(e)}
