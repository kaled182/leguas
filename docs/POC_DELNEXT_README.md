# POC Delnext - Playwright Web Scraping

## 📋 Visão Geral

Este POC (Proof of Concept) demonstra a viabilidade de scraping do sistema Delnext usando **Playwright**, com funcionalidades avançadas de **network interception** para detectar APIs JSON escondidas.

## 🎯 Objetivos do POC

1. ✅ Validar login automatizado no Delnext
2. ✅ Extrair dados de **Inbound Partners** (recebimentos)
3. ✅ Extrair dados de **Outbound Consult** (previsão de entregas)
4. ✅ Acessar **Application Stats** (estatísticas operacionais)
5. ✅ **Detectar APIs JSON escondidas** (feature killer!)
6. ✅ Gerar relatório completo + JSON + screenshots

## 🚀 Como Executar

### Método 1: Fora do Docker (Desenvolvimento Local)

```powershell
# 1. Ativar ambiente virtual
.venv\Scripts\Activate.ps1

# 2. Instalar Playwright
pip install playwright

# 3. Instalar navegadores Playwright
playwright install chromium

# 4. Testar instalação (opcional)
python test_playwright_install.py

# 5. Executar POC
python delnext_poc_playwright.py
```

### Método 2: Dentro do Docker

```powershell
# 1. Adicionar Playwright ao container
docker exec -it leguas_web pip install playwright

# 2. Instalar navegador Chromium
docker exec -it leguas_web playwright install chromium
docker exec -it leguas_web playwright install-deps chromium

# 3. Testar instalação
docker exec -it leguas_web python test_playwright_install.py

# 4. Executar POC
docker exec -it leguas_web python delnext_poc_playwright.py
```

## 📂 Arquivos Gerados

Após executar o POC, os seguintes arquivos serão criados:

```
debug_files/delnext_poc/
├── 01_login_page.png              # Screenshot da página de login
├── 02_after_login.png             # Screenshot após login
├── 03_inbound_page.png            # Página de Inbound
├── 04_outbound_page.png           # Página de Outbound (CRÍTICO)
├── 05_stats_page.png              # Página de Stats
├── 06_final_page.png              # Estado final
├── delnext_data_sample.json       # Dados extraídos em JSON
└── error_*.png                    # Screenshots de erro (se houver)
```

## 📊 Estrutura do JSON Gerado

```json
{
  "timestamp": "2026-03-01T12:00:00",
  "inbound": [
    {
      "parcel_id": "ABC123",
      "admin_name": "VianaCastelo",
      "warehouse": "WH01",
      "destination_zone": "Braga",
      "country": "Portugal",
      "city": "Braga",
      "date": "2026-03-01",
      "comment": ""
    }
  ],
  "outbound": [
    {
      "parcel_id": "DEF456",
      "destination": "Lisboa",
      "postal_code": "1000-001",
      "status": "confirmed",
      "weight": "2.5"
    }
  ],
  "stats": {
    "drivers": [...],
    "incidents": [...],
    "deliveries_summary": {...}
  },
  "api_endpoints": [
    {
      "url": "https://delnext.com/api/data.json",
      "status": 200,
      "content_type": "application/json",
      "has_json": true
    }
  ]
}
```

## 🔍 Network Interception (Feature Killer)

O POC usa **network interception** do Playwright para detectar automaticamente APIs JSON escondidas:

```python
def log_response(response: Response):
    """Monitora TODAS as requisições de rede"""
    if 'api' in response.url or 'json' in response.url:
        print(f"🔴 API DETECTADA: {response.url}")
        # Captura resposta JSON automaticamente!
```

### Por que isso é importante?

Se o Delnext fizer chamadas AJAX para buscar dados em JSON:
- ✅ Podemos usar **Requests** direto (MUITO mais rápido!)
- ✅ Não precisa parsear HTML (dados estruturados)
- ✅ Menos frágil a mudanças no layout

## 📈 Interpretando os Resultados

### Cenário 1: APIs JSON Detectadas ✅

```
🔴 API DETECTADA:
   URL: https://delnext.com/api/inbound/list
   Status: 200
   Content-Type: application/json
```

**🎯 PRÓXIMO PASSO:** Usar Requests + engenharia reversa da API
- Muito mais rápido (5-10x)
- Mais estável
- Dados estruturados

### Cenário 2: Nenhuma API Detectada ⚠️

```
⚠️ Nenhuma API JSON escondida detectada
   Continuar com Playwright para scraping de HTML
```

**🎯 PRÓXIMO PASSO:** Implementar scraper Playwright completo
- Mais lento que API
- Funcional e confiável
- Requer manutenção se HTML mudar

## 🛠️ Troubleshooting

### Erro: "Playwright not installed"

```powershell
pip install playwright
playwright install chromium
```

### Erro: "Executable doesn't exist"

```powershell
# Instalar dependências do navegador
playwright install-deps chromium

# Ou reinstalar tudo
playwright install
```

### Erro no Docker: "Browser closed unexpectedly"

```dockerfile
# Adicionar ao Dockerfile:
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libgbm1
```

### Erro de Login

Verifique:
1. Credenciais corretas (VianaCastelo / HelloViana23432)
2. Site está acessível
3. Screenshots em `debug_files/delnext_poc/error_*.png`

## 📝 Próximos Passos Após POC

### Se POC for bem-sucedido:

1. **Analisar resultados**
   - Revisar JSON gerado
   - Verificar se APIs foram detectadas
   - Validar qualidade dos dados

2. **Decisão técnica**
   - APIs detectadas → usar Requests
   - Sem APIs → continuar com Playwright

3. **Implementação completa**
   - Criar `orders_manager/adapters/delnext/`
   - Implementar scraper + mapper
   - Integrar com modelo `Order` genérico
   - Configurar Celery Beat (sync automático)

### Se POC falhar:

1. **Debug**
   - Revisar screenshots de erro
   - Ajustar seletores CSS
   - Testar manualmente no navegador

2. **Alternativas**
   - Tentar com credenciais diferentes
   - Contatar Delnext para API oficial
   - Considerar outras abordagens

## 🔐 Segurança

⚠️ **IMPORTANTE:**
- Credenciais estão hardcoded no POC (apenas para teste)
- Em produção, usar variáveis de ambiente
- Não commitar credenciais reais

```python
# Produção:
username = os.getenv("DELNEXT_USERNAME")
password = os.getenv("DELNEXT_PASSWORD")
```

## 📞 Suporte

Problemas com o POC?
1. Verificar logs em console
2. Revisar screenshots em `debug_files/delnext_poc/`
3. Executar `test_playwright_install.py` para validar ambiente

---

**Desenvolvido por:** Léguas Franzinas IT Team  
**Data:** 01/03/2026  
**Versão:** 1.0.0
