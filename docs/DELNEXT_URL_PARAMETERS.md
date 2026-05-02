# 🔗 Parâmetros URL - Delnext Outbound

## ✨ Descoberta - 01/03/2026

O sistema Delnext permite filtrar dados **diretamente via URL**, eliminando a necessidade de interação com o datepicker JavaScript.

## 📖 Estrutura da URL

```
https://www.delnext.com/admind/outbound_consult.php?date_range={JSON}&zone={ZONE}
```

### Parâmetros

#### 1. `date_range` (obrigatório)
JSON URL-encoded com formato:
```json
{"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}
```

**Exemplo codificado:**
```
%7B%22start%22%3A%222026-02-27%22%2C%22end%22%3A%222026-02-27%22%7D
```

**Em Python:**
```python
import json
import urllib.parse

date_range = {"start": "2026-02-27", "end": "2026-02-27"}
encoded = urllib.parse.quote(json.dumps(date_range))
# Resultado: %7B%22start%22%3A%20%222026-02-27%22%2C%20%22end%22%3A%20%222026-02-27%22%7D
```

#### 2. `zone` (opcional)
Nome da zona de destino, ou `all` para todas as zonas.

**Valores comuns:**
- `VianaCastelo`
- `2.0 Lisboa`
- `Margem Sul 2`
- `Porto4.0`
- `all` (padrão)

## 🎯 Exemplos de URLs

### Exemplo 1: VianaCastelo (27/02/2026)
```
https://www.delnext.com/admind/outbound_consult.php?date_range=%7B%22start%22%3A%222026-02-27%22%2C%22end%22%3A%222026-02-27%22%7D&zone=VianaCastelo
```

**Resultado:**
- 144 entregas
- Todas da zona VianaCastelo
- Tempo de resposta: ~3s

### Exemplo 2: Todas as zonas (27/02/2026)
```
https://www.delnext.com/admind/outbound_consult.php?date_range=%7B%22start%22%3A%222026-02-27%22%2C%22end%22%3A%222026-02-27%22%7D&zone=all
```

**Resultado:**
- 3249 entregas
- Todas as zonas
- Tempo de resposta: ~10s

### Exemplo 3: Lisboa (27/02/2026)
```
https://www.delnext.com/admind/outbound_consult.php?date_range=%7B%22start%22%3A%222026-02-27%22%2C%22end%22%3A%222026-02-27%22%7D&zone=2.0%20Lisboa
```

**Note:** Espaços devem ser codificados como `%20`

## 🚀 Implementação em Python

### Função auxiliar
```python
def build_outbound_url(date: str, zone: str = "all") -> str:
    """
    Constrói URL do Delnext Outbound com parâmetros.
    
    Args:
        date: Data no formato "YYYY-MM-DD" (ex: "2026-02-27")
        zone: Nome da zona ou "all" (ex: "VianaCastelo")
    
    Returns:
        URL completa com parâmetros
    """
    import json
    import urllib.parse
    
    date_range = {"start": date, "end": date}
    date_range_encoded = urllib.parse.quote(json.dumps(date_range))
    
    base_url = "https://www.delnext.com/admind/outbound_consult.php"
    return f"{base_url}?date_range={date_range_encoded}&zone={zone}"
```

### Uso
```python
# Exemplo 1: VianaCastelo
url = build_outbound_url("2026-02-27", "VianaCastelo")
page.goto(url)

# Exemplo 2: Todas as zonas
url = build_outbound_url("2026-02-27", "all")
page.goto(url)

# Exemplo 3: Data atual
from datetime import datetime
today = datetime.now().strftime("%Y-%m-%d")
url = build_outbound_url(today, "VianaCastelo")
page.goto(url)
```

## 📊 Comparação de Performance

