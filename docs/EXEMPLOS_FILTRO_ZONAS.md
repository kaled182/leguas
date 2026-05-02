# 🔍 Exemplos de Uso: Filtro por Destination Zone

## Contexto

O POC Delnext agora suporta filtro por **Destination Zone** para extrair apenas entregas relevantes à sua operação.

**Por que usar filtro?**
- 🎯 Reduz ruído de outras zonas/regiões
- ⚡ JSON menor e processamento mais rápido
- 📊 Relatórios focados na sua área operacional
- 🚚 Planejamento de rotas mais eficiente

---

## 🌍 Zonas Disponíveis (Delnext)

Baseado nos dados reais extraídos em 27/02/2026:

### Zonas Principais
- **VianaCastelo** (Portugal - Norte)
- **2.0 Lisboa** (Lisboa - Centro)
- **1.9 Lisboa** (Lisboa - Centro)
- **2.3 Lisboa** (Lisboa - Expansão)
- **Margem Sul 2** (Lisboa - Sul do Tejo)
- **Santarem1** (Região Centro)
- **Coimbra2** (Região Centro)
- **Algarve** (Sul de Portugal)
- **Funchal** (Madeira)
- **Minho2** (Norte de Portugal)

---

## 📝 Exemplos Práticos

### Exemplo 1: Filtrar apenas VianaCastelo (padrão do POC)

```python
# delnext_poc_playwright.py (linha ~543)
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="VianaCastelo"
)
```

**Resultado esperado:**
```
🎯 Total extraído: 30 entregas agendadas
🔍 Filtro aplicado: Destination Zone = 'VianaCastelo'
✅ Resultados filtrados: 13 de 30 (43.3%)
```

**JSON gerado:**
```json
{
  "outbound": [
    {
      "product_id": "7495108",
      "destination_zone": "VianaCastelo",
      "city": "Gondomar, Portugal",
      "postal_code": "4420-213"
    },
    {
      "product_id": "7505076",
      "destination_zone": "VianaCastelo",
      "city": "Cemitério",
      "postal_code": "4920-100"
    }
    // ... mais 11 entregas
  ]
}
```

---

### Exemplo 2: Filtrar TODAS as zonas de Lisboa

```python
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="Lisboa"  # Match: "2.0 Lisboa", "1.9 Lisboa", "2.3 Lisboa"
)
```

**Resultado esperado:**
```
🔍 Filtro aplicado: Destination Zone = 'Lisboa'
✅ Resultados filtrados: 12 de 30 (40.0%)
```

**Zonas incluídas:**
- ✅ 2.0 Lisboa
- ✅ 1.9 Lisboa
- ✅ 2.3 Lisboa
- ❌ Margem Sul 2 (não contém "Lisboa" exato)

---

### Exemplo 3: Filtrar zona específica de Lisboa (2.0)

```python
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="2.0 Lisboa"  # Match EXATO
)
```

**Resultado esperado:**
```
🔍 Filtro aplicado: Destination Zone = '2.0 Lisboa'
✅ Resultados filtrados: 5 de 30 (16.7%)
```

**Zonas incluídas:**
- ✅ 2.0 Lisboa
- ❌ 1.9 Lisboa
- ❌ 2.3 Lisboa

---

### Exemplo 4: Filtrar Margem Sul

```python
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="Margem Sul"
)
```

**Resultado esperado:**
```
🔍 Filtro aplicado: Destination Zone = 'Margem Sul'
✅ Resultados filtrados: 3 de 30 (10.0%)
```

---

### Exemplo 5: SEM filtro (todas as zonas)

```python
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter=None  # Ou omitir o parâmetro
)
```

**Resultado esperado:**
```
🎯 Total extraído: 30 entregas agendadas
(Sem mensagem de filtro)
```

**JSON contém TODAS as 30 entregas** (todas as zonas)

---

## 🔧 Como Personalizar para Sua Operação

### Cenário 1: Empresa Opera Apenas em VianaCastelo

```python
# Configuração padrão (já está assim no POC)
zone_filter="VianaCastelo"
```

**Benefício:** Extrai apenas suas ~13 entregas diárias

---

### Cenário 2: Empresa Opera em Múltiplas Zonas

**Opção A: Executar POC 2x (uma por zona)**

```python
# Run 1: VianaCastelo
outbound_viana = self.scrape_outbound(page, test_date="Feb 27, 2026", zone_filter="VianaCastelo")

# Run 2: Lisboa
outbound_lisboa = self.scrape_outbound(page, test_date="Feb 27, 2026", zone_filter="Lisboa")

# Combinar resultados
all_data = outbound_viana + outbound_lisboa
```

**Opção B: Sem filtro + processar localmente**

```python
# Extrair tudo
all_outbound = self.scrape_outbound(page, test_date="Feb 27, 2026", zone_filter=None)

# Filtrar em Python
viana_only = [item for item in all_outbound if "VianaCastelo" in item['destination_zone']]
lisboa_only = [item for item in all_outbound if "Lisboa" in item['destination_zone']]
```

---

### Cenário 3: Empresa Opera em TODO o País

```python
# Sem filtro
zone_filter=None
```

