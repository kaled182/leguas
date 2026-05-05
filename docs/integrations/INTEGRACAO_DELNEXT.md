# Integração Delnext

Integração completa para importar previsões de entrega do Delnext (Outbound) via web scraping.

## 📋 Visão Geral

O sistema automatiza a importação de dados de previsão de entregas do Delnext para o Orders Manager, permitindo:

- ✅ Scraping autenticado com bypass de Cloudflare
- ✅ Filtro por data e zona diretamente na URL
- ✅ Importação automática para modelo Order
- ✅ Mapeamento de status e dados
- ✅ Suporte a múltiplas zonas

## 🚀 Uso Rápido

### Comando Básico

```bash
# Importar última sexta-feira, zona VianaCastelo
python manage.py sync_delnext

# Testar sem salvar (dry-run)
python manage.py sync_delnext --dry-run
```

### Exemplos Avançados

```bash
# Data específica
python manage.py sync_delnext --date 2026-02-27

# Zona específica (Lisboa)
python manage.py sync_delnext --zone "2.0 Lisboa"

# Data + Zona
python manage.py sync_delnext --date 2026-02-27 --zone VianaCastelo

# Credenciais customizadas
python manage.py sync_delnext \
    --username MeuUsuario \
    --password MinhaSenha \
    --zone Minho2
```

## 🔧 Configuração

### 1. Instalar Playwright

```bash
pip install playwright
playwright install chromium
```

### 2. Criar Partner Delnext (se não existir)

O comando cria automaticamente, mas você pode personalizar:

```python
from core.models import Partner

Partner.objects.get_or_create(
    name="Delnext",
    defaults={
        "nif": "123456789",  # NIF real
        "contact_email": "operacoes@delnext.com",
        "contact_phone": "+351 XXX XXX XXX",
        "is_active": True,
    }
)
```

### 3. Configurar Credenciais (Opcional)

Editar `orders_manager/adapters.py`:

```python
class DelnextAdapter:
    def __init__(self, username=None, password=None):
        self.username = username or "SEU_USUARIO_PADRAO"
        self.password = password or "SUA_SENHA_PADRAO"
```

## 📊 Mapeamento de Dados

### Delnext → Order Model

| Campo Delnext      | Campo Order           | Notas                              |
|--------------------|----------------------|------------------------------------|
| product_id         | external_reference   | ID único da entrega                |
| customer_name      | recipient_name       | Nome do destinatário               |
| address            | recipient_address    | Endereço completo                  |
| postal_code        | postal_code          | Normalizado para XXXX-XXX          |
| city               | recipient_address    | Adicionado ao endereço             |
| destination_zone   | notes                | Zona de destino                    |
| date               | scheduled_delivery   | Data agendada de entrega           |
| status             | current_status       | Ver mapeamento de status           |

### Mapeamento de Status

| Status Delnext | Status Order | Descrição           |
|---------------|--------------|---------------------|
| Enviada       | IN_TRANSIT   | Em trânsito         |
| Entregue      | DELIVERED    | Entregue            |
| Pendente      | PENDING      | Pendente            |
| A processar   | PENDING      | A processar         |
| Devolvida     | RETURNED     | Devolvida           |
| Cancelada     | CANCELLED    | Cancelada           |

## 🗓️ Cálculo de Data Automático

Por padrão, o sistema usa a **última sexta-feira** se nenhuma data for especificada:

- **Segunda a Sexta**: Usa data atual
- **Sábado**: Usa sexta-feira anterior
- **Domingo**: Usa sexta-feira anterior

Isso porque o Delnext opera apenas de segunda a sexta-feira.

## 🎯 Zonas Disponíveis

Principais zonas do Delnext:

- `VianaCastelo`
- `2.0 Lisboa`
- `1.9 Lisboa`
- `2.3 Lisboa`
- `Margem Sul 2`
- `Minho2`
- `Porto4.0`
- `Gaia`
- `Coimbra2`
- `Algarve`
- (e outras...)

**Filtrar todas as zonas:**

```bash
python manage.py sync_delnext --zone "all"
```

## 🔄 Automação com Celery

