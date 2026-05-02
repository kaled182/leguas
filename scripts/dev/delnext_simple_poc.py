"""
POC Delnext - Login Manual Simplificado
Você loga, aperta Enter, script continua
"""

from playwright.sync_api import sync_playwright, Page
from pathlib import Path
import json
from datetime import datetime


def scrape_outbound(page: Page, zone_filter: str = None) -> list:
    """Extrai previsão de pacotes (Outbound)"""
    try:
        print("\n📤 Capturando Outbound (Previsão de Entregas)")
        print(f"   URL: https://www.delnext.com/admind/outbound_consult.php")
        
        page.goto("https://www.delnext.com/admind/outbound_consult.php", wait_until="networkidle", timeout=60000)
        
        screenshots_dir = Path("debug_files/delnext_poc_manual")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshots_dir / "02_outbound_page.png"))
        
        # Aguardar tabela
        print("   ⏳ Aguardando tabela...")
        page.wait_for_selector("table", timeout=15000)
        print("   ✅ Tabela encontrada")
        
        rows = page.query_selector_all("table tr")
        print(f"   📋 Total de linhas: {len(rows)}")
        
        if len(rows) <= 1:
            print("   ⚠️ TABELA VAZIA")
            return []
        
        data = []
        
        for i, row in enumerate(rows):
            if i == 0:  # Skip header
                continue
            
            cells = row.query_selector_all("td")
            
            if cells and len(cells) >= 8:
                cell_data = [cell.text_content().strip() for cell in cells]
                product_id = cell_data[0]
                
                if product_id and product_id != "":
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
        
        # Aplicar filtro
        if zone_filter:
            original_count = len(data)
            data = [item for item in data if zone_filter.lower() in item['destination_zone'].lower()]
            print(f"   🔍 Filtro: '{zone_filter}'")
            print(f"   ✅ Filtrados: {len(data)} de {original_count} ({len(data)/original_count*100:.1f}%)")
        
        return data
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return []


def run_simple_poc():
    """POC simplificado com login manual"""
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║  DELNEXT POC - LOGIN MANUAL SIMPLIFICADO                ║
╚═══════════════════════════════════════════════════════════╝

Credenciais:
  Usuário: VianaCastelo
  Senha: HelloViana23432

Passos:
  1. O navegador abrirá
  2. Faça login manualmente
  3. Volte aqui e aperte Enter
  4. O script continuará automaticamente

Pressione Enter para abrir o navegador...
    """)
    input()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--start-maximized']
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()
        
        try:
            # Abrir página de login
            print("\n🌐 Abrindo página de login...")
            page.goto("https://www.delnext.com/admind/index.php", timeout=60000)
            
            screenshots_dir = Path("debug_files/delnext_poc_manual")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshots_dir / "00_login_page.png"))
            
            print("\n" + "=" * 60)
            print("⏸️  FAÇA O LOGIN NO NAVEGADOR")
            print("=" * 60)
            print("\n👉 Quando terminar de logar, volte aqui e aperte Enter...")
            input()
            
            # Tirar screenshot após login
            page.screenshot(path=str(screenshots_dir / "01_after_login.png"))
            print("\n✅ Continuando...")
            
            # Scraping Outbound
            outbound_data = scrape_outbound(page, zone_filter="VianaCastelo")
            
            # Salvar JSON
            output_file = screenshots_dir / "delnext_data_vianaCastelo.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "outbound": outbound_data,
                }, f, indent=2, ensure_ascii=False)
            
            # Relatório
            print("\n" + "=" * 60)
            print("📊 RESULTADO")
            print("=" * 60)
            print(f"✅ Entregas capturadas (VianaCastelo): {len(outbound_data)}")
            
            if len(outbound_data) > 0:
                print("\n📦 Primeiras 5 entregas:")
                for i, item in enumerate(outbound_data[:5], 1):
                    print(f"   {i}. {item['product_id']} - {item['customer_name']}")
                    print(f"      {item['city']} ({item['postal_code']})")
                
                print(f"\n💾 JSON salvo: {output_file}")
                print(f"📸 Screenshots: {screenshots_dir}")
            else:
                print("\n⚠️ Nenhuma entrega encontrada para VianaCastelo")
            
            print("\n✅ POC CONCLUÍDO!")
            
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            print("\n⏸️ Aperte Enter para fechar o navegador...")
            input()
            browser.close()


if __name__ == "__main__":
    run_simple_poc()
