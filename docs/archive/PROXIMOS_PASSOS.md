# 🚀 Próximos Passos - Sistema Omnichannel

**Última Atualização:** 10 de Fevereiro de 2026

---

## 📋 Roadmap Completo

### ✅ FASE 1: INFRAESTRUTURA (CONCLUÍDA)
**Status:** 100% Completo ✅  
**Data:** 10/02/2026

- [x] Deploy Chatwoot + PostgreSQL + Redis
- [x] Configurar WPPConnect e conectar WhatsApp
- [x] Criar bridge Node.js bidirecional
- [x] Implementar polling de mensagens
- [x] Resolver issues críticos (source_id, API format, etc)
- [x] Deploy Typebot (infraestrutura)
- [x] Testes de comunicação bidirecional
- [x] Documentação técnica completa

**Resultado:** Sistema 100% funcional com 9 containers rodando

---

## 🎯 FASE 2: AUTOMAÇÃO COM TYPEBOT

**Prioridade:** 🔥 ALTA  
**Prazo Estimado:** 3-5 dias  
**Complexidade:** Média

### 2.1. Configurar Typebot Builder
**Responsável:** Equipe de Produto  
**Tempo:** 4-6 horas

**Tarefas:**
1. [ ] Acessar http://localhost:8081
2. [ ] Criar conta/login inicial
3. [ ] Criar novo bot: "Cadastro Motorista Léguas"
4. [ ] Configurar variáveis globais:
   - Nome completo
   - NIF
   - Telefone
   - Email
   - Morada completa
   - Código Postal
   - Cidade

**Estrutura do Fluxo (15 blocos):**

```
Bloco 1: Boas-vindas
├─ "Olá! Bem-vindo ao cadastro de motoristas Léguas Franzinas"
└─ Botão: "Iniciar Cadastro"

Bloco 2: Nome Completo
├─ "Qual é o seu nome completo?"
└─ Input Text → Salvar em {{nome_completo}}

Bloco 3: NIF
├─ "Qual é o seu NIF?"
├─ Input Number (9 dígitos)
└─ Validação: 9 dígitos numéricos

Bloco 4: Validação NIF (Condição)
├─ Se válido → Próximo
└─ Se inválido → "NIF inválido. Digite novamente"

Bloco 5: Telefone
├─ "Qual é o seu telefone? (Formato: +351 XXX XXX XXX)"
└─ Input Text → {{telefone}}

Bloco 6: Email
├─ "Qual é o seu email?"
├─ Input Email
└─ Validação: formato email

Bloco 7: Morada
├─ "Qual é a sua morada completa? (Rua, Número, Andar)"
└─ Input Text → {{morada}}

Bloco 8: Código Postal
├─ "Código Postal? (Formato: 0000-000)"
├─ Input Text
└─ Validação: XXXX-XXX

Bloco 9: Cidade
├─ "Cidade?"
└─ Input Text → {{cidade}}

Bloco 10: Upload CNH
├─ "Envie foto da sua CNH (frente)"
└─ Input File → {{cnh_frente}}

Bloco 11: Upload CNH Verso
├─ "Envie foto da sua CNH (verso)"
└─ Input File → {{cnh_verso}}

Bloco 12: Comprovante Morada
├─ "Envie comprovante de morada (máx 3 meses)"
└─ Input File → {{comprovante_morada}}

Bloco 13: Confirmação Dados
├─ "Confirme seus dados:"
├─ Mostrar resumo de todas as variáveis
└─ Botões: "Confirmar" | "Corrigir"

Bloco 14: Webhook Django
├─ Se "Confirmar":
├─ HTTP Request POST
├─ URL: http://web:8000/drivers/register-typebot/
├─ Headers: Content-Type: application/json
└─ Body: JSON com todas as variáveis

Bloco 15: Finalização
├─ "Cadastro enviado com sucesso!"
├─ "Nossa equipe analisará em até 48 horas"
└─ "Agradecemos seu interesse!"
```

**Exportar:**
- [ ] Exportar bot como JSON (backup)
- [ ] Salvar em: `docs/typebot-flows/cadastro-motorista.json`

---

### 2.2. Integrar Typebot com Chatwoot
**Responsável:** DevOps  
**Tempo:** 2-3 horas

**Tarefas:**
1. [ ] No Chatwoot, criar Integration:
   - Settings → Integrations → Webhooks
   - Name: "Typebot Cadastro"
   - URL: http://leguas_typebot_viewer:8082/api/v1/typebots/{typebot_id}/startChat
   - Events: conversation.created

2. [ ] No Typebot, configurar webhook de resposta:
   - Webhook URL: http://leguas_chatwoot_web:3000/webhooks/typebot
   - Método: POST
   - Headers: api_access_token: w2w8N98Pv8yqazrHPyqAuwkR

3. [ ] Testar fluxo completo:
   ```
   WhatsApp → Chatwoot → Typebot → Coleta Dados → Django
   ```

