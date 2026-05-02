# Plano de Integração Delnext - Web Scraping

> **⚠️ REVISÃO ARQUITETURAL (01/03/2026)**  
> Este plano foi ajustado para seguir o **Padrão Adapter**, integrando-se ao modelo genérico `Order` do app `orders_manager` em vez de criar modelos específicos. Isso mantém a consistência com a arquitetura consolidada no sistema.

## 🏗️ DECISÃO ARQUITETURAL CRÍTICA

### ❌ O Que NÃO Fazer

**Criar modelos específicos como `DelnextOrder`, `DelnextDriver`, etc.**

**Por que evitar:**
- Repete o erro do `ordersmanager_paack` (sistema legado que estamos migrando)
- Daqui a 6 meses, teríamos `EcoscootingOrder`, `GlovoOrder`, etc.
- Dashboards e relatórios teriam que consultar 5+ tabelas diferentes
- Quebra a promessa de sistema genérico multi-partner

### ✅ A Solução: Padrão Adapter

**O scraper é apenas um "adaptador" que converte dados Delnext → modelo genérico `Order`**

```python
# ✅ CORRETO: Usa modelo genérico
from orders_manager.models import Order
from core.models import Partner

def process_delnext_data(scraped_data):
    partner = Partner.objects.get(name="Delnext")
    
    Order.objects.update_or_create(
        tracking_number=scraped_data['parcel_id'],
        partner=partner,
        defaults={
            'customer_name': scraped_data['admin_name'],
            'delivery_address': scraped_data['city'],
            'postal_code': scraped_data['destination_zone'],
            'status': normalize_delnext_status(scraped_data['status']),
            'weight': scraped_data['weight'],
            'is_cod': scraped_data.get('is_cod', False),
            'comments': scraped_data.get('comment', ''),
        }
    )

# ❌ ERRADO: Modelo específico (NÃO FAZER)
# DelnextOrder.objects.create(...)
```

**Benefícios:**
- ✅ Um único dashboard para TODOS os parceiros
- ✅ Relatórios unificados (settlements, analytics)
- ✅ Fácil adicionar novos parceiros (apenas novo adapter)
- ✅ Consistência com Paack, Amazon, DPD, Glovo

---

## 📊 ANÁLISE DO SISTEMA DELNEXT

### Sistema Atual
- **URL Base**: https://www.delnext.com/admind/
- **Tipo**: Painel administrativo PHP (sem API REST)
- **Autenticação**: Login tradicional (usuário/senha)
- **Credenciais**: VianaCastelo / HelloViana23432

### Páginas Principais

#### 1. **Inbound Partners** (`inbound_partners.php`)
- **Função**: Recebimento de encomendas do dia
- **Dados**: Parcel ID, Admin Name, Warehouse, Destination Zone, Country, City, Date, Comment
- **Status**: Tabela pode estar vazia se não houver atividade

#### 2. **Outbound Consult** (`outbound_consult.php`)
- **Função**: Previsão de pacotes para o dia seguinte
- **Dados**: Lista de encomendas agendadas para entrega
- **Importância**: ⭐⭐⭐⭐⭐ (Planejamento de rotas)

#### 3. **Application Stats** (`application_stats.php`)
- **Função**: Dashboard operacional do dia
- **Dados**:
  - Lista de motoristas ativos (vianacastelo1, vianacastelo10, vianacastelo11, etc.)
  - Incidências do dia
  - Entregas do dia (COD, status, peso)
  - Resumo de cobranças/reembolsos por motorista
  - Recolhas realizadas com sucesso
  - Recolhas não realizadas/com incidência
  - Late Parcels (encomendas atrasadas)

#### 4. **Application Stats Operations** (`application_stats_operations.php`)
- **Função**: Pesquisa e gestão operacional
- **Dados**:
  - Procurar encomenda específica (por Parcel ID)
  - Encomendas em distribuição
  - Status detalhado (Confirmed, COD, Postal Code, Destination, Weight, Tracking)
  - Gestão de incidências

---

## 🔍 ANÁLISE TÉCNICA - OPÇÕES DE IMPLEMENTAÇÃO

### Opção 1: **Web Scraping com Playwright** ⭐⭐⭐ RECOMENDADO

**Tecnologia**: Python + Playwright

**Como Funciona:**
1. Abre navegador headless (Chrome/Firefox sem interface)
2. Faz login automatizado
3. Navega pelas páginas
4. Extrai dados das tabelas HTML
5. Salva no banco de dados Django

**Prós:**
- ✅✅✅ **2-3x mais rápido que Selenium**
- ✅ Auto-waiting (aguarda elementos sem `time.sleep()`)
- ✅ Funciona perfeitamente em Docker (binários isolados)
- ✅ **Network Interception** (detecta APIs escondidas automaticamente)
- ✅ Mantém sessão de login automaticamente
- ✅ Screenshots/PDFs nativos para debug
- ✅ API moderna e intuitiva

**Contras:**
- ❌ Requer mais recursos que Requests puro (~500MB RAM)
- ❌ Frágil a mudanças no HTML (mitigado com bons seletores)

**Por que Playwright > Selenium para este projeto:**
1. **Docker-Friendly**: Selenium + ChromeDriver quebra constantemente em containers. Playwright instala navegadores isolados.
2. **Velocidade**: Playwright é nativo async, Selenium é síncrono bloqueante.
3. **Investigação + Scraping em 1**: Playwright monitora rede enquanto navega (detecta APIs JSON escondidas).

