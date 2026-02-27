import requests
import os
import sys
import django
import environ
from pathlib import Path

# Adicionar o diretório do projeto ao path e configurar Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

# Agora importar após configurar Django
from send_paack_reports.views import generate_report_text

# Configuração do ambiente
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

def send_automated_report(target_date=None):
    """
    Função para enviar relatório automatizado com dados atualizados.
    
    Args:
        target_date (date, optional): Data específica para o relatório. Se None, usa data atual.
        
    Returns:
        dict: Resultado da operação com status e mensagens
    """
    try:
        # Gerar relatório com dados atualizados
        report_text = generate_report_text(target_date)
        
        # Carrega a chave da API do arquivo .env
        api_key = env('AUTHENTICATION_API_KEY')
        
        print(f"Using API key: {api_key}")
        
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
        
        print("Response status:", response.status_code)
        print("Response text:", response.text)
        
        # Aceitar qualquer código de sucesso (2xx)
        if 200 <= response.status_code < 300:
            return {
                'success': True,
                'message': 'Relatório enviado com sucesso!',
                'report': report_text,
                'api_response': response.text,
                'status_code': response.status_code
            }
        else:
            return {
                'success': False,
                'error': f'Erro na API: {response.status_code}',
                'report': report_text,
                'api_response': response.text
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def preview_report(target_date=None):
    """
    Função para visualizar o relatório sem enviar.
    
    Args:
        target_date (date, optional): Data específica para o relatório. Se None, usa data atual.
        
    Returns:
        str: Texto do relatório
    """
    try:
        return generate_report_text(target_date)
    except Exception as e:
        return f"Erro ao gerar relatório: {str(e)}"

if __name__ == "__main__":
    print("🔄 Gerando relatório automatizado...")
    
    # Mostrar prévia primeiro
    print("\n📋 Prévia do relatório:")
    preview = preview_report()
    print(preview)
    
    # Perguntar se deve enviar
    confirm = input("\n❓ Deseja enviar este relatório? (s/N): ").lower().strip()
    
    if confirm in ['s', 'sim', 'y', 'yes']:
        print("\n📤 Enviando relatório...")
        result = send_automated_report()
        
        if result['success']:
            print("✅ Relatório enviado com sucesso!")
        else:
            print("❌ Erro ao enviar relatório:")
            print(result['error'])
    else:
        print("❌ Envio cancelado pelo usuário.")
