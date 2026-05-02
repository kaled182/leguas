# Atualização POC Delnext - Seleção de Data + Filtro por Zona

## 🆕 Novas Funcionalidades (01/03/2026)

### 1. Seleção de Data Automática

O POC agora suporta seleção de data no datepicker do Delnext:

```python
# Data com dados confirmados (27/02/2026)
outbound_data = scraper.scrape_outbound(page, test_date="Feb 27, 2026")
```

**Formatos aceitos:**
- `"Feb 27, 2026"` (padrão americano)
- `"27/02/2026"` (formato BR - será convertido)
- `"2026-02-27"` (ISO 8601)

### 2. 🎯 Filtro por Destination Zone (NOVO!)

Filtre automaticamente apenas as entregas da sua zona operacional:

```python
# Filtrar apenas VianaCastelo
outbound_data = scraper.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="VianaCastelo"  # 🔥 NOVO parâmetro
)

# Outras opções de filtro:
zone_filter="Lisboa"          # Todas as zonas com "Lisboa"
zone_filter="2.0 Lisboa"      # Zona específica
zone_filter="Margem Sul"      # Região Sul
zone_filter=None              # Sem filtro (todas as zonas)
```

**Saída com filtro:**
```
📤 FASE 3: Capturando Outbound (Previsão de Entregas)
   ✅ Total extraído: 30 entregas agendadas
   🔍 Filtro aplicado: Destination Zone = 'VianaCastelo'
   ✅ Resultados filtrados: 13 de 30 (43.3%)
```

**Benefícios:**
- ✅ Reduz ruído de outras zonas
- ✅ Foco apenas nas entregas relevantes
- ✅ JSON menor e mais rápido de processar
- ✅ Útil para empresas multi-regionais

### 3. Detecção de Tabelas Vazias

O POC agora detecta automaticamente quando tabelas estão vazias:

```
⚠️ TABELA VAZIA - Nenhuma entrega agendada para esta data
💡 Solução: Selecionar data específica no datepicker
   Exemplo: 27/02/2026 (data com dados confirmados)
```

### 3. Parser Preciso da Estrutura Real

Baseado nas screenshots reais do sistema, o parser agora extrai **11 campos**:

**Estrutura Outbound (Real):**
```python
{
    "product_id": "7495108",           # ID do pedido
    "destination_zone": "VianaCastelo", # Zona de destino
    "customer_name": "Mafalda Ferreira", # Nome do cliente
    "address": "Rua de Mureles, ...",   # Endereço completo
    "postal_code": "4420-213",          # Código postal
    "city": "Gondomar, Portugal",       # Cidade
    "date": "2026-02-27 11:36:39",      # Data/hora agendada
    "status": "Enviada",                # Status da entrega
    "admin": "operacoes",               # Admin responsável
    "inbound_date": "",                 # Data de entrada
    "inbound_by": ""                    # Recebido por
}
```

**Campos Críticos para Planejamento de Rotas:**
- ✅ `destination_zone` - Zona (ex: VianaCastelo, 2.0 Lisboa)
- ✅ `city` - Cidade de destino
- ✅ `postal_code` - Código postal
- ✅ `date` - Data/hora agendada
- ✅ `address` - Endereço completo

---

## 📊 Dados Reais Confirmados

### Outbound - 27/02/2026

**Zonas detectadas nas screenshots:**
- VianaCastelo (Portugal)
- 2.0 Lisboa
- 1.9 Lisboa
- 2.3 Lisboa
- Margem Sul 2
- Santarem1
- Coimbra2
- Algarve
- Funchal
- Margem Sul 2
- Minho2

**Exemplo de entregas reais:**
```json
[
  {
    "product_id": "7495108",
    "destination_zone": "VianaCastelo",
    "customer_name": "Mafalda Ferreira",
    "city": "Gondomar, Portugal",
    "postal_code": "4420-213",
    "date": "2026-02-27 11:36:39"
  },
  {
    "product_id": "7505076",
    "destination_zone": "VianaCastelo",
    "customer_name": "Nogyal Raman Nagyal",
    "city": "Cemitério",
    "postal_code": "4920-100",
    "date": "2026-02-27 11:45:05"
  }
]
```

**Total de entregas:** 30+ pacotes visíveis nas screenshots

---

## 🔧 Como Usar

### Executar POC com Filtro VianaCastelo (Padrão)

```powershell
# Executar POC (já configurado para VianaCastelo + 27/02/2026)
python delnext_poc_playwright.py
```

O POC vai:
1. ✅ Fazer login
2. ✅ Selecionar data 27/02/2026 no datepicker
3. ✅ Extrair **todas** as entregas da tabela
4. ✅ **Filtrar apenas zona VianaCastelo**
5. ✅ Gerar JSON com dados filtrados

