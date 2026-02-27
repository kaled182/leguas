#!/bin/bash
# Script para envio automático de relatórios no início de cada hora (xx:00), das 8:00 até 22:00

PROJECT_PATH="/home/leguas-franzinas/web/app.leguasfranzinas.pt/public_html/leguas-monitoring"
VENV_PATH="$PROJECT_PATH/venv/bin/activate"
START_HOUR=8
END_HOUR=22
LAST_LOG_DAY=""

# Algoritmo de espera adaptativa:
# - Durante o período de execução (8h às 22h):
#   - Executa no minuto 00 de cada hora
#   - Espera 4 minutos entre verificações quando está longe da próxima execução
#   - Espera 20 segundos quando está próximo de uma possível execução (últimos 5 minutos da hora)
# - Fora do período de execução:
#   - Verifica a cada 5 minutos para economizar recursos
#   - A hora START_HOUR-1 (7h) é verificada para garantir que o script esteja pronto para execução às 8h

while true; do
    now=$(date '+%Y-%m-%d %H:%M:%S')
    hour=$(date +%H)
    minute=$(date +%M)
    day=$(date +%Y-%m-%d)

    # Log diário no início do dia
    if [[ "$day" != "$LAST_LOG_DAY" ]]; then
        echo "[LOG] ===== Início dos envios do dia $day ====="
        LAST_LOG_DAY="$day"
    fi

    if (( hour >= START_HOUR && hour <= END_HOUR )) && [[ "$minute" == "00" ]]; then
        echo "[LOG] $now - Iniciando envio de relatório da hora ${hour}:00..."
        source "$VENV_PATH"
        cd "$PROJECT_PATH"
        python3 manage.py send_report_cron --force
        echo "[LOG] $now - Execução finalizada."
        sleep 60  # Evita múltiplos envios no mesmo minuto
    else
        # Ajustar o tempo de espera com base no tempo restante para o próximo minuto 00
        # Isso reduz o número de verificações desnecessárias
        if (( hour >= START_HOUR-1 && hour < END_HOUR )); then
            current_minute=$(date +%M)
            if (( current_minute > 0 && current_minute < 55 )); then
                sleep 240  # Se estiver longe do próximo horário de execução, dorme 4 minutos
            else
                sleep 20  # Se estiver próximo do próximo horário de execução, verifica mais frequentemente
            fi
        else
            sleep 300  # Fora do período de execução, verifica a cada 5 minutos
        fi
    fi
done