**DECISÃO FINAL: Usar 100% Playwright para Delnext**

---

### ~~Opção 2: Web Scraping com Requests + BeautifulSoup~~ (NÃO RECOMENDADO)

**Tecnologia**: Python + Requests + BeautifulSoup4

**Como Funciona:**
1. Faz requisição POST para login
2. Salva cookies de sessão
3. Faz requisições GET para cada página
4. Parseia HTML com BeautifulSoup
5. Extrai dados das tabelas

**Prós:**
- ✅ Muito mais rápido
- ✅ Usa menos recursos
- ✅ Mais estável
- ✅ Fácil de debugar

**Contras:**
- ❌ Não executa JavaScript
- ❌ Precisa gerenciar cookies manualmente
- ❌ Difícil com autenticação complexa (CSRF tokens, etc.)

**Quando Usar:**
- Sites estáticos (HTML puro)
- Autenticação simples
- Sem JavaScript crítico

---

### ~~Opção 3: Hybrid (Selenium Login + Requests Scraping)~~ (DESNECESSÁRIO)

**Tecnologia**: Selenium para login, depois Requests com cookies extraídos

**Como Funciona:**
1. Selenium faz login e extrai cookies
2. Passa cookies para Requests
3. Requests faz scraping rápido

**Prós:**
- ✅ Melhor performance após login
- ✅ Gerencia autenticação complexa
- ✅ Scraping rápido depois

**Contras:**
- ❌ Complexidade adicional
- ❌ Precisa manter cookies válidos

---

### Opção 4: **API Reversa (Engenharia Reversa)**

**Tecnologia**: Inspecionar Network Tab e descobrir endpoints JSON

**Como Funciona:**
1. Abre DevTools (F12)
2. Faz ações no site
3. Procura requisições XHR/Fetch
4. Descobre endpoints JSON diretos
5. Usa Requests diretamente

**Prós:**
- ✅✅✅ MUITO mais rápido se funcionar
- ✅ Dados estruturados (JSON)
- ✅ Não quebra com mudanças de HTML

**Contras:**
- ❌ Nem sempre existe API escondida
- ❌ Pode ter autenticação complexa
- ❌ Pode ter rate limiting

**Quando Usar:**
- Sites modernos (React, Vue, Angular)
- SPAs (Single Page Applications)
- **VALE A PENA INVESTIGAR PRIMEIRO**

---

## 🎯 RECOMENDAÇÃO FINAL

### **Abordagem Híbrida em 3 Fases:**

#### **FASE 1: Investigação (1-2 dias)** 🔍
1. **Análise de Rede**:
   - Abrir DevTools → Network
   - Fazer login
   - Navegar pelas páginas
   - Procurar requisições JSON/AJAX
   - Verificar estrutura de autenticação (cookies, tokens)

2. **Mapeamento HTML**:
   - Inspecionar estrutura das tabelas
   - Identificar IDs, classes, selectores CSS
   - Mapear campos de cada página

3. **Decisão**:
   - Se encontrar JSON → usar Requests + API Reversa
   - Se não encontrar → usar Selenium

**Entregável**: Documento técnico com endpoints/selectores mapeados

---

#### **FASE 2: Proof of Concept (2-3 dias)** 🧪

**Script POC - Testar Viabilidade com Playwright:**

