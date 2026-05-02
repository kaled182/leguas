"""
POC Delnext - Versão Totalmente Automática
Tenta contornar Cloudflare com estratégias anti-detecção
"""

from playwright.sync_api import sync_playwright, Page
from pathlib import Path
import json
from datetime import datetime, timedelta
import time
import random


def get_last_weekday() -> str:
    """Retorna a última sexta-feira ou dia útil mais recente (formato: 2026-02-27)"""
    today = datetime.now()
    
    # Se hoje é sábado (5) ou domingo (6), voltar para sexta
    if today.weekday() == 5:  # Sábado
        last_weekday = today - timedelta(days=1)  # Sexta
    elif today.weekday() == 6:  # Domingo
        last_weekday = today - timedelta(days=2)  # Sexta
    else:
        # Dia útil - usar hoje
        last_weekday = today
    
    # Formato: 2026-02-27 (YYYY-MM-DD)
    return last_weekday.strftime("%Y-%m-%d")


def human_delay():
    """Delay humanizado (random entre 1-3s)"""
    time.sleep(random.uniform(1.0, 3.0))


def scrape_outbound_safe(page: Page, target_date: str, zone_filter: str = None) -> list:
    """Extrai previsão de pacotes (Outbound) com tratamento de erros
    
    Args:
        target_date: Data para consultar (formato: "2026-02-27" YYYY-MM-DD)
        zone_filter: Filtro por zona (ex: "VianaCastelo")
    """
    try:
        print("\n📤 FASE 2: Capturando Outbound (Previsão de Entregas)")
        print(f"   📅 Data alvo: {target_date}")
        
        # Construir URL com date_range e zone diretamente (descoberta do usuário!)
        import json
        import urllib.parse
        
        date_range = {
            "start": target_date,
            "end": target_date
        }
        date_range_encoded = urllib.parse.quote(json.dumps(date_range))
        
        # Usar zone_filter na URL ou "all" se não especificado
        zone_param = zone_filter if zone_filter else "all"
        url = f"https://www.delnext.com/admind/outbound_consult.php?date_range={date_range_encoded}&zone={zone_param}"
        
        print(f"   🔗 URL: {url}")
        if zone_filter:
            print(f"   🎯 Filtro de zona aplicado na URL: {zone_filter}")
        
        # Navegar diretamente com parâmetros
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        human_delay()
        
        screenshots_dir = Path("debug_files/delnext_poc_manual")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Aguardar página carregar completamente
        print("   ⏳ Aguardando página carregar com data...")
        time.sleep(3)
        
        page.screenshot(path=str(screenshots_dir / "02_outbound_page.png"))
        print("   📸 Screenshot salvo")
        
        # Aguardar tabela
        print("   ⏳ Aguardando tabela...")
        try:
            page.wait_for_selector("table", timeout=20000)
            print("   ✅ Tabela encontrada")
        except:
            print("   ⚠️ Tabela não encontrada (timeout)")
            return []
        
        rows = page.query_selector_all("table tr")
        print(f"   📋 Total de linhas: {len(rows)}")
        
        if len(rows) <= 1:
            print("   ⚠️ Tabela vazia ou só com header")
            return []
        
        data = []
        
        # Textos de UI que devem ser ignorados
        ui_texts = [
            "customer:", "order id:", "status", "search:", "search by", "parcels processing:",
            "showing", "Copy", "CSV", "Excel", "PDF", "Print", "All Orders", "Pendente",
            "A processar", "Entregue", "Comentarios", "Cancelada", "Enviada", "Devolvida",
            "order search:", "all zones", "clear search"
        ]
        
        for i, row in enumerate(rows):
            if i == 0:  # Skip header
                header_cells = row.query_selector_all("th")
                if header_cells:
                    headers = [cell.text_content().strip() for cell in header_cells]
                    print(f"   📌 Colunas: {', '.join(headers[:6])}...")
                continue
            
            cells = row.query_selector_all("td")
            
            if cells and len(cells) >= 8:
                cell_data = [cell.text_content().strip() for cell in cells]
                product_id = cell_data[0]
                
                # Filtrar linhas de UI (que não são dados reais)
                is_ui_element = False
                for ui_text in ui_texts:
                    if any(ui_text in cell.text_content().lower() for cell in cells):
                        is_ui_element = True
                        break
                
                # Verificar se é uma linha de dados válida
                # Product ID geralmente é numérico
                if product_id and product_id != "" and not is_ui_element:
                    # Verificar se product_id é numérico (ou tem padrão esperado)
                    if product_id.isdigit() or len(product_id) >= 6:
                        row_dict = {
                            "product_id": product_id,
                            "destination_zone": cell_data[1] if len(cell_data) > 1 else "",
                            "customer_name": cell_data[2] if len(cell_data) > 2 else "",
                            "address": cell_data[3] if len(cell_data) > 3 else "",
                            "postal_code": cell_data[4] if len(cell_data) > 4 else "",
                            "city": cell_data[5] if len(cell_data) > 5 else "",
                            "date": cell_data[6] if len(cell_data) > 6 else "",
                            "status": cell_data[7] if len(cell_data) > 7 else "",
                            "admin": cell_data[8] if len(cell_data) > 8 else "",
                            "inbound_date": cell_data[9] if len(cell_data) > 9 else "",
                            "inbound_by": cell_data[10] if len(cell_data) > 10 else "",
                        }
                        data.append(row_dict)
                        
                        destination = f"{row_dict['city']} ({row_dict['destination_zone']})"
                        print(f"   ✅ {i:3d}. {product_id} → {destination}")
        
        print(f"\n   🎯 Total extraído: {len(data)} entregas")
        
        # Filtro já aplicado na URL - filtragem adicional não necessária
        # Mas mantemos por segurança caso haja dados não filtrados
        if zone_filter:
            original_count = len(data)
            # Verificar se todos já estão filtrados
            filtered_data = [item for item in data if zone_filter.lower() in item['destination_zone'].lower()]
            
            if filtered_data != data and len(filtered_data) < original_count:
                # Há dados não filtrados - aplicar filtro
                data = filtered_data
                print(f"   🔍 Filtro adicional aplicado: '{zone_filter}'")
                print(f"   ✅ Resultados: {len(data)} de {original_count} ({len(data)/original_count*100:.1f}%)")
            else:
                print(f"   ✅ Zona '{zone_filter}': {len(data)} entregas (já filtrado pela URL)")
        
        return data
        
    except Exception as e:
        print(f"   ❌ Erro ao capturar Outbound: {e}")
        return []


