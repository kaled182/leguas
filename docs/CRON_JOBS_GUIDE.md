# ⏰ Guia de Configuração de Cron Jobs - Analytics

## 📋 Visão Geral

O sistema possui 3 jobs automáticos configuráveis que processam dados analytics:

| Job | Descrição | Frequência Recomendada |
|-----|-----------|------------------------|
| 📊 **Métricas Diárias** | Calcula agregados de pedidos, receita, motoristas | Diário às 01:00 |
| 📈 **Forecasts de Volume** | Gera previsões estatísticas para próximos 7 dias | Diário às 02:00 |
| 🔔 **Alertas de Performance** | Monitora thresholds e cria alertas | 3x/dia (06:00, 12:00, 18:00) |

---

## 🎛️ Configuração via Django Admin

### 1. Acessar Configurações do Sistema

1. Faça login no Django Admin: `http://localhost:8000/admin/`
2. Navegue para: **System Config → Configuração do Sistema**
3. Expanda a seção: **⏰ Cron Jobs - Analytics**

### 2. Configurar Job: Métricas Diárias

**Objetivo:** Calcula métricas agregadas (pedidos, receita, motoristas ativos) para cada partner.

```
📊 Cálculo de Métricas Diárias Ativado: [X] Sim
📊 Horário de Execução (Métricas): 01:00
📊 Dias de Backfill (Métricas): 1
```

**Parâmetros:**
- **Ativado**: Marque para ativar o job
- **Horário**: Formato HH:MM (24h). Ex: `01:00` para 1h da manhã
- **Dias de Backfill**: Quantos dias recalcular (default: 1 = apenas ontem)
  - Use `7` para recalcular última semana (útil após mudanças de código)

### 3. Configurar Job: Forecasts de Volume

**Objetivo:** Gera previsões de volume usando 5 métodos estatísticos.

```
📈 Geração de Forecasts Ativada: [X] Sim
📈 Horário de Execução (Forecasts): 02:00
📈 Dias de Previsão: 7
📈 Método de Forecasting: ALL (Todos os Métodos)
📈 Manter Apenas Melhor Previsão: [X] Sim
```

**Parâmetros:**
- **Dias de Previsão**: Quantos dias prever (default: 7)
- **Método**:
  - `MA7`: Média Móvel 7 dias (curto prazo)
  - `MA30`: Média Móvel 30 dias (longo prazo)
  - `EMA`: Exponential Moving Average (peso em dados recentes)
  - `TREND`: Análise de Tendências (regressão linear)
  - `SEASONAL`: Padrões Sazonais (dia da semana)
  - `ALL`: Gera com todos os métodos
- **Manter Apenas Melhor**: Se marcado, mantém apenas previsão com maior confiança por data

### 4. Configurar Job: Alertas de Performance

**Objetivo:** Monitora thresholds de performance e cria alertas automáticos.

```
🔔 Verificação de Alertas Ativada: [X] Sim
🔔 Horários de Execução (Alertas): 06:00,12:00,18:00
🔔 Dias de Análise (Alertas): 1
🔔 Enviar Notificações: [X] Sim
```

**Parâmetros:**
- **Horários**: Múltiplos horários separados por vírgula
  - Ex: `06:00,12:00,18:00` = 3 execuções por dia
- **Dias de Análise**: Quantos dias de métricas analisar
- **Enviar Notificações**: Se marcado, envia notificações quando alertas são criados

**Alertas Monitorados:**
- Taxa de sucesso < 80% → WARNING
- Taxa de sucesso < 70% → CRITICAL
- Taxa de falhas > 15% → WARNING
- Taxa de falhas > 25% → CRITICAL
- Tempo médio entrega > 48h → WARNING
- Motoristas disponíveis < 5 → WARNING
- Pico de volume (50%+ vs média 7 dias) → INFO
- Queda de receita (30%+ vs média 7 dias) → WARNING

---

## 🖥️ Configuração do Scheduler (Crontab)