```python
# delnext_poc_playwright.py
from playwright.sync_api import sync_playwright
import json
from datetime import datetime

class DelnextPlaywrightPOC:
    def __init__(self):
        self.base_url = "https://www.delnext.com/admind/"
        self.username = "VianaCastelo"
        self.password = "HelloViana23432"
        self.api_endpoints_found = []  # Para detectar APIs escondidas
        
    def log_response(self, response):
        """Monitora requisições de rede - detecta APIs JSON escondidas"""
        url = response.url
        
        # Detectar endpoints JSON/API
        if any(keyword in url.lower() for keyword in ['api', 'json', 'ajax', 'data']):
            print(f"🔴 API DETECTADA: {url}")
            print(f"   Status: {response.status}")
            print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
            self.api_endpoints_found.append(url)
    
    def run_poc(self):
        with sync_playwright() as p:
            # Lançar navegador (pode usar headless=True em produção)
            browser = p.chromium.launch(headless=False)  # headless=True para servidor
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            # 🕶️ Monitorar todas as requisições de rede
            page.on("response", self.log_response)
            
            try:
                print("🔐 FASE 1: Login...")
                page.goto(f"{self.base_url}index.php", wait_until="networkidle")
                
                # Preencher login (Playwright auto-aguarda elementos)
                page.fill("input[name='username']", self.username)
                page.fill("input[name='password']", self.password)
                page.click("button[type='submit']")
                
                # Aguardar redirecionamento
                page.wait_for_url("**/dashboard**", timeout=10000)
                print("✅ Login realizado!\n")
                
                # FASE 2: Scraping Inbound
                print("📥 FASE 2: Capturando Inbound Partners...")
                page.goto(f"{self.base_url}inbound_partners.php", wait_until="networkidle")
                
                # Aguardar tabela aparecer
                page.wait_for_selector("table", timeout=10000)
                
                # Extrair dados da tabela
                rows = page.query_selector_all("table tr")
                print(f"   📋 Linhas encontradas: {len(rows)}")
                
                inbound_data = []
                for i, row in enumerate(rows[1:], 1):  # Skip header
                    cells = row.query_selector_all("td")
                    if len(cells) >= 8:
                        row_data = {
                            "parcel_id": cells[0].text_content().strip(),
                            "admin_name": cells[1].text_content().strip(),
                            "warehouse": cells[2].text_content().strip(),
                            "destination_zone": cells[3].text_content().strip(),
                            "country": cells[4].text_content().strip(),
                            "city": cells[5].text_content().strip(),
                            "date": cells[6].text_content().strip(),
                            "comment": cells[7].text_content().strip(),
                        }
                        
                        if row_data['parcel_id']:  # Ignorar linhas vazias
                            inbound_data.append(row_data)
                            print(f"   ✅ Linha {i}: {row_data['parcel_id']} - {row_data['city']}")
                
                print(f"\n✅ Inbound: {len(inbound_data)} registros capturados\n")
                
                # FASE 3: Scraping Outbound (PRIORITÁRIO ⭐⭐⭐⭐⭐)
                print("📤 FASE 3: Capturando Outbound (Proteção dia seguinte)...")
                page.goto(f"{self.base_url}outbound_consult.php", wait_until="networkidle")
                page.wait_for_selector("table", timeout=10000)
                
                outbound_rows = page.query_selector_all("table tr")
                print(f"   📋 Entregas agendadas: {len(outbound_rows) - 1}\n")
                
                # FASE 4: Application Stats
                print("📊 FASE 4: Capturando Application Stats...")
                page.goto(f"{self.base_url}application_stats.php", wait_until="networkidle")
                
                # Verificar motoristas
                drivers = page.query_selector_all(".driver-item, .motorista, [data-driver]")
                print(f"   🚚 Motoristas encontrados: {len(drivers)}\n")
                
                # RELATÓRIO FINAL
                print("=" * 60)
                print("🎯 RELATÓRIO DO POC")
                print("=" * 60)
                print(f"✅ Login: SUCESSO")
                print(f"✅ Inbound: {len(inbound_data)} registros")
                print(f"✅ Outbound: {len(outbound_rows) - 1} entregas agendadas")
                print(f"✅ Stats: Acessado com sucesso")
                
                if self.api_endpoints_found:
                    print(f"\n🔴 APIs ESCONDIDAS DETECTADAS: {len(self.api_endpoints_found)}")
                    for endpoint in self.api_endpoints_found:
                        print(f"   - {endpoint}")
                    print("   → RECOMENDAÇÃO: Usar Requests direto (muito mais rápido!)")
                else:
                    print(f"\n⚠️ Nenhuma API JSON detectada - usar Playwright para scraping")
                
                print("\n" + "=" * 60)
                
                # Screenshot para validação visual
                page.screenshot(path="delnext_poc_screenshot.png")
                print("📸 Screenshot salvo: delnext_poc_screenshot.png")
                
                # Salvar dados de exemplo
                with open("delnext_inbound_sample.json", "w", encoding="utf-8") as f:
                    json.dump(inbound_data, f, indent=2, ensure_ascii=False)
                print("💾 Dados salvos: delnext_inbound_sample.json")
                
            except Exception as e:
                print(f"\n❌ ERRO: {e}")
                page.screenshot(path="delnext_error_screenshot.png")
                raise
            
            finally:
                browser.close()


if __name__ == "__main__":
    print("🚀 Iniciando POC Delnext com Playwright...\n")
    poc = DelnextPlaywrightPOC()
    poc.run_poc()
    print("\n✅ POC concluído!")
```

**Objetivos do POC:**
- ✅ Validar que conseguimos fazer login
- ✅ **Detectar automaticamente se há APIs JSON escondidas** (via network interception)
- ✅ Extrair tabelas Inbound, Outbound, Stats
- ✅ Medir tempo de execução
- ✅ Gerar screenshot + JSON de exemplo

**Entregável**: Script funcional + relatório de viabilidade

---

#### **FASE 3: Implementação Completa (1-2 semanas)** 🚀

**Estrutura do Sistema (Padrão Adapter):**

```
orders_manager/
├── adapters/                    # 🆕 Nova pasta para adapters de parceiros
│   ├── __init__.py
│   └── delnext/
│       ├── __init__.py
│       ├── scraper.py          # Playwright scraper
│       ├── parser.py           # Converte HTML → dict
│       ├── mapper.py           # Mapeia Delnext → Order genérico
│       └── status_mapping.py   # "Confirmed" → "DELIVERED", etc.
├── management/
│   └── commands/
│       ├── sync_partner.py     # Já existe (genérico)
│       └── sync_delnext.py     # 🆕 Wrapper específico (opcional)
├── models.py                    # Order genérico (JÁ EXISTE)
└── ...

core/
├── services/
│   └── delnext_sync_service.py # 🆕 Orquestrador (usa adapter)
└── ...
```

**Princípio:**
- **Nenhum modelo novo** (usa `Order`, `Partner`, `SyncLog` existentes)
- **Adapter** traduz dados Delnext → formato genérico
- **Serviço** orquestra scraping + salvamento
- **Comando** permite executar via cron/celery

**1. Mapeamento de Status** (`orders_manager/adapters/delnext/status_mapping.py`):

