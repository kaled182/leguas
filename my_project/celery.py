"""
Configuração do Celery para o projeto Léguas Franzinas.

Este módulo configura o Celery para:
- Sincronizações automáticas de parceiros
- Tarefas agendadas (Celery Beat)
- Processamento assíncrono de tasks
"""

import os
from celery import Celery
from celery.schedules import crontab

# Definir configuração padrão do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')

# Criar instância do Celery
app = Celery('leguas')

# Carregar configurações do Django settings com namespace 'CELERY'
# Isso significa que todas as configurações Celery devem ter prefixo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descobrir tasks em todos os apps Django instalados
# Vai procurar tasks.py em cada app
app.autodiscover_tasks()

# Configurações adicionais
app.conf.update(
    # Timezone
    timezone='Europe/Lisbon',
    enable_utc=True,
    
    # Task result settings
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos timeout máximo
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Pegar 1 task por vez (bom para tasks longas)
    worker_max_tasks_per_child=1000,  # Reiniciar worker após 1000 tasks (prevenir memory leaks)
)

# Agendamento de tarefas periódicas (Celery Beat)
app.conf.beat_schedule = {
    # Sincronização diária do Delnext às 6h da manhã
    'sync-delnext-daily': {
        'task': 'core.sync_delnext_last_weekday',
        'schedule': crontab(hour=6, minute=0),  # 6:00 AM todos os dias
        'options': {
            'expires': 3600,  # Expirar após 1 hora se não executar
        }
    },
    
    # Sincronização de todos os parceiros às 7h da manhã
    'sync-all-partners-daily': {
        'task': 'core.sync_all_active_integrations',
        'schedule': crontab(hour=7, minute=0),  # 7:00 AM todos os dias
        'options': {
            'expires': 3600,
        }
    },
    
    # Limpeza de dados antigos toda Segunda às 3h da manhã
    'cleanup-old-data-weekly': {
        'task': 'core.cleanup_old_partner_data',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday 3 AM
        'kwargs': {'days': 90},  # Manter 90 dias
        'options': {
            'expires': 3600,
        }
    },
    
    # Relatório semanal às Sextas às 18h
    'send-weekly-report': {
        'task': 'core.send_sync_report',
        'schedule': crontab(hour=18, minute=0, day_of_week=5),  # Friday 6 PM
        'options': {
            'expires': 3600,
        }
    },
    
    # Auto-emit de PFs por frota — corre todo dia 06:30 e
    # decide internamente quais frotas processar nesse dia (mensal/semanal)
    'auto-emit-fleet-invoices': {
        'task': 'core.auto_emit_fleet_invoices',
        'schedule': crontab(hour=6, minute=30),
        'options': {'expires': 3600},
    },

    # Relatório semanal de Pacotes Not Arrived — sextas às 18h
    'not-arrived-weekly-report': {
        'task': 'settlements.send_not_arrived_weekly_report',
        'schedule': crontab(
            hour=18, minute=0, day_of_week=5,
        ),
        'options': {'expires': 3600},
    },

    # Snapshot diário de Not Arrived + spike alert — todos os dias 18h
    'not-arrived-daily-snapshot': {
        'task': 'settlements.create_daily_not_arrived_snapshot',
        'schedule': crontab(hour=18, minute=0),
        'options': {'expires': 3600},
    },

    # Gerar instâncias de contas recorrentes — todos os dias 06:00
    'accounting-generate-recurring-bills': {
        'task': 'accounting.generate_recurring_bills',
        'schedule': crontab(hour=6, minute=0),
        'kwargs': {'lookahead_days': 7},
        'options': {'expires': 3600},
    },

    # Alertas WhatsApp de contas a vencer/vencidas — todos os dias 09:00
    'accounting-send-bill-reminders': {
        'task': 'accounting.send_bill_reminders',
        'schedule': crontab(hour=9, minute=0),
        'kwargs': {'days': 3},
        'options': {'expires': 3600},
    },

    # Alerta WhatsApp do break-even mensal — todos os dias 19:00
    'accounting-break-even-alert': {
        'task': 'accounting.break_even_alert',
        'schedule': crontab(hour=19, minute=0),
        'options': {'expires': 3600},
    },

    # Tarefa de teste a cada 5 minutos (pode remover em produção)
    # 'test-celery-every-5min': {
    #     'task': 'core.test_task',
    #     'schedule': crontab(minute='*/5'),  # A cada 5 minutos
    # },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarefa de debug para testar Celery."""
    print(f'Request: {self.request!r}')