**Validação:**
- [ ] Mensagem no WhatsApp dispara bot
- [ ] Bot responde corretamente
- [ ] Dados salvos no Django
- [ ] Arquivos (CNH, comprovante) armazenados

---

### 2.3. Implementar Endpoint Django
**Responsável:** Backend Developer  
**Tempo:** 3-4 horas

**Arquivo:** `drivers_app/views.py`

```python
import json
import base64
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core.files.base import ContentFile
from .models import Driver
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def register_driver_typebot(request):
    """
    Endpoint para receber cadastro de motorista do Typebot
    """
    try:
        data = json.loads(request.body)
        logger.info(f"Recebido cadastro do Typebot: {data}")
        
        # Extrair dados do payload Typebot
        variables = {v['name']: v['value'] for v in data.get('variables', [])}
        
        # Criar motorista
        driver = Driver.objects.create(
            name=variables.get('nome_completo'),
            nif=variables.get('nif'),
            phone_number=variables.get('telefone'),
            email=variables.get('email'),
            address=variables.get('morada'),
            postal_code=variables.get('codigo_postal'),
            city=variables.get('cidade'),
            status='pending_approval'  # Aguardando aprovação
        )
        
        # Processar arquivos (CNH, Comprovante)
        if 'cnh_frente' in variables:
            cnh_data = base64.b64decode(variables['cnh_frente'])
            driver.cnh_front.save(
                f'cnh_frente_{driver.nif}.jpg',
                ContentFile(cnh_data),
                save=False
            )
        
        if 'cnh_verso' in variables:
            cnh_data = base64.b64decode(variables['cnh_verso'])
            driver.cnh_back.save(
                f'cnh_verso_{driver.nif}.jpg',
                ContentFile(cnh_data),
                save=False
            )
        
        if 'comprovante_morada' in variables:
            comp_data = base64.b64decode(variables['comprovante_morada'])
            driver.address_proof.save(
                f'comprovante_{driver.nif}.pdf',
                ContentFile(comp_data),
                save=False
            )
        
        driver.save()
        
        logger.info(f"Motorista {driver.id} criado com sucesso")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Motorista cadastrado com sucesso',
            'driver_id': driver.id
        })
        
    except Exception as e:
        logger.error(f"Erro ao processar cadastro: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
```

**Arquivo:** `drivers_app/urls.py`

```python
from django.urls import path
from . import views

urlpatterns = [
    # ... URLs existentes ...
    path('register-typebot/', views.register_driver_typebot, name='register_typebot'),
]
```

**Tarefas:**
- [ ] Implementar código acima
- [ ] Adicionar rota no urls.py
- [ ] Criar migrations se necessário (campos Driver)
- [ ] Testar endpoint manualmente:
  ```bash
  curl -X POST http://localhost:8000/drivers/register-typebot/ \
    -H "Content-Type: application/json" \
    -d '{"variables":[{"name":"nome_completo","value":"Teste"}]}'
  ```

---

## 🔧 FASE 3: MELHORIAS E OTIMIZAÇÕES

**Prioridade:** 🟡 MÉDIA  
**Prazo Estimado:** 1-2 semanas  
**Complexidade:** Baixa-Média

### 3.1. Suporte a Mídias no Bridge
**Tempo:** 4-6 horas

**Tarefas:**
- [ ] Detectar tipo de mídia (image, video, document, audio)
- [ ] Download de arquivo do WPPConnect
- [ ] Upload para Chatwoot API
- [ ] Suporte a thumbnails
- [ ] Validação de tamanho/formato

**Código Exemplo:**
```javascript
// Em sendMessageToChatwoot()
if (msg.type === 'image') {
  // Download da imagem
  const mediaData = await axios.get(
    `${config.wppconnect.url}/api/${session}/download-media/${msg.id}`,
    { headers: { Authorization: `Bearer ${token}` }}
  );
  
  // Upload para Chatwoot
  const formData = new FormData();
  formData.append('content', msg.body || 'Imagem recebida');
  formData.append('attachments[]', mediaData.data, 'image.jpg');
  
  await axios.post(chatwootUrl, formData, {
    headers: { 
      'api_access_token': token,
      'Content-Type': 'multipart/form-data' 
    }
  });
}
```

---

### 3.2. Dashboard de Métricas
**Tempo:** 8-12 horas

**Tecnologias:**
- Prometheus (coleta de métricas)
- Grafana (visualização)
- Node Exporter (métricas do sistema)

**Métricas a Monitorar:**
- Total de mensagens (enviadas/recebidas)
- Latência média
- Taxa de erro
- Uptime dos containers
- CPU/Memory usage
- Chats ativos
- Tempo médio de resposta

**Dashboards:**
1. Overview (visão geral do sistema)
2. Performance (latência, throughput)
3. Erros (logs, stack traces)
4. Negócio (conversões, satisfação)

