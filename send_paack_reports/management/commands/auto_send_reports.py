from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
from send_paack_reports.views import generate_report_text, sync_before_report
import requests
import environ
from pathlib import Path
import logging
import time

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envia relatórios automatizados a cada 30 minutos com sincronização automática'

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-once',
            action='store_true',
            help='Executa apenas uma vez e sai (útil para teste)',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Intervalo em minutos entre os envios (padrão: 30)',
        )
        parser.add_argument(
            '--start-hour',
            type=int,
            default=8,
            help='Hora de início dos envios (padrão: 8h)',
        )
        parser.add_argument(
            '--end-hour',
            type=int,
            default=20,
            help='Hora de fim dos envios (padrão: 20h)',
        )
        parser.add_argument(
            '--test-mode',
            action='store_true',
            help='Modo de teste - apenas mostra o que seria enviado',
        )
        parser.add_argument(
            '--debug-timing',
            action='store_true',
            help='Mostra informações detalhadas sobre timing e agendamento',
        )

    def handle(self, *args, **options):
        self.interval_minutes = options['interval']
        self.start_hour = options['start_hour']
        self.end_hour = options['end_hour']
        self.test_mode = options['test_mode']
        self.debug_timing = options['debug_timing']
        
        if self.test_mode:
            self.stdout.write(self.style.WARNING("🧪 MODO DE TESTE ATIVADO - Nenhum relatório será enviado"))
        
        current_time = timezone.localtime()
        is_working_hours = self._is_within_working_hours()
        
        self.stdout.write(
            f"🤖 Iniciando envio automático de relatórios:\n"
            f"   ⏰ Intervalo: {self.interval_minutes} minutos\n"
            f"   🌅 Horário: {self.start_hour}h às {self.end_hour}h\n"
            f"   📋 Teste: {'Sim' if self.test_mode else 'Não'}\n"
            f"   🕐 Hora atual: {current_time.strftime('%H:%M:%S')}\n"
            f"   🏢 Horário de trabalho: {'Sim' if is_working_hours else 'Não'}"
        )
        
        if self.debug_timing:
            next_run = self._calculate_next_run()
            time_diff = next_run - current_time
            self.stdout.write(
                f"\n🔍 Debug de Timing:\n"
                f"   📅 Próximo envio: {next_run.strftime('%H:%M:%S')}\n"
                f"   ⏱️  Tempo até envio: {int(time_diff.total_seconds() // 60)} minutos\n"
                f"   🔄 Intervalos configurados: {self.start_hour}h:00, {self.start_hour}h:30, ... {self.end_hour-1}h:30"
            )
        
        if options['run_once']:
            self._send_single_report()
        else:
            self._run_continuous_loop()

    def _send_single_report(self):
        """Envia um único relatório e sai."""
        try:
            if self._is_within_working_hours():
                self.stdout.write("📤 Enviando relatório único...")
                success = self._execute_report_cycle()
                if success:
                    self.stdout.write(self.style.SUCCESS("✅ Relatório enviado com sucesso!"))
                else:
                    self.stdout.write(self.style.ERROR("❌ Falha no envio do relatório"))
            else:
                self.stdout.write(self.style.WARNING("⏰ Fora do horário de trabalho - relatório não enviado"))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n🛑 Operação cancelada pelo usuário"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro inesperado: {str(e)}"))

    def _run_continuous_loop(self):
        """Executa o loop contínuo de envio a cada 30 minutos."""
        try:
            self.stdout.write("🔄 Iniciando loop contínuo...")
            next_run = self._calculate_next_run()
            
            self.stdout.write(f"⏰ Próximo envio agendado para: {next_run.strftime('%H:%M:%S')}")
            self.stdout.write("💡 Pressione Ctrl+C para parar o loop")
            
            while True:
                current_time = timezone.localtime()
                
                # Mostrar countdown apenas a cada minuto
                if current_time.second == 0:
                    time_diff = next_run - current_time
                    if time_diff.total_seconds() > 0:
                        minutes_left = int(time_diff.total_seconds() // 60)
                        self.stdout.write(f"⏳ Aguardando... {minutes_left} minutos para o próximo envio")
                
                if current_time >= next_run:
                    if self._is_within_working_hours():
                        self.stdout.write(f"📤 {current_time.strftime('%H:%M:%S')} - Enviando relatório...")
                        success = self._execute_report_cycle()
                        status = "✅ Sucesso" if success else "❌ Falha"
                        self.stdout.write(f"   {status}")
                    else:
                        self.stdout.write(f"⏰ {current_time.strftime('%H:%M:%S')} - Fora do horário de trabalho")
                    
                    next_run = self._calculate_next_run()
                    self.stdout.write(f"⏰ Próximo envio: {next_run.strftime('%H:%M:%S')}")
                
                # Aguardar 1 minuto antes de verificar novamente
                time.sleep(60)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n🛑 Loop interrompido pelo usuário"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro no loop: {str(e)}"))

    def _execute_report_cycle(self):
        """
        Executa um ciclo completo: sincronização + geração + envio.
        
        Returns:
            bool: True se sucesso, False caso contrário
        """
        try:
            # Gerar relatório (inclui sincronização automática)
            report_text = generate_report_text(include_sync_info=True)
            
            if self.test_mode:
                self.stdout.write("📋 Relatório que seria enviado:")
                self.stdout.write(self.style.SUCCESS(report_text))
                return True
            
            # Enviar relatório
            result = self._send_report(report_text)
            return result['success']
            
        except Exception as e:
            logger.error(f"Erro no ciclo de relatório: {str(e)}")
            self.stdout.write(f"   ❌ Erro: {str(e)}")
            return False

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
            environ.Env.read_env(BASE_DIR / '.env')
            
            # Carrega a chave da API
            api_key = env('AUTHENTICATION_API_KEY')
            
            url = "http://45.160.176.150:9090/message/sendText/leguasreports"
            
            payload = {
                "number": "120363418429414442@g.us",
                "textMessage": {"text": report_text}
            }
            headers = {
                "apikey": api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            # Aceitar qualquer código de sucesso (2xx)
            if 200 <= response.status_code < 300:
                return {
                    'success': True,
                    'api_response': response.text,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': f'Erro HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _is_within_working_hours(self):
        """Verifica se está dentro do horário de trabalho."""
        current_hour = timezone.localtime().hour
        return self.start_hour <= current_hour < self.end_hour

    def _calculate_next_run(self):
        """Calcula o próximo horário de execução."""
        now = timezone.localtime()
        
        # Calcular próximo intervalo de 30 minutos
        current_minute = now.minute
        if current_minute < 30:
            next_minute = 30
            next_hour = now.hour
        else:
            next_minute = 0
            next_hour = now.hour + 1
        
        next_run = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
        
        # Se passou para o próximo dia, ajustar
        if next_run.date() > now.date():
            next_run = next_run.replace(hour=self.start_hour, minute=0)
        
        # Se está fora do horário de trabalho, ir para o próximo horário válido
        if next_run.hour < self.start_hour:
            next_run = next_run.replace(hour=self.start_hour, minute=0)
        elif next_run.hour >= self.end_hour:
            # Ir para o próximo dia
            next_run = next_run.replace(hour=self.start_hour, minute=0) + timedelta(days=1)
        
        return next_run