```python
"""Mapeia status Delnext → Status genérico do sistema"""

STATUS_MAPPING = {
    # Delnext → orders_manager.Order.STATUS_CHOICES
    "confirmed": "DELIVERED",
    "in_distribution": "IN_TRANSIT",
    "pending": "PENDING",
    "incident": "INCIDENT",
    "cancelled": "CANCELLED",
    "returned": "RETURNED",
}

def normalize_status(delnext_status: str) -> str:
    """Converte status Delnext para status padrão"""
    return STATUS_MAPPING.get(delnext_status.lower(), "PENDING")
```

---

**2. Adapter/Mapper** (`orders_manager/adapters/delnext/mapper.py`):

```python
"""Converte dados extraídos do Delnext → modelo Order genérico"""
from orders_manager.models import Order
from core.models import Partner
from .status_mapping import normalize_status
import logging

logger = logging.getLogger(__name__)


class DelnextOrderMapper:
    """Mapeia dados Delnext para modelo Order genérico"""
    
    def __init__(self):
        self.partner = Partner.objects.get(name="Delnext")
    
    def map_inbound_row(self, row_data: dict) -> dict:
        """Converte linha de Inbound → campos do Order"""
        return {
            'tracking_number': row_data['parcel_id'],
            'partner': self.partner,
            'customer_name': row_data.get('admin_name', ''),
            'delivery_address': row_data.get('city', ''),
            'postal_code': row_data.get('destination_zone', ''),
            'country': row_data.get('country', 'Portugal'),
            'status': 'PENDING',  # Inbound sempre começa como PENDING
            'comments': row_data.get('comment', ''),
        }
    
    def map_outbound_row(self, row_data: dict) -> dict:
        """Converte linha de Outbound → campos do Order"""
        return {
            'tracking_number': row_data['parcel_id'],
            'partner': self.partner,
            'delivery_address': row_data.get('destination', ''),
            'postal_code': row_data.get('postal_code', ''),
            'weight': row_data.get('weight'),
            'status': normalize_status(row_data.get('status', 'pending')),
            'is_cod': row_data.get('cod_type', '').upper() == 'COD',
        }
    
    def map_stats_row(self, row_data: dict) -> dict:
        """Converte linha de Stats → campos do Order"""
        return {
            'tracking_number': row_data['parcel_id'],
            'partner': self.partner,
            'status': normalize_status(row_data.get('status', 'pending')),
            'weight': row_data.get('weight'),
            'delivered_at': row_data.get('delivered_at'),  # Se disponível
        }
    
    def save_order(self, order_data: dict, operation_type: str) -> tuple:
        """Salva/atualiza Order no banco de dados"""
        try:
            order, created = Order.objects.update_or_create(
                tracking_number=order_data['tracking_number'],
                partner=order_data['partner'],
                defaults=order_data
            )
            
            action = "created" if created else "updated"
            logger.info(f"📦 Order {order.tracking_number} {action} ({operation_type})")
            
            return order, created
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar order {order_data.get('tracking_number')}: {e}")
            raise
```

---

**3. ~~Modelos Específicos~~ (NÃO CRIAR - Usar Order Genérico)**

```python
# ❌ NÃO FAZER ISSO:
# class DelnextOrder(models.Model):
    """Pedidos capturados do Delnext"""
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name="delnext_orders")
    
    # Identificação
    parcel_id = models.CharField("Parcel ID", max_length=100, unique=True, db_index=True)
    tracking_number = models.CharField("Tracking", max_length=100, blank=True)
    
    # Tipo de operação
    operation_type = models.CharField(max_length=20, choices=[
        ("INBOUND", "Inbound"),
        ("OUTBOUND", "Outbound"),
    ])
    
    # Destinatário
    destination_zone = models.CharField("Zona", max_length=100, blank=True)
    city = models.CharField("Cidade", max_length=100, blank=True)
    country = models.CharField("País", max_length=100, default="Portugal")
    postal_code = models.CharField("Código Postal", max_length=20, blank=True)
    
    # Status
    status = models.CharField(max_length=50, blank=True)
    confirmed = models.BooleanField("Confirmado", default=False)
    is_cod = models.BooleanField("COD (Cash on Delivery)", default=False)
    
    # Detalhes
    weight = models.DecimalField("Peso (kg)", max_digits=6, decimal_places=2, null=True, blank=True)
    admin_name = models.CharField("Admin", max_length=100, blank=True)
    warehouse = models.CharField("Armazém", max_length=100, blank=True)
    
    # Motorista
    assigned_driver = models.ForeignKey("DelnextDriver", on_delete=models.SET_NULL, null=True, blank=True)
    
    # Observações
    comment = models.TextField("Comentário", blank=True)
    
    # Datas
    scheduled_date = models.DateField("Data Agendada", null=True, blank=True)
    delivered_at = models.DateTimeField("Entregue em", null=True, blank=True)
    
    # Metadados
    scraped_at = models.DateTimeField("Capturado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)
    
    class Meta:
        verbose_name = "Pedido Delnext"
        verbose_name_plural = "Pedidos Delnext"
        ordering = ["-scraped_at"]
        indexes = [
            models.Index(fields=["partner", "operation_type"]),
            models.Index(fields=["status", "scheduled_date"]),
        ]
    
    def __str__(self):
        return f"{self.parcel_id} - {self.operation_type}"


class DelnextDriver(models.Model):
    """Motoristas do sistema Delnext"""
    username = models.CharField("Username", max_length=50, unique=True)
    zone = models.CharField("Zona", max_length=100, blank=True)
    is_active = models.BooleanField("Ativo", default=True)
    
    # Vincular com motorista interno (se existir)
    internal_driver = models.ForeignKey(
        "drivers_app.DriverProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delnext_accounts"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Motorista Delnext"
        verbose_name_plural = "Motoristas Delnext"
    
    def __str__(self):
        return self.username


class DelnextIncident(models.Model):
    """Incidências reportadas no Delnext"""
    order = models.ForeignKey(DelnextOrder, on_delete=models.CASCADE, related_name="incidents")
    
    incident_type = models.CharField("Tipo", max_length=100)
    description = models.TextField("Descrição", blank=True)
    resolved = models.BooleanField("Resolvida", default=False)
    resolved_at = models.DateTimeField("Resolvida em", null=True, blank=True)
    
    created_at = models.DateTimeField("Reportada em", auto_now_add=True)
    
    class Meta:
        verbose_name = "Incidência Delnext"
        verbose_name_plural = "Incidências Delnext"
        ordering = ["-created_at"]


class DelnextSyncLog(models.Model):
    """Log de sincronizações com Delnext"""
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=[
        ("SUCCESS", "Sucesso"),
        ("ERROR", "Erro"),
        ("PARTIAL", "Parcial"),
    ], default="SUCCESS")
    
    page_scraped = models.CharField("Página", max_length=50)
    records_found = models.IntegerField("Registros Encontrados", default=0)
    records_created = models.IntegerField("Criados", default=0)
    records_updated = models.IntegerField("Atualizados", default=0)
    
    error_message = models.TextField("Erro", blank=True)
    
    class Meta:
        verbose_name = "Log de Sync Delnext"
        verbose_name_plural = "Logs de Sync Delnext"
        ordering = ["-started_at"]
```