---

### 3.3. Sistema de Alertas
**Tempo:** 4-6 horas

**Alertas Críticos:**
- [ ] Container down (Chatwoot, WPPConnect, Bridge)
- [ ] Erro rate > 5%
- [ ] Latência > 30 segundos
- [ ] WPPConnect desconectado
- [ ] Disco > 80% cheio
- [ ] Memory > 90%

**Canais de Notificação:**
- Email (admin@leguasfranzinas.pt)
- Slack/Discord (se configurado)
- SMS (para alertas críticos)

**Ferramentas:**
- Alertmanager (Prometheus)
- PagerDuty (opcional)
- Sentry (erros de aplicação)

---

### 3.4. Otimização de Polling
**Tempo:** 6-8 horas

**Melhorias:**

1. **Polling Adaptativo:**
```javascript
let pollingInterval = 5000; // Inicial: 5s

function adjustPollingInterval(hasMessages) {
  if (hasMessages) {
    pollingInterval = Math.max(2000, pollingInterval - 1000); // Reduz até 2s
  } else {
    pollingInterval = Math.min(10000, pollingInterval + 1000); // Aumenta até 10s
  }
}
```

2. **Considerar WebSocket (se WPPConnect suportar):**
```javascript
const ws = new WebSocket('ws://wppconnect:21465/socket');
ws.on('message', (data) => {
  processMessage(JSON.parse(data));
});
```

3. **Redis Cache Distribuído:**
```javascript
// Substituir Set() por Redis
const redis = require('redis').createClient();
await redis.sadd('processed_ids', messageId);
```

---

## 📈 FASE 4: PRODUÇÃO

**Prioridade:** 🟢 BAIXA  
**Prazo:** Quando necessário escalar  
**Complexidade:** Alta

### 4.1. Segurança
- [ ] HTTPS/SSL para todos endpoints
- [ ] Rate limiting (nginx/redis)
- [ ] IP whitelisting
- [ ] Rotação automática de tokens
- [ ] Secrets management (Vault)
- [ ] Auditoria de logs

### 4.2. Escalabilidade
- [ ] Load balancer (nginx/HAProxy)
- [ ] Múltiplas instâncias do Bridge
- [ ] Queue system (RabbitMQ/Redis Queue)
- [ ] Sharding de banco de dados
- [ ] CDN para arquivos estáticos

### 4.3. Backup e Disaster Recovery
- [ ] Backup diário PostgreSQL
- [ ] Backup incremental a cada 6 horas
- [ ] Armazenamento offsite (S3/Backblaze)
- [ ] Plano de recuperação documentado
- [ ] Testes de restore trimestrais

### 4.4. Monitoring Avançado
- [ ] APM (Application Performance Monitoring)
- [ ] Distributed Tracing (Jaeger/Zipkin)
- [ ] Log aggregation (ELK Stack)
- [ ] Real User Monitoring
- [ ] Synthetic monitoring

---

## ✅ Checklist Geral

### Antes de Ir para Produção
- [ ] Todos os testes passando
- [ ] Documentação atualizada
- [ ] Secrets em .env (não em código)
- [ ] Backup configurado
- [ ] Monitoring ativo
- [ ] Alertas configurados
- [ ] Plano de rollback definido
- [ ] Performance testada (load test)
- [ ] Segurança auditada
- [ ] Equipe treinada

### Após Deploy em Produção
- [ ] Monitorar primeiras 24h continuamente
- [ ] Validar métricas baseline
- [ ] Coletar feedback de usuários
- [ ] Ajustar alertas baseado em dados reais
- [ ] Documentar incidentes
- [ ] Revisar logs diariamente (primeira semana)

---

## 🎯 Prioridades Imediatas (Esta Semana)

**1. Typebot (URGENTE)**
- Configurar bot de cadastro
- Integrar com Chatwoot
- Implementar endpoint Django
- Testar fluxo completo

**2. Documentação (IMPORTANTE)**
- ✅ Documentação técnica (concluída)
- [ ] Manual de operação para equipe
- [ ] Runbook de incidentes
- [ ] FAQ para usuários

**3. Testes (IMPORTANTE)**
- [ ] Teste de carga (100+ mensagens simultâneas)
- [ ] Teste de falha (container down)
- [ ] Teste de recuperação
- [ ] Teste de segurança básico

---

## 📞 Contatos e Responsabilidades

| Área | Responsável | Contato |
|------|-------------|---------|
| **Backend/Django** | (definir) | (email) |
| **DevOps/Infra** | (definir) | (email) |
| **Produto/Typebot** | (definir) | (email) |
| **Suporte Técnico** | (definir) | (email) |

---

**Próxima Revisão:** 13 de Fevereiro de 2026  
**Status Tracker:** [OMNICHANNEL_CHECKLIST.md](OMNICHANNEL_CHECKLIST.md)