### Opção 1: Crontab Linux (Recomendado)

Adicione ao crontab do servidor:

```bash
# Editar crontab
crontab -e

# Adicionar linha (executa a cada minuto)
* * * * * cd /caminho/para/projeto && docker compose exec -T web python manage.py run_scheduled_jobs >> /var/log/cron_jobs.log 2>&1
```

**Explicação:**
- `* * * * *`: Executa todo minuto
- `cd /caminho/para/projeto`: Navega para diretório do projeto
- `docker compose exec -T web`: Executa dentro do container web
- `>> /var/log/cron_jobs.log`: Salva logs
- `2>&1`: Redireciona erros para o mesmo arquivo

### Opção 2: Django-Crontab

1. Instalar pacote:
```bash
pip install django-crontab
```

2. Adicionar ao `settings.py`:
```python
INSTALLED_APPS = [
    ...
    'django_crontab',
]

CRONJOBS = [
    ('* * * * *', 'django.core.management.call_command', ['run_scheduled_jobs']),
]
```

3. Ativar:
```bash
python manage.py crontab add
```

### Opção 3: Celery Beat (Para Sistemas Complexos)

Se já usa Celery, configure no `celery.py`:

```python
from celery import Celery
from celery.schedules import crontab

app = Celery('leguas')

app.conf.beat_schedule = {
    'run-scheduled-jobs': {
        'task': 'core.tasks.run_cron_jobs',
        'schedule': crontab(minute='*'),  # Todo minuto
    },
}
```

---

## 📊 Monitoramento de Execuções

### Ver Histórico no Admin

1. Django Admin → **System Config → Execuções de Cron Jobs**
2. Filtros disponíveis:
   - Tipo de job (📊 Métricas, 📈 Forecasts, 🔔 Alertas)
   - Status (✅ Sucesso, ❌ Falhou, ⏳ Em Execução)
   - Data de execução

### Informações Exibidas

- **Duração**: Tempo de execução
- **Resultados**:
  - ✨ Criados (registros novos)
  - 🔄 Atualizados (registros modificados)
  - ⏭️ Ignorados (já existentes)
  - ❌ Erros (falhas)
- **Taxa de Sucesso**: Percentual de operações bem-sucedidas
- **Logs**: Output completo e erros

### Status na Configuração

No admin de **Sistema Configuration**, seção Cron Jobs exibe:

- 🟢 Status: ATIVO / 🔴 INATIVO
- ⏰ Horário configurado
- Última execução (data/hora e tempo atrás)
- Status da última execução: ✅ Sucesso / ❌ Falhou / ⏳ Em Execução

---

## 🧪 Testes e Troubleshooting

### Testar Execução Manual (Dry Run)

Simula execução sem processar dados:

```bash
docker compose exec web python manage.py run_scheduled_jobs --dry-run
```

### Forçar Execução de Job Específico

```bash
# Forçar cálculo de métricas (ignora horário agendado)
docker compose exec web python manage.py run_scheduled_jobs --force-job metrics

# Forçar geração de forecasts
docker compose exec web python manage.py run_scheduled_jobs --force-job forecasts

# Forçar verificação de alertas
docker compose exec web python manage.py run_scheduled_jobs --force-job alerts
```

### Executar Jobs Diretamente (Bypass Scheduler)

```bash
# Métricas (últimos 7 dias)
docker compose exec web python manage.py calculate_daily_metrics --backfill 7

# Forecasts (próximos 7 dias, todos os métodos, melhor apenas)
docker compose exec web python manage.py generate_forecasts --days 7 --method ALL --best-only

# Alertas (últimas 24h, com notificações)
docker compose exec web python manage.py check_performance_alerts --days 1
```

### Verificar Logs

```bash
# Logs do crontab (se configurado)
tail -f /var/log/cron_jobs.log

# Logs do Docker
docker compose logs -f web | grep "run_scheduled_jobs"
```

### Problemas Comuns