**2. Scraper com Playwright** (`orders_manager/adapters/delnext/scraper.py`):

```python
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, Page
from django.utils import timezone
from typing import List, Dict

logger = logging.getLogger(__name__)


class DelnextPlaywrightScraper:
    """Scraper Delnext usando Playwright"""
    
    def __init__(self, username="VianaCastelo", password="HelloViana23432"):
        self.username = username
        self.password = password
        self.base_url = "https://www.delnext.com/admind/"
        self.api_endpoints = []  # Para detectar APIs escondidas
        
    def _monitor_network(self, response):
        """Detecta APIs JSON durante navegação"""
        if any(kw in response.url.lower() for kw in ['api', 'json', 'ajax']):
            logger.info(f"🔴 API detectada: {response.url}")
            self.api_endpoints.append(response.url)
    
    def _login(self, page: Page) -> bool:
        """Realiza login no Delnext"""
        try:
            logger.info(f"🔐 Login como {self.username}...")
            page.goto(f"{self.base_url}index.php", wait_until="networkidle")
            
            # Playwright auto-aguarda elementos
            page.fill("input[name='username']", self.username)
            page.fill("input[name='password']", self.password)
            page.click("button[type='submit']")
            
            # Aguardar redirecionamento
            page.wait_for_url("**/dashboard**", timeout=10000)
            
            logger.info("✅ Login realizado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no login: {e}")
            page.screenshot(path="delnext_login_error.png")
            return False
    
    def scrape_inbound(self, page: Page) -> List[Dict]:
        """Extrai dados de Inbound Partners"""
        logger.info("📥 Capturando Inbound Partners...")
        
        page.goto(f"{self.base_url}inbound_partners.php", wait_until="networkidle")
        page.wait_for_selector("table", timeout=10000)
        
        rows = page.query_selector_all("table tr")
        data = []
        
        for row in rows[1:]:  # Skip header
            cells = row.query_selector_all("td")
            if len(cells) >= 8:
                parcel_id = cells[0].text_content().strip()
                
                if not parcel_id:
                    continue
                
                data.append({
                    "parcel_id": parcel_id,
                    "admin_name": cells[1].text_content().strip(),
                    "warehouse": cells[2].text_content().strip(),
                    "destination_zone": cells[3].text_content().strip(),
                    "country": cells[4].text_content().strip(),
                    "city": cells[5].text_content().strip(),
                    "date": cells[6].text_content().strip(),
                    "comment": cells[7].text_content().strip(),
                })
        
        logger.info(f"✅ Inbound: {len(data)} registros")
        return data
    
    def scrape_outbound(self, page: Page) -> List[Dict]:
        """Extrai previsão de pacotes (Outbound) - PRIORITÁRIO"""
        logger.info("📤 Capturando Outbound (planejamento)...")
        
        page.goto(f"{self.base_url}outbound_consult.php", wait_until="networkidle")
        page.wait_for_selector("table", timeout=10000)
        
        rows = page.query_selector_all("table tr")
        data = []
        
        for row in rows[1:]:
            cells = row.query_selector_all("td")
            if cells:
                # Ajustar conforme estrutura real da tabela
                data.append({
                    "parcel_id": cells[0].text_content().strip(),
                    "destination": cells[1].text_content().strip() if len(cells) > 1 else "",
                    "postal_code": cells[2].text_content().strip() if len(cells) > 2 else "",
                    "status": cells[3].text_content().strip() if len(cells) > 3 else "",
                })
        
        logger.info(f"✅ Outbound: {len(data)} entregas agendadas")
        return data
    
    def scrape_all(self) -> Dict:
        """Executa scraping completo"""
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,  # Sem interface gráfica
                args=['--no-sandbox', '--disable-dev-shm-usage']  # Docker-friendly
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            # Monitorar rede
            page.on("response", self._monitor_network)
            
            try:
                # Login
                if not self._login(page):
                    raise Exception("Falha no login")
                
                # Scraping
                results = {
                    "inbound": self.scrape_inbound(page),
                    "outbound": self.scrape_outbound(page),
                    "api_endpoints": self.api_endpoints,
                }
                
                logger.info("🎉 Scraping completo!")
                return results
                
            finally:
                browser.close()
```

