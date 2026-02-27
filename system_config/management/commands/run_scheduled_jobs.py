"""
Management command para executar jobs agendados.

Este comando verifica a configuração do sistema e executa os jobs analytics
que estão agendados para o horário atual.

Pode ser executado via crontab a cada minuto:
* * * * * cd /app && python manage.py run_scheduled_jobs

Ou via scheduler Python (APScheduler, Celery Beat, etc.)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from datetime import datetime
import socket

from system_config.models import SystemConfiguration, CronJobExecution


class Command(BaseCommand):
    help = 'Executa jobs agendados conforme configuração do sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-job',
            type=str,
            choices=['metrics', 'forecasts', 'alerts'],
            help='Força execução de um job específico, ignorando horário agendado'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula execução sem executar os jobs'
        )

    def handle(self, *args, **options):
        config = SystemConfiguration.get_config()
        force_job = options.get('force_job')
        dry_run = options.get('dry_run')
        
        now = timezone.now()
        current_time = now.strftime('%H:%M')
        
        self.stdout.write(f"🕐 Verificando jobs agendados para {current_time}...")
        
        jobs_to_run = []
        
        # Check Metrics Job
        if force_job == 'metrics' or (
            config.cron_metrics_enabled and
            config.cron_metrics_schedule == current_time
        ):
            jobs_to_run.append({
                'type': 'metrics',
                'name': 'Cálculo de Métricas Diárias',
                'emoji': '📊',
                'command': 'calculate_daily_metrics',
                'args': ['--backfill', str(config.cron_metrics_backfill_days)]
            })
        
        # Check Forecasts Job
        if force_job == 'forecasts' or (
            config.cron_forecasts_enabled and
            config.cron_forecasts_schedule == current_time
        ):
            args = [
                '--days', str(config.cron_forecasts_days_ahead),
                '--method', config.cron_forecasts_method
            ]
            if config.cron_forecasts_best_only:
                args.append('--best-only')
            
            jobs_to_run.append({
                'type': 'forecasts',
                'name': 'Geração de Forecasts',
                'emoji': '📈',
                'command': 'generate_forecasts',
                'args': args
            })
        
        # Check Alerts Job
        if force_job == 'alerts' or (
            config.cron_alerts_enabled and
            current_time in config.cron_alerts_schedule.split(',')
        ):
            args = ['--days', str(config.cron_alerts_check_days)]
            if not config.cron_alerts_send_notifications:
                args.append('--skip-notifications')
            
            jobs_to_run.append({
                'type': 'alerts',
                'name': 'Verificação de Alertas',
                'emoji': '🔔',
                'command': 'check_performance_alerts',
                'args': args
            })
        
        if not jobs_to_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Nenhum job agendado para {current_time}"
                )
            )
            return
        
        # Execute jobs
        for job in jobs_to_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{job['emoji']} Executando: {job['name']}"
                )
            )
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [DRY-RUN] Comando: {job['command']} {' '.join(job['args'])}"
                    )
                )
                continue
            
            # Create execution record
            execution = CronJobExecution.objects.create(
                job_type=job['type'],
                triggered_by='cron' if not force_job else 'manual',
                hostname=socket.gethostname(),
                parameters={
                    'command': job['command'],
                    'args': job['args'],
                    'scheduled_time': current_time
                }
            )
            
            try:
                # Capture output
                from io import StringIO
                import sys
                
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                
                stdout_buffer = StringIO()
                stderr_buffer = StringIO()
                
                sys.stdout = stdout_buffer
                sys.stderr = stderr_buffer
                
                try:
                    # Execute management command
                    call_command(job['command'], *job['args'])
                    
                    # Get output
                    output = stdout_buffer.getvalue()
                    errors = stderr_buffer.getvalue()
                    
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                
                # Parse results from output
                # Simplified parsing - can be enhanced based on command output format
                created = 0
                updated = 0
                skipped = 0
                error_count = 0
                
                if 'Created:' in output:
                    try:
                        created = int(output.split('Created:')[1].split()[0])
                    except:
                        pass
                
                if 'Updated:' in output:
                    try:
                        updated = int(output.split('Updated:')[1].split()[0])
                    except:
                        pass
                
                if 'Skipped:' in output:
                    try:
                        skipped = int(output.split('Skipped:')[1].split()[0])
                    except:
                        pass
                
                if 'Errors:' in output:
                    try:
                        error_count = int(output.split('Errors:')[1].split()[0])
                    except:
                        pass
                
                # Update execution record
                execution.finished_at = timezone.now()
                execution.status = 'success' if error_count == 0 else 'failed'
                execution.records_created = created
                execution.records_updated = updated
                execution.records_skipped = skipped
                execution.errors_count = error_count
                execution.output_log = output
                execution.error_log = errors
                execution.save()
                
                # Update config last run
                if job['type'] == 'metrics':
                    config.cron_metrics_last_run = timezone.now()
                    config.cron_metrics_last_status = execution.status
                elif job['type'] == 'forecasts':
                    config.cron_forecasts_last_run = timezone.now()
                    config.cron_forecasts_last_status = execution.status
                elif job['type'] == 'alerts':
                    config.cron_alerts_last_run = timezone.now()
                    config.cron_alerts_last_status = execution.status
                
                config.save()
                
                # Show results
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Concluído em {execution.get_duration_display()}"
                    )
                )
                self.stdout.write(
                    f"     Criados: {created} | Atualizados: {updated} | "
                    f"Ignorados: {skipped} | Erros: {error_count}"
                )
                
                if errors:
                    self.stdout.write(
                        self.style.ERROR(f"  ⚠️ Avisos/Erros: {errors[:200]}")
                    )
                
            except Exception as e:
                # Update execution as failed
                execution.finished_at = timezone.now()
                execution.status = 'failed'
                execution.error_log = str(e)
                execution.save()
                
                # Update config
                if job['type'] == 'metrics':
                    config.cron_metrics_last_run = timezone.now()
                    config.cron_metrics_last_status = 'failed'
                elif job['type'] == 'forecasts':
                    config.cron_forecasts_last_run = timezone.now()
                    config.cron_forecasts_last_status = 'failed'
                elif job['type'] == 'alerts':
                    config.cron_alerts_last_run = timezone.now()
                    config.cron_alerts_last_status = 'failed'
                
                config.save()
                
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Erro: {str(e)}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Execução de jobs concluída!"
            )
        )