### Criar Celery Task

Editar `orders_manager/tasks.py`:

```python
from celery import shared_task
from orders_manager.adapters import get_delnext_adapter

@shared_task
def sync_delnext_daily(zone="VianaCastelo"):
    """Sincroniza Delnext diariamente (última sexta-feira)"""
    adapter = get_delnext_adapter()
    data = adapter.fetch_outbound_data(zone=zone)
    stats = adapter.import_to_orders(data)
    return stats
```

### Agendar com Celery Beat

Editar `my_project/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'sync-delnext-daily': {
        'task': 'orders_manager.tasks.sync_delnext_daily',
        'schedule': crontab(hour=6, minute=0),  # Todo dia 6h
        'kwargs': {'zone': 'VianaCastelo'},
    },
}
```

## 🧪 Testes

### Teste Manual

```bash
# Dry-run (sem salvar)
python manage.py sync_delnext --dry-run

# Ver preview dos dados
python manage.py sync_delnext --dry-run --date 2026-02-27
```

### Usando o Adapter Diretamente

```python
from orders_manager.adapters import get_delnext_adapter

# Criar adapter
adapter = get_delnext_adapter()

# Buscar dados
data = adapter.fetch_outbound_data(
    date="2026-02-27",
    zone="VianaCastelo"
)

print(f"Encontrados {len(data)} pedidos")

# Importar
stats = adapter.import_to_orders(data)
print(stats)
# {'total': 144, 'created': 144, 'updated': 0, 'errors': 0}
```

## 🐛 Troubleshooting

### Erro: Playwright não instalado

```bash
pip install playwright
playwright install chromium
```

### Erro: Cloudflare Challenge

O adapter já implementa bypass automático. Se falhar:

1. Verificar se `headless=True` pode ser mudado para `headless=False`
2. Aumentar timeout em `adapters.py`
3. Adicionar mais delay após login

### Erro: Tabela vazia

Delnext opera apenas Segunda-Sexta. Verificar:

```bash
# Usar data de sexta-feira anterior
python manage.py sync_delnext --date 2026-02-27
```

### Erro: NIF inválido

Editar `adapters.py` e adicionar NIF real do Delnext:

```python
defaults={
    "nif": "123456789",  # NIF correto
    ...
}
```

## 📈 Performance

### Benchmarks

| Operação              | Tempo Médio | Notas                        |
|-----------------------|-------------|------------------------------|
| Login + Scraping      | ~20s        | Inclui bypass Cloudflare     |
| Extração 150 pedidos  | ~80s        | Depende da conexão           |
| Importação DB         | ~2s         | 150 pedidos                  |
| **Total**             | **~100s**   | Para 150 pedidos             |

### Otimizações

- ✅ Filtro server-side (zona na URL)
- ✅ Headless browser (faster)
- ✅ Bulk create/update (Django ORM)
- ✅ Reuso de conexão Playwright

## 🔐 Segurança

### Credenciais

**Nunca commitar credenciais!** Use variáveis de ambiente:

```python
import os

adapter = DelnextAdapter(
    username=os.environ.get("DELNEXT_USERNAME"),
    password=os.environ.get("DELNEXT_PASSWORD"),
)
```

Criar `.env`:

```bash
DELNEXT_USERNAME=VianaCastelo
DELNEXT_PASSWORD=HelloViana23432
```

## 📚 Referências

- **POC Original**: `delnext_auto_poc.py`
- **Documentação POC**: `EXEMPLOS_FILTRO_ZONAS.md`
- **Adapter**: `orders_manager/adapters.py` (DelnextAdapter)
- **Management Command**: `orders_manager/management/commands/sync_delnext.py`
- **Order Model**: `orders_manager/models.py`

## 🎯 Próximos Passos

1. ✅ Adapter criado e funcional
2. ✅ Management command implementado
3. ⏳ Celery task para automação
4. ⏳ Dashboard de monitoramento
5. ⏳ Notificações de erro (email/Slack)
6. ⏳ Relatórios de importação

---

**Última atualização**: 01/03/2026  
**Versão**: 1.0.0
