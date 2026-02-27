from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime
from send_paack_reports.views import generate_report_text, sync_before_report
import requests
import environ
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envia relatório automatizado com dados atualizados do dashboard (inclui sincronização automática)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Data específica para o relatório (formato: YYYY-MM-DD)',
        )
        parser.add_argument(
            '--preview',
            action='store_true',
            help='Apenas mostra o relatório sem enviar',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Envia sem confirmação',
        )
        parser.add_argument(
            '--no-sync',
            action='store_true',
            help='Pula a sincronização automática (não recomendado)',
        )

    def handle(self, *args, **options):
        try:
            # Processar data se fornecida
            target_date = None
            if options['date']:
                try:
                    target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                    self.stdout.write(f"📅 Usando data específica: {target_date.strftime('%d/%m/%Y')}")
                except ValueError:
                    raise CommandError(f"Data inválida: {options['date']}. Use o formato YYYY-MM-DD")
            
            # Executar sincronização se não foi desabilitada
            if not options['no_sync']:
                self.stdout.write("🔄 Executando sincronização automática...")
                sync_result = sync_before_report()
                if sync_result['success']:
                    self.stdout.write(self.style.SUCCESS("✅ Sincronização concluída!"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️ Sincronização com problemas: {sync_result.get('error', 'Erro desconhecido')}"))
                    if not options['force']:
                        confirm = input("❓ Continuar mesmo com problemas na sincronização? (s/N): ").lower().strip()
                        if confirm not in ['s', 'sim', 'y', 'yes']:
                            self.stdout.write(self.style.ERROR("❌ Operação cancelada devido a problemas na sincronização"))
                            return
            else:
                self.stdout.write(self.style.WARNING("⚠️ Sincronização automática desabilitada - dados podem estar desatualizados"))
            
            # Gerar relatório
            self.stdout.write("� Gerando relatório...")
            report_text = generate_report_text(target_date, include_sync_info=True)
            
            # Mostrar prévia
            self.stdout.write("\n📋 Relatório gerado:")
            self.stdout.write(self.style.SUCCESS(report_text))
            
            # Se for apenas prévia, parar aqui
            if options['preview']:
                self.stdout.write("\n✅ Prévia gerada com sucesso!")
                return
            
            # Confirmar envio se não for forçado
            if not options['force']:
                confirm = input("\n❓ Confirma o envio do relatório? (s/N): ").lower().strip()
                if confirm not in ['s', 'sim', 'y', 'yes']:
                    self.stdout.write(self.style.WARNING("❌ Envio cancelado pelo usuário."))
                    return
            
            # Enviar relatório
            self.stdout.write("\n📤 Enviando relatório...")
            result = self._send_report(report_text)
            
            if result['success']:
                status_code = result.get('status_code', 'N/A')
                self.stdout.write(self.style.SUCCESS(f"✅ Relatório enviado com sucesso! (HTTP {status_code})"))
                if 'api_response' in result:
                    self.stdout.write(f"📝 Resposta da API: {result['api_response']}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Erro ao enviar: {result['error']}"))
                
        except Exception as e:
            raise CommandError(f"Erro inesperado: {str(e)}")
    
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
            
            response = requests.post(url, json=payload, headers=headers)
            
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