def try_auto_login(page: Page) -> bool:
    """Tenta fazer login automático com anti-detecção"""
    try:
        print("\n🔐 FASE 1: Tentando Login Automático")
        print("   URL: https://www.delnext.com/admind/index.php")
        
        # Navegar com timeout longo (Cloudflare pode demorar)
        print("   ⏳ Navegando para página de login...")
        page.goto("https://www.delnext.com/admind/index.php", 
                 wait_until="domcontentloaded",
                 timeout=90000)
        
        screenshots_dir = Path("debug_files/delnext_poc_manual")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Screenshot inicial
        page.screenshot(path=str(screenshots_dir / "00_login_page.png"))
        print("   📸 Screenshot inicial salvo")
        
        # Aguardar página estabilizar (Cloudflare pode estar processando)
        print("   ⏳ Aguardando página estabilizar (Cloudflare)...")
        time.sleep(8)  # Aguardar Cloudflare processar
        
        # Screenshot após espera
        page.screenshot(path=str(screenshots_dir / "00b_after_wait.png"))
        
        # Verificar se ainda está no Cloudflare
        page_content = page.content().lower()
        if "cloudflare" in page_content or "checking your browser" in page_content:
            print("   ⚠️ Cloudflare ainda ativo - aguardando mais 10s...")
            time.sleep(10)
            page.screenshot(path=str(screenshots_dir / "00c_after_cloudflare.png"))
        
        # Procurar campos de login
        print("   🔍 Procurando campos de login...")
        
        username_selectors = [
            "input[name='username']",
            "input[id='username']",
            "input[type='text']",
            "#user",
            ".username",
        ]
        
        password_selectors = [
            "input[name='password']",
            "input[id='password']",
            "input[type='password']",
            "#pass",
            ".password",
        ]
        
        # Encontrar username
        username_field = None
        for selector in username_selectors:
            try:
                username_field = page.query_selector(selector)
                if username_field and username_field.is_visible():
                    print(f"   ✅ Campo username encontrado: {selector}")
                    break
            except:
                continue
        
        if not username_field:
            print("   ❌ Campo username não encontrado - pode estar bloqueado pelo Cloudflare")
            return False
        
        # Encontrar password
        password_field = None
        for selector in password_selectors:
            try:
                password_field = page.query_selector(selector)
                if password_field and password_field.is_visible():
                    print(f"   ✅ Campo password encontrado: {selector}")
                    break
            except:
                continue
        
        if not password_field:
            print("   ❌ Campo password não encontrado")
            return False
        
        # Preencher com delays humanizados
        print("   ⌨️ Preenchendo credenciais...")
        
        # Clicar no campo e digitar devagar
        username_field.click()
        time.sleep(0.5)
        for char in "VianaCastelo":
            username_field.type(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        time.sleep(0.5)
        
        password_field.click()
        time.sleep(0.5)
        for char in "HelloViana23432":
            password_field.type(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        print("   ✅ Credenciais preenchidas")
        page.screenshot(path=str(screenshots_dir / "00d_filled.png"))
        
        # Procurar botão de submit
        print("   🔍 Procurando botão de login...")
        
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Login')",
            "button:has-text('Entrar')",
            ".btn-login",
        ]
        
        submit_button = None
        for selector in submit_selectors:
            try:
                submit_button = page.query_selector(selector)
                if submit_button and submit_button.is_visible():
                    print(f"   ✅ Botão encontrado: {selector}")
                    break
            except:
                continue
        
        # Submit
        print("   🚀 Enviando login...")
        if submit_button:
            submit_button.click()
        else:
            print("   ⚠️ Botão não encontrado, tentando Enter...")
            password_field.press("Enter")
        
        # Aguardar redirecionamento
        print("   ⏳ Aguardando redirecionamento...")
        time.sleep(5)
        
        page.screenshot(path=str(screenshots_dir / "01_after_login.png"))
        
        # Verificar se login funcionou
        current_url = page.url
        print(f"   📍 URL atual: {current_url}")
        
        if "index.php" not in current_url or "admind" in current_url:
            print("   ✅ Login parece ter sido bem-sucedido!")
            return True
        else:
            print("   ⚠️ Login pode não ter funcionado (ainda na página de login)")
            
            # Verificar mensagem de erro
            error_possible = page.query_selector(".error, .alert, #error")
            if error_possible:
                print(f"   ❌ Erro detectado: {error_possible.text_content()}")
            
            return False
        
    except Exception as e:
        print(f"   ❌ Erro no login: {e}")
        return False


def run_full_auto_poc():
    """POC totalmente automático"""
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║  DELNEXT POC - TOTALMENTE AUTOMÁTICO                    ║
║  (Tenta contornar Cloudflare)                           ║
╚═══════════════════════════════════════════════════════════╝

Iniciando em 3 segundos...
    """)
    
    time.sleep(3)
    
    start_time = datetime.now()
    
    with sync_playwright() as p:
        # Configurações anti-detecção
        print("🚀 Iniciando navegador com configurações anti-detecção...")
        
        browser = p.chromium.launch(
            headless=False,  # Visível ajuda com Cloudflare
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
            ]
        )
        
        # Context com configurações naturais
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="pt-PT",
            timezone_id="Europe/Lisbon",
        )
        
        # Remover webdriver flag
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.new_page()
        
        try:
            # Tentar login automático
            login_success = try_auto_login(page)
            
            if not login_success:
                print("\n" + "=" * 60)
                print("⚠️ LOGIN AUTOMÁTICO FALHOU")
                print("=" * 60)
                print("\n💡 O Cloudflare pode estar bloqueando.")
                print("   Você pode:")
                print("   1. Fazer login manualmente no navegador que abriu")
                print("   2. Depois voltar aqui e apertar Enter")
                print("\n👉 Aperte Enter quando estiver logado...")
                input()
                
                page.screenshot(path=str(Path("debug_files/delnext_poc_manual") / "01_manual_login.png"))
            
            # Calcular última sexta-feira
            target_date = get_last_weekday()
            print(f"\n📅 Data calculada: {target_date}")
            
            today = datetime.now()
            if today.weekday() >= 5:  # Sábado ou Domingo
                print(f"   ℹ️ Hoje é {['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'][today.weekday()]}")
                print(f"   ℹ️ Delnext trabalha Segunda-Sexta, usando última sexta: {target_date}")
            
            # Continuar com scraping
            outbound_data = scrape_outbound_safe(page, target_date=target_date, zone_filter="VianaCastelo")
            
            # Salvar JSON
            screenshots_dir = Path("debug_files/delnext_poc_manual")
            output_file = screenshots_dir / "delnext_data_vianaCastelo.json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": start_time.isoformat(),
                    "query_date": target_date,
                    "login_method": "automatic" if login_success else "manual",
                    "outbound": outbound_data,
                }, f, indent=2, ensure_ascii=False)
            
            # Relatório
            print("\n" + "=" * 60)
            print("📊 RELATÓRIO FINAL")
            print("=" * 60)
            print(f"✅ Login: {'Automático' if login_success else 'Manual'}")
            print(f"📤 Entregas (VianaCastelo): {len(outbound_data)}")
            
            if len(outbound_data) > 0:
                print("\n📦 Primeiras 5 entregas:")
                for i, item in enumerate(outbound_data[:5], 1):
                    print(f"   {i}. {item['product_id']} - {item['customer_name']}")
                    print(f"      📍 {item['city']} ({item['postal_code']})")
                    print(f"      📅 {item['date']}")
                    print()
                
                print(f"💾 JSON salvo: {output_file}")
                print(f"📸 Screenshots: {screenshots_dir}")
                
                # Estatísticas
                zones = {}
                for item in outbound_data:
                    zone = item['destination_zone']
                    zones[zone] = zones.get(zone, 0) + 1
                
                if len(zones) > 1:
                    print(f"\n📊 Distribuição por zona:")
                    for zone, count in sorted(zones.items(), key=lambda x: x[1], reverse=True):
                        print(f"   • {zone}: {count} entregas")
            else:
                print("\n⚠️ Nenhuma entrega encontrada para VianaCastelo")
            
            print("\n✅ POC CONCLUÍDO!")
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            print(f"⏱️ Tempo total: {execution_time:.1f}s")
            
        except Exception as e:
            print(f"\n❌ Erro crítico: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            print("\n⏸️ Aperte Enter para fechar o navegador...")
            input()
            browser.close()


if __name__ == "__main__":
    run_full_auto_poc()