---

**3. Serviço de Sincronização** (`core/services/delnext_sync_service.py`):

```python
import logging
from django.db import transaction
from django.utils import timezone

from orders_manager.adapters.delnext.scraper import DelnextPlaywrightScraper
from orders_manager.adapters.delnext.mapper import DelnextOrderMapper
from core.models import SyncLog, Partner

logger = logging.getLogger(__name__)


class DelnextSyncService:
    """Orquestra scraping + mapeamento + salvamento"""
    
    def __init__(self):
        self.scraper = DelnextPlaywrightScraper()
        self.mapper = DelnextOrderMapper()
        self.partner = Partner.objects.get(name="Delnext")
    
    def sync_inbound(self, scraped_data: list) -> dict:
        """Processa e salva dados de Inbound"""
        stats = {"created": 0, "updated": 0, "errors": 0}
        
        with transaction.atomic():
            for row in scraped_data:
                try:
                    order_data = self.mapper.map_inbound_row(row)
                    order, created = self.mapper.save_order(order_data, "INBOUND")
                    
                    if created:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                        
                except Exception as e:
                    logger.error(f"❌ Erro ao processar {row.get('parcel_id')}: {e}")
                    stats["errors"] += 1
        
        return stats
    
    def sync_outbound(self, scraped_data: list) -> dict:
        """Processa e salva dados de Outbound"""
        stats = {"created": 0, "updated": 0, "errors": 0}
        
        with transaction.atomic():
            for row in scraped_data:
                try:
                    order_data = self.mapper.map_outbound_row(row)
                    order, created = self.mapper.save_order(order_data, "OUTBOUND")
                    
                    if created:
                        stats["created"] += 1
                    else:
                        stats["updated"] += 1
                        
                except Exception as e:
                    logger.error(f"❌ Erro: {e}")
                    stats["errors"] += 1
        
        return stats
    
    def sync_all(self) -> dict:
        """Executa sincronização completa"""
        sync_log = SyncLog.objects.create(
            partner_integration=self.partner.integrations.first(),
            status="STARTED",
        )
        
        try:
            # Scraping
            logger.info("🚀 Iniciando scraping Delnext...")
            scraped_data = self.scraper.scrape_all()
            
            # Processar dados
            inbound_stats = self.sync_inbound(scraped_data["inbound"])
            outbound_stats = self.sync_outbound(scraped_data["outbound"])
            
            # Atualizar log
            total_created = inbound_stats["created"] + outbound_stats["created"]
            total_updated = inbound_stats["updated"] + outbound_stats["updated"]
            
            sync_log.status = "SUCCESS"
            sync_log.records_created = total_created
            sync_log.records_updated = total_updated
            sync_log.completed_at = timezone.now()
            sync_log.save()
            
            logger.info(f"✅ Sync completo: {total_created} criados, {total_updated} atualizados")
            
            return {
                "status": "SUCCESS",
                "inbound": inbound_stats,
                "outbound": outbound_stats,
            }
            
        except Exception as e:
            sync_log.status = "ERROR"
            sync_log.error_details = str(e)
            sync_log.completed_at = timezone.now()
            sync_log.save()
            
            logger.error(f"❌ Erro no sync: {e}")
            raise
```

---

**4. Comando Django** (`orders_manager/management/commands/sync_delnext.py`):

```python
from django.core.management.base import BaseCommand
from core.services.delnext_sync_service import DelnextSyncService


class Command(BaseCommand):
    help = "Sincroniza dados do Delnext via web scraping (Playwright)"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--inbound-only',
            action='store_true',
            help='Sincronizar apenas Inbound',
        )
        parser.add_argument(
            '--outbound-only',
            action='store_true',
            help='Sincronizar apenas Outbound',
        )
    
    def handle(self, *args, **options):
        self.stdout.write("🚀 Iniciando sincronização Delnext...\n")
        
        service = DelnextSyncService()
        
        try:
            results = service.sync_all()
            
            self.stdout.write(self.style.SUCCESS(
                f"✅ Sincronização concluída!\n"
                f"   📥 Inbound: {results['inbound']['created']} criados, {results['inbound']['updated']} atualizados\n"
                f"   📤 Outbound: {results['outbound']['created']} criados, {results['outbound']['updated']} atualizados\n"
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro: {e}"))
            raise
```

### 🐳 Configuração Docker para Playwright

**1. Atualizar `requirements.txt`:**

```txt
# ... dependências existentes ...

# Web Scraping
playwright==1.40.0
```

**2. Atualizar `Dockerfile`:**

```dockerfile
FROM python:3.11-slim

# Instalar dependências do sistema para Playwright
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Instalar aplicação Django
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores do Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

CMD ["gunicorn", "my_project.wsgi:application", "--bind", "0.0.0.0:8000"]
```