**Benefício:** Extrai todas as ~30-50 entregas diárias

---

## 🎯 Integração com Sistema Genérico

### Adapter Pattern (Produção)

```python
# orders_manager/adapters/delnext/scraper.py

class DelnextScraper:
    def __init__(self, company_zones: list):
        """
        Args:
            company_zones: Lista de zonas operacionais da empresa
                          Ex: ["VianaCastelo", "Minho2"]
        """
        self.company_zones = company_zones
    
    def sync_outbound(self, date: str):
        """Sincroniza outbound filtrando por zonas da empresa"""
        
        # Opção 1: Multiple filters (uma query por zona)
        all_data = []
        for zone in self.company_zones:
            zone_data = self.scrape_outbound(
                page, 
                test_date=date,
                zone_filter=zone
            )
            all_data.extend(zone_data)
        
        # Opção 2: Single query + filter local (mais rápido)
        all_data = self.scrape_outbound(page, test_date=date, zone_filter=None)
        filtered = [
            item for item in all_data 
            if any(zone in item['destination_zone'] for zone in self.company_zones)
        ]
        
        return filtered
```

**Uso:**
```python
# Django command: sync_delnext
scraper = DelnextScraper(company_zones=["VianaCastelo"])
deliveries = scraper.sync_outbound(date="Feb 27, 2026")

# Mapear para Order genérico
for delivery in deliveries:
    Order.objects.update_or_create(
        tracking_number=delivery['product_id'],
        partner=Partner.objects.get(name='Delnext'),
        defaults={
            'delivery_zone': delivery['destination_zone'],
            'city': delivery['city'],
            'postal_code': delivery['postal_code'],
            # ... outros campos
        }
    )
```

---

## 🐛 Troubleshooting

### Filtro retorna 0 resultados

**Problema:**
```
⚠️ Nenhuma entrega encontrada para zona 'VianaCastelo'
```

**Possíveis causas:**
1. **Nome da zona digitado errado**
   - Solução: Verificar exatamente como aparece no Delnext
   - Ex: "VianaCastelo" vs "Viana Castelo" vs "vianaCastelo"

2. **Data sem entregas para essa zona**
   - Solução: Testar com data conhecida (27/02/2026)

3. **Filtro case-sensitive**
   - **JÁ RESOLVIDO**: O filtro usa `.lower()` (case-insensitive)
   - `"VianaCastelo"` = `"vianaCastelo"` = `"VIANACASTELO"`

**Debug:**
```python
# Executar SEM filtro primeiro para ver zonas disponíveis
outbound_all = self.scrape_outbound(page, test_date="Feb 27, 2026", zone_filter=None)

# Ver todas as zonas detectadas
zones = set([item['destination_zone'] for item in outbound_all])
print(f"Zonas disponíveis: {zones}")
```

---

### Filtro parcial não funciona

**Problema:** Quer filtrar "Lisboa" mas só retorna "2.0 Lisboa"

**Explicação:** O filtro usa `in`, então:
```python
zone_filter="Lisboa"  # Match: "2.0 Lisboa", "1.9 Lisboa", "Lisboa Centro"
zone_filter="2.0"     # Match: "2.0 Lisboa" apenas
```

**Se quiser match exato:**
```python
# Modificar POC (linha de filtro)
# ANTES:
data = [item for item in data if zone_filter.lower() in item['destination_zone'].lower()]

# DEPOIS (match exato):
data = [item for item in data if zone_filter.lower() == item['destination_zone'].lower()]
```

---

## 📊 Performance

### Comparação: Com vs Sem Filtro

**Cenário: 100 entregas totais, 20 para VianaCastelo**

| Métrica | Sem Filtro | Com Filtro | Ganho |
|---------|-----------|-----------|-------|
| Extração | ~5s | ~5s | 0% |
| JSON Size | 50KB | 10KB | **80%** |
| Processamento | ~2s | ~0.4s | **80%** |
| Insert DB | ~5s | ~1s | **80%** |
| **TOTAL** | **~12s** | **~6.4s** | **47%** |

**Conclusão:** Filtro NÃO acelera scraping, mas **acelera processamento**.

---

## 🎓 Boas Práticas

### ✅ RECOMENDADO

```python
# 1. Usar filtro para reduzir dados irrelevantes
zone_filter="VianaCastelo"

# 2. Combinar com data específica
test_date="Feb 27, 2026"
zone_filter="VianaCastelo"

# 3. Logging claro
print(f"Filtrando zona: {zone_filter}")
```

### ❌ NÃO RECOMENDADO

```python
# 1. Filtro muito genérico
zone_filter="a"  # Match quase tudo!

# 2. Múltiplas queries desnecessárias
for zone in ["VianaCastelo", "Minho2", "Porto"]:
    # 3 queries = 3x mais lento
    data = scrape_outbound(page, zone_filter=zone)

# MELHOR: 1 query + filtro local
all_data = scrape_outbound(page, zone_filter=None)
filtered = filter_zones(all_data, ["VianaCastelo", "Minho2"])
```

---

**Atualizado:** 01/03/2026  
**Versão:** 1.2.0  
**Status:** ✅ Produção-ready