### Método Antigo (Datepicker JavaScript)
```
1. Navegar para outbound_consult.php
2. Aguardar página carregar (3s)
3. Procurar elemento de data
4. Clicar no dropdown
5. Aguardar calendário abrir (2s)
6. Clicar em "Last Week" ou dia específico
7. Procurar botão "Apply"
8. Clicar e aguardar reload (5s)
9. Extrair dados de TODAS as zonas (3249 linhas)
10. Filtrar em Python
```
**Total:** ~15-20 segundos

### Método Novo (URL Direta)
```
1. Construir URL com parâmetros
2. Navegar diretamente (3s)
3. Extrair dados JÁ FILTRADOS (144 linhas)
```
**Total:** ~5-8 segundos

**Ganho:** 60-70% mais rápido! ⚡

## ✅ Vantagens

1. **Performance**: Filtragem server-side (muito mais rápido)
2. **Confiabilidade**: Sem dependência de JavaScript customizado
3. **Simplicidade**: Menos código, menos pontos de falha
4. **Precisão**: Delnext retorna apenas dados solicitados
5. **Manutenibilidade**: URL é mais estável que seletores CSS

## ⚠️ Limitações

1. **Autenticação**: Requer sessão ativa (login prévio)
2. **Encoding**: Zona com caracteres especiais precisa de URL encoding
3. **Validação**: Delnext não valida zonas - zona inválida retorna 0 resultados

## 🔍 Descobrindo Mais Parâmetros

Para explorar outros parâmetros suportados, inspecione:

1. **Network Tab** do DevTools durante uso normal
2. **Formulários** na página (atributos `name`)
3. **JavaScript** que constrói requisições

### Possíveis parâmetros adicionais (não confirmados):
- `status`: Filtrar por status (ex: "Enviada", "Entregue")
- `customer`: Filtrar por cliente
- `product_id`: Filtrar por ID específico

## 📝 Notas Técnicas

### URL Encoding
- Espaços: ` ` → `%20`
- Vírgulas: `,` → `%2C`
- Dois-pontos: `:` → `%3A`
- Aspas: `"` → `%22`
- Chaves: `{` → `%7B`, `}` → `%7D`

### JSON Encoding
O parâmetro `date_range` aceita JSON com espaços:
```json
// Com espaços (funciona)
{"start": "2026-02-27", "end": "2026-02-27"}

// Sem espaços (funciona também)
{"start":"2026-02-27","end":"2026-02-27"}
```

## 🎓 Exemplo Completo

```python
from playwright.sync_api import sync_playwright
import json
import urllib.parse
from datetime import datetime, timedelta

def get_last_friday():
    """Retorna última sexta-feira"""
    today = datetime.now()
    days_back = (today.weekday() - 4) % 7
    if days_back == 0 and today.weekday() != 4:
        days_back = 7
    friday = today - timedelta(days=days_back)
    return friday.strftime("%Y-%m-%d")

def scrape_delnext_zone(zone: str = "VianaCastelo"):
    """Extrai entregas de uma zona específica"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # 1. Login (código omitido)
        # ...
        
        # 2. Construir URL
        date = get_last_friday()
        date_range = {"start": date, "end": date}
        encoded = urllib.parse.quote(json.dumps(date_range))
        url = f"https://www.delnext.com/admind/outbound_consult.php?date_range={encoded}&zone={zone}"
        
        # 3. Navegar
        page.goto(url, timeout=30000)
        
        # 4. Extrair dados
        rows = page.query_selector_all("table tr")
        # ... processar linhas
        
        browser.close()

# Uso
scrape_delnext_zone("VianaCastelo")  # 144 entregas
scrape_delnext_zone("2.0 Lisboa")     # ~800 entregas
scrape_delnext_zone("all")            # 3249 entregas
```

## 🎉 Conclusão

A descoberta dos parâmetros URL transforma o POC Delnext de uma automação complexa e frágil em uma integração simples e robusta. **Use sempre este método!**

---
**Última atualização:** 01/03/2026  
**Descoberto por:** Paulo Adriano (via análise de URLs do navegador)
