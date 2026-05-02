# 🐛 Correções de Bugs - Integração Delnext

## Data: 01/03/2026

---

## ❌ Problemas Encontrados

### Erro 1: Import Error na Sincronização
**Erro:**
```python
cannot import name 'get_sync_service' from 'core.services' (/app/core/services/__init__.py)
```

**Causa Raiz:**
- Conflito de módulos: Existiam AMBOS `core/services.py` (arquivo) E `core/services/` (pasta)
- Python prioriza a pasta, então `from core.services import X` importava de `core/services/__init__.py`
- A função `get_sync_service` e classe `DelnextSyncService` estavam em `core/services.py` (arquivo)
- O `__init__.py` da pasta não exportava essas funções

**Onde Aparecia:**
- Ao clicar em "Sincronizar Agora" na página do parceiro Delnext
- View `partner_sync_manual` em [core/views.py](d:\app.leguasfranzinas.pt\app.leguasfranzinas.pt\core\views.py) linha 263

---

### Erro 2: AttributeError no Dashboard Delnext
**Erro:**
```python
AttributeError at /core/delnext/dashboard/
'Partner' object has no attribute 'partnerintegration_set'
```

**Causa Raiz:**
- Uso incorreto do related_name
- O modelo `PartnerIntegration` define `related_name="integrations"` (não o padrão `partnerintegration_set`)
- View usava `partner.partnerintegration_set` em vez de `partner.integrations`

**Onde Aparecia:**
- Ao acessar `/core/delnext/dashboard/`
- View `delnext_dashboard` em [core/views.py](d:\app.leguasfranzinas.pt\app.leguasfranzinas.pt\core\views.py) linha 421

---

## ✅ Soluções Aplicadas

### Solução 1: Exportar `get_sync_service` do Package

**Arquivo Modificado:** [core/services/__init__.py](d:\app.leguasfranzinas.pt\app.leguasfranzinas.pt\core\services\__init__.py)

**O que foi feito:**
1. ✅ Copiado código da classe `DelnextSyncService` do `services.py` para `services/__init__.py`
2. ✅ Copiado função `get_sync_service` para `services/__init__.py`
3. ✅ Adicionado ao `__all__` para exportação:
   ```python
   __all__ = [
       "PartnerSyncService", 
       "PaackAPIConnector", 
       "PartnerDataProcessor",
       "DelnextSyncService",      # ✨ NOVO
       "get_sync_service",        # ✨ NOVO
   ]
   ```

**Benefício:**
- Agora `from core.services import get_sync_service` funciona corretamente
- Mantém compatibilidade com código existente
- Centraliza serviços na pasta `core/services/`

---

### Solução 2: Corrigir Related Name

**Arquivo Modificado:** [core/views.py](d:\app.leguasfranzinas.pt\app.leguasfranzinas.pt\core\views.py) linha 421

**Mudança:**
```python
# ❌ ANTES (ERRADO):
last_integration = partner.partnerintegration_set.filter(is_active=True).first()

# ✅ DEPOIS (CORRETO):
last_integration = partner.integrations.filter(is_active=True).first()
```

**Benefício:**
- Dashboard Delnext agora carrega sem erro
- Mostra última sincronização corretamente
- Consistente com o related_name definido no modelo

---

## 🔧 Ação Tomada

### Container Reiniciado
```bash
docker-compose restart web
```

**Status:** ✅ Container reiniciado com sucesso

---

## ✅ Testes Recomendados

### 1. Testar Sincronização Manual

**Passos:**
1. Acesse: http://localhost:8000/core/partners/5/
2. Clique em **"Sincronizar Agora"**
3. Modal deve abrir normalmente
4. Configure data e zona (ou deixe vazio)
5. Clique em **"Executar Sincronização"**
6. ✅ **Esperado**: Sincronização inicia sem erro de import

**Como Verificar:**
- Se aparecer erro de import → ainda tem problema
- Se aparecer erro de Playwright/scraping → import está OK, problema é outro

---

### 2. Testar Dashboard Delnext

**Passos:**
1. Acesse: http://localhost:8000/core/delnext/dashboard/
2. ✅ **Esperado**: Página carrega sem AttributeError
3. Verifica estatísticas de pedidos
4. Verifica última sincronização

**Como Verificar:**
- Se carregar normalmente → problema resolvido
- Se aparecer AttributeError → ainda tem problema (verificar logs)

---

### 3. Verificar Logs (Caso Ainda Haja Erro)

```bash
# Ver últimos 50 logs do container
docker logs --tail 50 leguas_web

# Filtrar erros
docker logs leguas_web 2>&1 | grep -i error

# Acompanhar em tempo real
docker logs -f leguas_web
```

---

## 📊 Status Final

| Item | Status | Observação |
|------|--------|------------|
| Import `get_sync_service` | ✅ CORRIGIDO | Adicionado ao `__init__.py` |
| AttributeError `partnerintegration_set` | ✅ CORRIGIDO | Alterado para `integrations` |
| Container reiniciado | ✅ COMPLETO | Pronto para testar |
| Testes manuais | ⏳ PENDENTE | Usuário deve validar |

---

## 🐛 Problemas Conhecidos Adicionais

### Se Sincronização Falhar com Erro de Playwright:

**Possíveis Causas:**
1. Playwright não instalado no container
2. Chromium não disponível
3. Credenciais Delnext incorretas
4. URL Delnext mudou

**Como Diagnosticar:**
```bash
# Ver logs completos da sincronização
docker logs leguas_web | grep "DELNEXT SYNC"

# Testar Playwright manualmente
docker exec leguas_web python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

**Soluções:**
- Se Playwright não instalado → rebuild container
- Se credenciais erradas → atualizar auth_config da integração
- Se URL mudou → atualizar endpoint_url da integração

---

## 📝 Próximos Passos

1. ✅ **Testar sincronização manual** (via frontend)
2. ✅ **Testar dashboard Delnext**
3. ✅ **Verificar se pedidos são criados** após sincronização
4. ✅ **Validar logs** para garantir que não há outros erros

---

## 💡 Lições Aprendidas

### Conflito de Módulos Python
- ❌ **Evitar**: Ter `module.py` E `module/` no mesmo diretório
- ✅ **Preferir**: Usar apenas pasta com `__init__.py` OU apenas arquivo .py
- ⚠️ **Python prioriza**: Pasta sobre arquivo no import

### Related Names Django
- ✅ **Sempre usar**: O `related_name` definido no modelo
- ❌ **Nunca assumir**: O nome padrão `_set` se `related_name` está definido
- 💡 **Verificar**: `model._meta.related_objects` para descobrir related_name

---

**Autor:** GitHub Copilot  
**Data:** 01/03/2026 21:36  
**Status:** ✅ Correções Aplicadas - Aguardando Validação