**3. Testar instalação:**

```bash
# Rebuild container
docker-compose build leguas_web

# Testar Playwright
docker exec -it leguas_web python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright OK')"

# Executar POC
docker exec -it leguas_web python delnext_poc_playwright.py

---

## 📅 CRONOGRAMA DETALHADO (REVISADO)

### ⚡ Fase 1: Preparação + POC (Dia 1-2)
- **Dia 1 Manhã** (2h): Setup Docker + Playwright
  - Atualizar `requirements.txt` e `Dockerfile`
  - Rebuild container
  - Instalar navegadores Playwright
  - Validar instalação

- **Dia 1 Tarde** (4h): POC com Network Interception
  - Criar `delnext_poc_playwright.py`
  - Executar scraping de teste
  - **Detectar APIs JSON escondidas** (critical!)
  - Analisar resultados

- **Dia 2** (6h): Validação e Decisão
  - Testar scraping de Inbound, Outbound, Stats
  - Medir performance (tempo de execução)
  - Gerar relatório técnico
  - **Decisão**: Continuar com Playwright ou usar API reversa?

**Entregável**: POC funcional + decisão técnica documentada

---

### 🏗️ Fase 2: Implementação Core (Dia 3-7)
- **Dia 3** (8h): Estrutura Adapter
  - Criar `orders_manager/adapters/delnext/`
  - Implementar `status_mapping.py`
  - Implementar `mapper.py` (Delnext → Order genérico)
  - ❌ **NÃO criar** modelos específicos

- **Dia 4-5** (16h): Scraper + Service
  - Implementar `scraper.py` (Playwright)
  - Implementar `delnext_sync_service.py`
  - Integração com `Order` e `SyncLog` existentes

- **Dia 6** (8h): Comando Django
  - Criar `sync_delnext.py`
  - Testes manuais
  - Debug e ajustes

- **Dia 7** (8h): Configuração Celery
  - Adicionar tasks assíncronas
  - Configurar Celery Beat (agendamento)
  - Testes de execução programada

**Entregável**: Sistema funcional com sync automático

---

### 📊 Fase 3: Integração + Monitoramento (Dia 8-10)
- **Dia 8** (6h): Dashboard Integration
  - Filtros por parceiro "Delnext" no orders_manager
  - Visualização de SyncLog no admin
  - ❌ **NÃO criar** templates específicos (usar genéricos)

- **Dia 9** (6h): Testes + Validação
  - Testes end-to-end
  - Validação de dados (comparar com Delnext site)
  - Performance testing

- **Dia 10** (4h): Alertas + Monitoramento
  - Configurar alertas de sync falho
  - Screenshots automáticos de erro
  - Documentação final

**Entregável**: Sistema em produção + documentação

---

### 🎯 Timeline Total: **10 dias úteis** (2 semanas)

**Comparado ao plano original (3 semanas):**
- ✅ Mais rápido (Playwright vs Selenium)
- ✅ Menos complexo (sem modelos específicos)
- ✅ Mais robusto (Adapter Pattern + Order genérico)

---

## 💰 ESTIMATIVA DE RECURSOS

### Infraestrutura
- **Container Docker**: Usar container existente `leguas_web`
- **RAM Adicional**: +500MB (Playwright headless Chromium)
- **Storage**: ~200MB (binários Playwright)
- **CPU**: Processo leve (execução assíncrona via Celery)

### Dependências Python

```txt
# requirements.txt (adicionar)
playwright==1.40.0              # Web scraping moderno (substitui Selenium)
```

**NÃO instalar:**
- ~~selenium~~ (substituído por Playwright)
- ~~webdriver-manager~~ (desnecessário)
- ~~beautifulsoup4~~ (Playwright tem parsing nativo)
- ~~pandas~~ (opcional, apenas se precisar análise de dados)

### Frequência de Sync (Agendamento Cron/Celery)

```python
# my_project/celery.py (Celery Beat Schedule)
from celery.schedules import crontab