**Saída esperada:**
```
📤 FASE 3: Capturando Outbound (Previsão de Entregas)
   📅 Selecionando data: Feb 27, 2026
   ✅ Tabela encontrada
   📋 Total de linhas na tabela: 31
   ✅   1. 7495108 → Gondomar (VianaCastelo)
   ✅   2. 7505076 → Cemitério (VianaCastelo)
   ...
   ✅  30. 7530123 → Matotinhos (2.0 Lisboa)
   
   🎯 Total extraído: 30 entregas agendadas
   🔍 Filtro aplicado: Destination Zone = 'VianaCastelo'
   ✅ Resultados filtrados: 13 de 30 (43.3%)
```

### Testar com Outra Zona

Editar `delnext_poc_playwright.py` (linha ~543):

```python
# Exemplo 1: Filtrar Lisboa
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="Lisboa"  # Todas as zonas com "Lisboa"
)

# Exemplo 2: Zona específica de Lisboa
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="2.0 Lisboa"  # Somente zona 2.0
)

# Exemplo 3: Sem filtro (todas as zonas)
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter=None  # Retorna tudo
)
```

### Testar com Outra Data

```python
# Linha ~543
outbound_data = self.scrape_outbound(
    page, 
    test_date="Mar 15, 2026",
    zone_filter="VianaCastelo"
)
```

### Verificar Resultados

```powershell
# Ver JSON gerado
cat debug_files/delnext_poc/delnext_data_sample.json

# Ver screenshots
explorer.exe debug_files\delnext_poc\
```

---

## 📸 Screenshots Relevantes

O POC agora gera screenshots mais informativos:

1. **01_login_page.png** - Página de login
2. **02_after_login.png** - Dashboard após login
3. **03_inbound_page.png** - Tabela Inbound
4. **04_outbound_page.png** - **Tabela Outbound com dados** ⭐
5. **05_stats_page.png** - Estatísticas
6. **06_final_page.png** - Estado final

---

## 🎯 Próximos Passos

### 1. Validar POC

```powershell
# Executar POC
python delnext_poc_playwright.py

# Verificar saída:
# ✅ Login: SUCESSO
# ✅ Outbound: 30+ entregas capturadas
# ✅ Estrutura JSON correta
```

### 2. Implementar Adapter Completo

```
orders_manager/adapters/delnext/
├── scraper.py              # BaseadO no POC
├── mapper.py               # Delnext → Order
├── status_mapping.py       # "Enviada" → "IN_TRANSIT"
└── __init__.py
```

### 3. Mapeamento de Status

**Status Delnext → Sistema Genérico:**
- `"Enviada"` → `"IN_TRANSIT"`
- `"Entregue"` → `"DELIVERED"`
- `"Pendente"` → `"PENDING"`
- `"Incidente"` → `"INCIDENT"`

### 4. Sincronização Automática

**Frequências recomendadas:**
- **Outbound**: 1x/dia às 23:00 (planejamento dia seguinte)
- **Inbound**: 2x/dia (manhã + tarde)
- **Stats**: A cada hora (monitoramento)

---

## 🐛 Troubleshooting

### Tabela vazia mesmo com data correta

**Causa:** Datepicker pode não aceitar formato direto

**Solução:** Ajustar seletor do datepicker:
```python
# Testar diferentes seletores
date_input = page.query_selector("input.datepicker")
date_input.click()  # Abrir calendário
page.click("td[data-date='27']")  # Clicar dia 27
```

### Campos extraídos errados

**Causa:** Ordem das colunas pode variar

**Solução:** Usar headers para mapear colunas dinamicamente:
```python
headers = [cell.text_content() for cell in row.query_selector_all("th")]
column_index = headers.index("Product ID")
product_id = cells[column_index].text_content()
```

### Dados incompletos

**Causa:** Paginação (tabela com 100+ registros)

**Solução:** Detectar e navegar paginação:
```python
# Procurar botão "Next"
next_button = page.query_selector("a:has-text('Next')")
if next_button:
    next_button.click()
    # Extrair próxima página
```

---

## 📝 Notas Técnicas

### Sistema Delnext
- **Tipo:** PHP server-side rendering (Zen Cart)
- **Frontend:** jQuery + Datepicker
- **API REST:** ❌ Não possui
- **Solução:** Playwright (única opção viável)

### Performance
- **Login:** ~2s
- **Scraping Outbound:** ~3-5s (30 registros)
- **Total POC:** ~15-20s

### Limitações
- ⚠️ Datepicker pode ter comportamento inconsistente
- ⚠️ Paginação não implementada (max 100 registros por página)
- ⚠️ Sem webhook/notificações (pull only)

---

**Atualizado:** 01/03/2026  
**Versão POC:** 1.1.0  
**Status:** ✅ Pronto para implementação completa
