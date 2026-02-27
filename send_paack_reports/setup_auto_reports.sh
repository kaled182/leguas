#!/bin/bash

# Script para configurar envio automático de relatórios a cada hora
# Executa das 8h às 22h (última execução do dia)

PROJECT_PATH="/home/leguas-franzinas/web/app.leguasfranzinas.pt/public_html/leguas-monitoring"
PYTHON_PATH="python3"
LOG_TAG="leguas_reports"

echo "🚀 Configurando envio automático de relatórios..."

# Verificar se o projeto existe
if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ Erro: Projeto não encontrado em $PROJECT_PATH"
    exit 1
fi

# Verificar se o comando existe
if ! cd "$PROJECT_PATH" && $PYTHON_PATH manage.py help send_report_cron >/dev/null 2>&1; then
    echo "❌ Erro: Comando send_report_cron não encontrado"
    exit 1
fi

# Criar entrada no crontab
CRON_ENTRY="0 8-22 * * * cd $PROJECT_PATH && $PYTHON_PATH manage.py send_report_cron 2>&1 | logger -t $LOG_TAG"

echo "📋 Configuração do cron job:"
echo "   Comando: $CRON_ENTRY"
echo "   Execução: A cada hora (8h00, 9h00, 10h00, ... 22h00)"
echo "   Logs: journalctl -t $LOG_TAG"

# Verificar se já existe uma entrada similar
if crontab -l 2>/dev/null | grep -q "send_report"; then
    echo "⚠️  Já existe uma entrada de relatório no crontab"
    echo "🔍 Entradas atuais:"
    crontab -l 2>/dev/null | grep "send_report" | sed 's/^/    /'
    echo ""
    read -p "Deseja substituir a configuração existente? (y/N): " choice
    if [[ $choice != [Yy]* ]]; then
        echo "❌ Operação cancelada"
        exit 0
    fi
    
    # Remover entradas existentes
    crontab -l 2>/dev/null | grep -v "send_report" | crontab -
    echo "🗑️  Entradas antigas removidas"
fi

# Adicionar nova entrada
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job configurado com sucesso!"
echo ""
echo "� Como monitorar:"
echo "   Ver logs em tempo real: sudo journalctl -t $LOG_TAG -f"
echo "   Ver últimos 50 logs: sudo journalctl -t $LOG_TAG -n 50"
echo "   Listar cron jobs: crontab -l"
echo ""
echo "🧪 Para testar:"
echo "   Teste manual: cd $PROJECT_PATH && $PYTHON_PATH manage.py send_report_cron --test-mode"
echo "   Forçar envio: cd $PROJECT_PATH && $PYTHON_PATH manage.py send_report_cron --force --test-mode"
echo ""
echo "🛑 Para parar:"
echo "   Editar crontab: crontab -e"
echo "   Ou executar este script novamente para substituir"
echo ""
echo "🎯 O sistema enviará relatórios automaticamente:"
echo "   📅 Todos os dias das 8h às 22h"
echo "   ⏰ A cada hora (xx:00)"
echo "   🔄 Com sincronização automática antes de cada envio"
echo "   📱 Via WhatsApp para o grupo configurado"