**1. Jobs não executam:**
- ✅ Verificar se crontab está ativo: `crontab -l`
- ✅ Verificar se jobs estão ativados no admin
- ✅ Verificar horários configurados (HH:MM em formato 24h)
- ✅ Verificar logs de erros no histórico de execuções

**2. Execuções falham:**
- ✅ Ver logs detalhados em **Execuções de Cron Jobs**
- ✅ Testar comando manualmente
- ✅ Verificar se há dados históricos suficientes (forecasting precisa ≥7 dias)

**3. Performance lenta:**
- ✅ Reduzir backfill_days (usar 1 ao invés de 7+)
- ✅ Executar forecasts em horários de baixo tráfego
- ✅ Considerar adicionar índices de banco de dados

---

## 🎯 Melhores Práticas

### Horários Recomendados

```
01:00 → Métricas Diárias (após meia-noite, dados do dia anterior completos)
02:00 → Forecasts (após cálculo de métricas)
06:00, 12:00, 18:00 → Alertas (início, meio e fim do dia útil)
```

### Frequência

- **Métricas**: 1x/dia é suficiente (dados históricos são estáveis)
- **Forecasts**: 1x/dia (previsões não mudam muito intra-dia)
- **Alertas**: 2-3x/dia (para monitoramento em tempo útil)

### Backfill

- **Produção**: Use `backfill_days = 1` (apenas ontem)
- **Após Deploy**: Execute manualmente com `--backfill 30` para popular histórico
- **Após Bugfix**: Execute com `--backfill 7` para recalcular semana

### Notificações

- Configure emails/SMS/WhatsApp para alertas CRITICAL
- Use apenas INFO/WARNING no admin para revisão manual
- Evite spam: alertas são deduplicados (mesmo tipo + mesma data = 1 alerta apenas)

---

## 📈 Exemplo de Fluxo Completo

**Cenário**: Configurar sistema do zero

1. **Django Admin → Configuração do Sistema**
   - Ativar 3 jobs
   - Configurar horários: 01:00, 02:00, 06:00,12:00,18:00

2. **Popular dados históricos** (30 dias):
   ```bash
   docker compose exec web python manage.py calculate_daily_metrics --backfill 30
   ```

3. **Gerar forecasts iniciais**:
   ```bash
   docker compose exec web python manage.py generate_forecasts --days 7 --method ALL --best-only
   ```

4. **Configurar crontab**:
   ```bash
   * * * * * cd /app && docker compose exec -T web python manage.py run_scheduled_jobs >> /var/log/cron.log 2>&1
   ```

5. **Monitorar primeira execução**:
   - Aguardar até 01:00 (métricas)
   - Django Admin → Execuções de Cron Jobs
   - Verificar Status: ✅ Sucesso
   - Verificar duração e resultados

6. **Ajustar conforme necessário**:
   - Se forecasts muito lentos → considerar apenas MA7
   - Se muitos alertas → ajustar thresholds (código)
   - Se falhas → verificar logs e corrigir

---

## 🔗 Links Úteis

- **Dashboard Analytics**: `/analytics/dashboard/` (quando implementado)
- **Forecasts**: `/admin/analytics/volumeforecast/`
- **Alertas**: `/admin/analytics/performancealert/`
- **Métricas**: `/admin/analytics/dailymetrics/`
- **Histórico Jobs**: `/admin/system_config/cronjobexecution/`
- **Configuração**: `/admin/system_config/systemconfiguration/`

---

## ✅ Checklist de Implementação

- [ ] Configurar horários dos 3 jobs no admin
- [ ] Ativar jobs no admin
- [ ] Popular histórico com backfill manual (30 dias)
- [ ] Configurar crontab ou scheduler
- [ ] Testar execução manual forçada
- [ ] Aguardar primeira execução automática
- [ ] Verificar logs e histórico
- [ ] Configurar notificações para alertas CRITICAL
- [ ] Documentar procedimentos específicos da equipe
- [ ] Treinar equipe para usar dashboard analytics

🚀 **Sistema pronto para operar em produção!**
