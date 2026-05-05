# COMANDOS RÁPIDOS - POC DELNEXT

## 🚀 Setup Rápido (Docker)

```powershell
# 1. Instalar Playwright no container
docker exec -it leguas_web pip install playwright

# 2. Instalar navegador Chromium
docker exec -it leguas_web playwright install chromium
docker exec -it leguas_web playwright install-deps chromium

# 3. Testar instalação
docker exec -it leguas_web python test_playwright_install.py

# 4. Executar POC (com filtro VianaCastelo padrão)
docker exec -it leguas_web python delnext_poc_playwright.py
```

## 📋 Comandos Principais

### Executar POC (Configuração Padrão)
```powershell
# Filtro: VianaCastelo | Data: 27/02/2026
docker exec -it leguas_web python delnext_poc_playwright.py
```

### 🎯 Testar Diferentes Filtros de Zona

```powershell
# Opção 1: Script interativo
docker exec -it leguas_web python test_filtro_zonas.py

# Opção 2: Editar POC manualmente
# Ver seção "Personalizar Filtro" abaixo
```

### Validar Instalação
```powershell
docker exec -it leguas_web python test_playwright_install.py
```

### Ver Screenshots Gerados
```powershell
# Listar arquivos
docker exec -it leguas_web ls -la debug_files/delnext_poc/

# Copiar para Windows (se necessário)
docker cp leguas_web:/app/debug_files/delnext_poc/ ./delnext_poc_results/
```

### Ver JSON Gerado
```powershell
docker exec -it leguas_web cat debug_files/delnext_poc/delnext_data_sample.json
```

## 🐛 Debug

### Ver logs completos
```powershell
docker exec -it leguas_web python delnext_poc_playwright.py 2>&1 | tee poc_output.log
```

### Executar com navegador visível (não-headless)
Editar `delnext_poc_playwright.py`:
```python
browser = p.chromium.launch(
    headless=False,  # Alterar para False
    args=['--start-maximized']
)
```

### Limpar arquivos antigos
```powershell
docker exec -it leguas_web rm -rf debug_files/delnext_poc/*
```

## 🔄 Atualizar Código

Se fizer alterações no POC:
```powershell
# Container já está rodando, só executar novamente
docker exec -it leguas_web python delnext_poc_playwright.py
```

## 🎯 Personalizar Filtro de Zona

### Editar Zona no POC

Abrir `delnext_poc_playwright.py` e modificar **linha ~543**:

```python
# EXEMPLO 1: Filtrar apenas VianaCastelo (padrão)
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="VianaCastelo"
)

# EXEMPLO 2: Filtrar todas as zonas de Lisboa
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="Lisboa"  # Match: 2.0 Lisboa, 1.9 Lisboa, etc.
)

# EXEMPLO 3: Filtrar zona específica de Lisboa
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter="2.0 Lisboa"  # Somente zona 2.0
)

# EXEMPLO 4: SEM filtro (todas as zonas)
outbound_data = self.scrape_outbound(
    page, 
    test_date="Feb 27, 2026",
    zone_filter=None
)
```

### Zonas Disponíveis

- `VianaCastelo` (Norte)
- `2.0 Lisboa` (Centro)
- `1.9 Lisboa` (Centro)
- `2.3 Lisboa` (Expansão)
- `Margem Sul 2` (Sul do Tejo)
- `Santarem1` (Centro)
- `Coimbra2` (Centro)
- `Algarve` (Sul)
- `Funchal` (Madeira)
- `Minho2` (Norte)

📖 **Ver mais exemplos:** [EXEMPLOS_FILTRO_ZONAS.md](EXEMPLOS_FILTRO_ZONAS.md)

## ⚙️ Configuração Avançada

### Usar credenciais de variáveis de ambiente
```powershell
docker exec -it leguas_web bash -c "DELNEXT_USER=VianaCastelo DELNEXT_PASS=HelloViana23432 python delnext_poc_playwright.py"
```

### Executar dentro do container (modo interativo)
```powershell
docker exec -it leguas_web bash

# Dentro do container:
cd /app
python delnext_poc_playwright.py
exit
```

## 📊 Verificar Resultados

### Sucesso esperado (com filtro VianaCastelo):
```
✅ LOGIN: SUCESSO ✅
📥 INBOUND: X registros capturados
📤 OUTBOUND: 30 entregas extraídas
🔍 FILTRO: Destination Zone = 'VianaCastelo'
✅ RESULTADOS: 13 de 30 entregas (43.3%)
📊 STATS: Página acessada SIM ✅
🔴 APIs detectadas: 0 endpoints (esperado)
⏱️ Tempo: ~15-30s
```

### Sucesso esperado (SEM filtro):
```
✅ LOGIN: SUCESSO ✅
📥 INBOUND: X registros capturados
📤 OUTBOUND: 30 entregas agendadas
📊 STATS: Página acessada SIM ✅
🔴 APIs detectadas: 0 endpoints
⏱️ Tempo: ~15-30s
```

### Se falhar:
1. Verificar screenshots em `debug_files/delnext_poc/error_*.png`
2. Revisar logs de erro no console
3. Validar credenciais
4. Ajustar seletores CSS se necessário

## 🎯 Próximo Passo

Após POC bem-sucedido:
```powershell
# Criar estrutura de adapters
mkdir -p orders_manager/adapters/delnext

# Começar implementação completa
# (seguir PLANO_INTEGRACAO_DELNEXT.md)
```
