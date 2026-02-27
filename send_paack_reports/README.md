# Send Paack Reports - Documentação

Este módulo é responsável por gerar e enviar relatórios automatizados com informações atualizadas do dashboard, **incluindo sincronização automática a cada execução**.

## ✨ Funcionalidades

### 🔄 **Sincronização Automática**
- Executa automaticamente antes de cada relatório
- Atualiza dados de pedidos, motoristas e despachos
- Garante informações sempre atualizadas

### 📋 **Geração de Relatório**
O relatório é gerado com as seguintes informações em tempo real:
- Data e hora atual
- Total de pedidos processados
- Pedidos por tentar
- Pedidos entregues
- Pedidos que falharam
- Pedidos recuperados
- Taxa de sucesso
- Melhor motorista do dia
- Eficiência semanal
- Status da sincronização

### 📤 **Envio via API**
O relatório pode ser enviado automaticamente via WhatsApp usando a API Evolution.

### ⏰ **Agendamento Automático**
- Envio a cada 30 minutos (configurável)
- Horário de funcionamento: 8h às 20h (configurável)
- Suporte a cron jobs

## 🚀 Como Usar

### Via Management Command (Recomendado)

```bash
# Visualizar relatório sem enviar (inclui sincronização automática)
python3 manage.py send_report --preview

# Enviar com confirmação
python3 manage.py send_report

# Enviar sem confirmação
python3 manage.py send_report --force

# Relatório para data específica
python3 manage.py send_report --date 2025-06-16 --preview

# Pular sincronização (não recomendado)
python3 manage.py send_report --no-sync --preview
```

### Via Envio Automático Contínuo

```bash
# Modo de teste (apenas mostra o que seria enviado)
python3 manage.py auto_send_reports --run-once --test-mode

# Executar uma única vez
python3 manage.py auto_send_reports --run-once

# Loop contínuo a cada 30 minutos
python3 manage.py auto_send_reports

# Personalizar configurações
python3 manage.py auto_send_reports --interval 15 --start-hour 7 --end-hour 22
```

### Via Script Standalone

```bash
# Executar o app.py diretamente
cd send_paack_reports
python3 app.py
```

### Via Endpoints Web

```bash
# Prévia do relatório (JSON)
GET /sendpaackreports/preview/

# Prévia para data específica
GET /sendpaackreports/preview/?date=2025-06-16

# Enviar relatório
POST /sendpaackreports/send/

# Interface web
GET /sendpaackreports/
```

## 📋 Exemplo de Saída

```
📋 Relatório Automático
🗓️ 17/06/2025 - 14:41:16

📦 Total de Pedidos: 470
⏳ Por Tentar: 138
✅ Entregues: 330
❌ Falhadas: 2
🔄 Recuperadas: —
📈 Taxa de Sucesso: 99.4%
🏅 Melhor Motorista: Gabrielle Tiengo (100.0%)
⚙️ Eficiência Semanal: 98.5%

🔄 Status: ✅ Dados sincronizados
```

## ⚙️ Configuração

### Variáveis de Ambiente

Certifique-se de que o arquivo `.env` contém:
```
AUTHENTICATION_API_KEY=sua_chave_aqui
```

### Configuração Automática de Cron

Execute o script de configuração:
```bash
./setup_auto_reports.sh
```

Isso criará um cron job para envio automático:
```bash
# Enviar relatório a cada 30 minutos (8h às 19h30)
0,30 8-19 * * * cd /path/to/project && python3 manage.py send_report --force
```

### Configuração Manual de Cron

```bash
# Editar crontab
crontab -e

# Adicionar linha para envio a cada 30 minutos
0,30 8-19 * * * cd /path/to/leguas-monitoring && python3 manage.py send_report --force 2>&1 | logger -t leguas_reports
```

## 🔧 Monitoramento

### Ver Logs em Tempo Real
```bash
# Logs do cron job
sudo journalctl -t leguas_reports -f

# Logs específicos dos últimos 100 registros
sudo journalctl -t leguas_reports -n 100
```

### Verificar Status
```bash
# Status da sincronização
curl http://localhost:8000/paack/sync-status/

# Teste de prévia
curl http://localhost:8000/sendpaackreports/preview/
```

## 📊 Estrutura dos Dados

O relatório busca informações em tempo real dos seguintes modelos:
- `Order` - Para dados de pedidos
- `Driver` - Para informações dos motoristas  
- `Dispatch` - Para dados de recuperação

### Processo de Sincronização

1. **Conecta à API Externa**: Busca dados atualizados
2. **Processa Dados**: Atualiza base de dados local
3. **Calcula Métricas**: Gera estatísticas em tempo real
4. **Gera Relatório**: Formata informações para envio

## 🚨 Tratamento de Erros

O sistema inclui tratamento robusto de erros:

### Tipos de Erro Cobertos
- **Timeout na API Externa**: Usa dados existentes na base
- **Falha de Conectividade**: Informa status no relatório
- **Dados Ausentes**: Mostra "—" para campos vazios
- **Erro no Envio**: Registra logs detalhados
- **Validação de Data**: Trata formatos inválidos

### Fallbacks Implementados
- Dados do cache quando API falha
- Relatório parcial quando sincronização falha
- Logs detalhados para troubleshooting
- Modo de teste para validação

## 🎛️ Configurações Avançadas

### Personalizar Horários
```bash
# Alterar horário de início/fim
python3 manage.py auto_send_reports --start-hour 7 --end-hour 21

# Alterar intervalo (em minutos)
python3 manage.py auto_send_reports --interval 15
```

### Modificar Template do Relatório
Edite a função `generate_report_text()` em `send_paack_reports/views.py`

### Adicionar Novos Campos
1. Modifique `DashboardCalculator` no módulo `management`
2. Atualize `generate_report_text()` 
3. Teste com `--preview`

## 🔍 Troubleshooting

### Problemas Comuns

**Comando não encontrado**
```bash
# Verificar se app está registrado
grep "send_paack_reports" my_project/settings.py
```

**API key ausente**
```bash
# Verificar arquivo .env
cat .env | grep AUTHENTICATION_API_KEY
```

**Sincronização falhando**
```bash
# Testar sincronização isoladamente
python3 manage.py sync_paack --force
```

**Cron job não funcionando**
```bash
# Verificar paths absolutos no crontab
crontab -l
```

### Testes de Validação

```bash
# Teste completo com sincronização
python3 manage.py send_report --preview

# Teste sem sincronização  
python3 manage.py send_report --no-sync --preview

# Teste em modo automático
python3 manage.py auto_send_reports --run-once --test-mode
```

## 📈 Métricas e Performance

### Otimizações Implementadas
- Cache de dados da API (5 minutos)
- Queries otimizadas no banco de dados
- Tratamento assíncrono de erros
- Timeout configurável para requisições

### Monitoramento de Performance
- Tempo de sincronização registrado
- Métricas de sucesso/falha
- Logs detalhados de performance

---

## 🎯 Status do Projeto

✅ **Implementação Completa**  
✅ **Sincronização Automática**  
✅ **Agendamento Flexível**  
✅ **Tratamento de Erros Robusto**  
✅ **Documentação Abrangente**  
✅ **Testes Validados**  

**🚀 Sistema pronto para produção!**