app.conf.beat_schedule = {
    'delnext-sync-inbound': {
        'task': 'core.tasks.sync_delnext_inbound',
        'schedule': crontab(minute='*/30'),  # A cada 30 minutos
    },
    'delnext-sync-outbound': {
        'task': 'core.tasks.sync_delnext_outbound',
        'schedule': crontab(hour=23, minute=0),  # 23:00 (planejamento do dia seguinte)
    },
    'delnext-sync-stats': {
        'task': 'core.tasks.sync_delnext_stats',
        'schedule': crontab(minute=0),  # A cada 1 hora
    },
}
```

**IMPORTANTE:**
- ⚠️ **NUNCA** executar scraping diretamente de uma view Django (timeout)
- ✅ Usar Celery workers para execução assíncrona
- ✅ Usuário vê apenas resultados no dashboard (atualização automática)

---

## ⚠️ RISCOS E MITIGAÇÕES

### Risco 1: Mudanças no HTML do Site
- **Probabilidade**: Alta
- **Impacto**: Alto (scraper quebra)
- **Mitigação**: 
  - Usar selectores CSS robustos (IDs > Classes > Tags)
  - Implementar testes automatizados
  - Alertas quando scraping falha

### Risco 2: Bloqueio por Rate Limiting
- **Probabilidade**: Média
- **Impacto**: Médio (IP bloqueado temporariamente)
- **Mitigação**:
  - Adicionar delays entre requisições (2-5 segundos)
  - User-Agent realista
  - Não abusar da frequência

### Risco 3: Mudança de Credenciais
- **Probabilidade**: Baixa
- **Impacto**: Alto (scraping para)
- **Mitigação**:
  - Armazenar credenciais em variáveis de ambiente
  - Sistema de alertas se login falhar

### Risco 4: Performance (Scraping Bloqueante)
- **Probabilidade**: Alta
- **Impacto**: Crítico se executado de views Django
- **Mitigação**:
  - ✅ **OBRIGATÓRIO**: Executar via Celery (assíncrono)
  - ✅ Usar Playwright headless (2-3x mais rápido que Selenium)
  - ✅ Cache de dados quando possível (5-10 min)
  - ✅ Paralelizar scraping de páginas diferentes (async Playwright)

### Risco 5: Manutenção do Adapter
- **Probabilidade**: Média (Delnext pode mudar HTML)
- **Impacto**: Médio (scraper quebra)
- **Mitigação**:
  - ✅ Testes automatizados (comparar schemas)
  - ✅ Alertas automáticos quando sync falha
  - ✅ Fallback: usar dados em cache até resolver
  - ✅ Screenshots de erro automáticos para debug

---

## 🎯 ALTERNATIVA: Playwright Async (Máxima Performance)

Se a performance for crítica, use Playwright **async** para scraping paralelo:

```python
import asyncio
from playwright.async_api import async_playwright

class DelnextAsyncScraper:
    async def scrape_all_parallel(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Executar scraping de 3 páginas em PARALELO
            tasks = [
                self.scrape_inbound(context),
                self.scrape_outbound(context),
                self.scrape_stats(context),
            ]
            
            results = await asyncio.gather(*tasks)
            await browser.close()
            
            return {
                "inbound": results[0],
                "outbound": results[1],
                "stats": results[2],
            }
```

**Vantagens Async:**
- ✅ 3x mais rápido (scraping paralelo)
- ✅ Melhor uso de recursos
- ✅ Ideal para múltiplas páginas

**Desvantagens:**
- ❌ Mais complexo de debugar
- ❌ Requer Django Channels ou Celery com async support

---

## 📊 PRÓXIMOS PASSOS - DECISÃO

### ✅ Opção RECOMENDADA: POC Rápido (2-3 dias) + Implementação Completa

**Fase 1 - POC (Dia 1-2):**
1. Instalar Playwright no Docker
2. Executar `delnext_poc_playwright.py`
3. Validar:
   - ✅ Login funciona
   - ✅ Consegue extrair tabelas
   - ✅ Detectar se há APIs JSON escondidas (network interception)
   - ✅ Medir tempo de execução

**Fase 2 - Implementação (Dia 3-10):**
1. Criar estrutura `orders_manager/adapters/delnext/`
2. Implementar scraper + mapper + service
3. Criar comando Django `sync_delnext`
4. Configurar Celery Beat (agendamento)
5. Testes + validação

**Fase 3 - Dashboard (Dia 11-14):**
1. Integrar com dashboard existente (sem views específicas)
2. Filtros por parceiro "Delnext" no orders_manager
3. Relatórios de sync (SyncLog)

---

## 🤔 MINHA RECOMENDAÇÃO FINAL (REVISADA)

### 🛣️ Roadmap Ajustado:

**1. HOJE: Preparar Ambiente** (⏱️ 30 min)
```bash
# Adicionar Playwright ao requirements.txt
echo "playwright==1.40.0" >> requirements.txt

# Atualizar Dockerfile (adicionar instalação Playwright)
# Rebuild container
docker-compose build leguas_web
docker-compose up -d

# Instalar navegadores
docker exec -it leguas_web playwright install chromium
```

**2. DIA 1: POC com Network Interception** (⏱️ 4-6 horas)
```bash
# Criar POC
touch delnext_poc_playwright.py

# Executar
docker exec -it leguas_web python delnext_poc_playwright.py

# Analisar resultados:
# - Se API JSON encontrada → Usar Requests (MUITO mais rápido)
# - Se não → Continuar com Playwright
```

**3. DIA 2-5: Implementação Core** (⏱️ 2-3 dias)
- Criar `orders_manager/adapters/delnext/`
- Implementar scraper + mapper (usa `Order` genérico)
- Criar serviço de sync
- Comando Django

**4. DIA 6-7: Integração + Testes** (⏱️ 1-2 dias)
- Configurar Celery Beat
- Testes manuais
- Validação de dados

**5. DIA 8+: Monitoramento** (⏱️ Contínuo)
- Alertas automáticos
- Dashboard de SyncLog

---

### 🚀 COMEÇAR AGORA:

Quer que eu:

**A) 🧪 Crie o POC completo** (script `delnext_poc_playwright.py` pronto para rodar)?  
   - Inclui network interception
   - Detecta APIs escondidas automaticamente
   - Gera JSON + screenshots de exemplo

**B) 🏗️ Implemente a estrutura completa** (adapters + scraper + mapper + comando)?  
   - Cria todas as pastas e arquivos
   - Integra com modelo `Order` genérico
   - Configura Docker + Playwright

**C) 🔍 Apenas atualize o Dockerfile** para preparar o ambiente primeiro?

**Qual opção prefere?** 🤔
