"""
POC Delnext - Versão com Login Manual
Para contornar Cloudflare Turnstile

Execute este script e faça o login manualmente quando o navegador abrir.
O script esperará você completar o login e depois continuará automaticamente.
"""

from playwright.sync_api import sync_playwright, Page
from pathlib import Path
import json
from datetime import datetime
import time


class DelnextPOCManualLogin:
    def __init__(self):
        self.base_url = "https://www.delnext.com/admind/"
        self.screenshots_dir = Path("debug_files/delnext_poc_manual")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Estatísticas
        self.stats = {
            "login_success": False,
            "inbound_records": 0,
            "outbound_records": 0,
            "stats_page_accessed": False,
            "errors": [],
        }
    
    def wait_for_manual_login(self, page: Page) -> bool:
        """Aguarda login manual do usuário"""
        try:
            print("\n" + "=" * 70)
            print("⏸️  PAUSADO: FAÇA O LOGIN MANUALMENTE")
            print("=" * 70)
            print()
            print("👉 Passos:")
            print("   1. Digite suas credenciais no navegador que abriu")
            print("   2. Complete o Cloudflare Turnstile (se aparecer)")
            print("   3. Clique em Login")
            print("   4. Aguarde o dashboard carregar")
            print()
            print("⏳ O script detectará automaticamente quando você logar...")
            print()
            
            # Aguardar até que NÃO esteja mais na página de login
            # (detecta mudança de URL ou presença de elementos do dashboard)
            max_wait = 300  # 5 minutos
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                current_url = page.url
                
                # Verificar se saiu da página de login
                if "index.php" not in current_url or "login" not in current_url.lower():
                    # Verificar se chegou no dashboard
                    if "admind" in current_url:
                        print("\n✅ Login detectado com sucesso!")
                        print(f"   URL atual: {current_url}")
                        
                        # Aguardar página estabilizar
                        page.wait_for_load_state("networkidle", timeout=10000)
                        page.screenshot(path=str(self.screenshots_dir / "01_after_manual_login.png"))
                        
                        self.stats["login_success"] = True
                        return True
                
                # Aguardar 1s antes de verificar novamente
                time.sleep(1)
            
            print("\n❌ Timeout: Login não foi completado em 5 minutos")
            return False
            
        except Exception as e:
            print(f"\n❌ Erro aguardando login: {e}")
            return False
    
    def scrape_outbound(self, page: Page, test_date: str = "Feb 27, 2026", zone_filter: str = None) -> list:
        """Extrai previsão de pacotes (Outbound)"""
        try:
            print("\n📤 FASE 2: Capturando Outbound (Previsão de Entregas)")
            print(f"   URL: {self.base_url}outbound_consult.php")
            
            page.goto(f"{self.base_url}outbound_consult.php", wait_until="networkidle", timeout=60000)
            page.screenshot(path=str(self.screenshots_dir / "02_outbound_page.png"))
            
            # Aguardar tabela
            try:
                page.wait_for_selector("table", timeout=10000)
                print("   ✅ Tabela encontrada")
            except:
                print("   ⚠️ Tabela não encontrada")
                return []
            
            rows = page.query_selector_all("table tr")
            print(f"   📋 Total de linhas na tabela: {len(rows)}")
            
            # Verificar se tabela está vazia
            if len(rows) <= 1:
                page_text = page.text_content("body").lower()
                if any(msg in page_text for msg in ["no data available", "showing 0 to 0"]):
                    print("   ⚠️ TABELA VAZIA - Nenhuma entrega agendada para esta data")
                    return []
            
            data = []
            headers = []
            
            for i, row in enumerate(rows):
                # Primeira linha: headers
                if i == 0:
                    header_cells = row.query_selector_all("th")
                    if header_cells:
                        headers = [cell.text_content().strip() for cell in header_cells]
                        print(f"   📌 Colunas detectadas: {len(headers)}")
                    continue
                
                # Linhas de dados
                cells = row.query_selector_all("td")
                
                if cells and len(cells) >= 8:
                    cell_data = [cell.text_content().strip() for cell in cells]
                    product_id = cell_data[0]
                    
                    if product_id and product_id != "":
                        row_dict = {
                            "product_id": product_id,
                            "parcel_id": product_id,
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
            
            print(f"\n   🎯 Total extraído: {len(data)} entregas agendadas")
            
            # Aplicar filtro por zona se especificado
            if zone_filter:
                original_count = len(data)
                data = [item for item in data if zone_filter.lower() in item['destination_zone'].lower()]
                print(f"   🔍 Filtro aplicado: Destination Zone = '{zone_filter}'")
                print(f"   ✅ Resultados filtrados: {len(data)} de {original_count} ({len(data)/original_count*100:.1f}%)")
            
            self.stats["outbound_records"] = len(data)
            return data
            
        except Exception as e:
            print(f"   ❌ Erro ao capturar Outbound: {e}")
            try:
                page.screenshot(path=str(self.screenshots_dir / "error_outbound.png"))
            except:
                pass
            self.stats["errors"].append(f"Outbound error: {str(e)}")
            return []
    
    def run_poc(self):
        """Executa POC com login manual"""
        start_time = datetime.now()
        
        print("=" * 70)
        print("🚀 DELNEXT POC - LOGIN MANUAL (Contorna Cloudflare)")
        print("=" * 70)
        print(f"Início: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Screenshots: {self.screenshots_dir}")
        
        with sync_playwright() as p:
            # Lançar navegador (SEMPRE visível para login manual)
            browser = p.chromium.launch(
                headless=False,
                args=['--start-maximized']
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            
            try:
                # FASE 1: Navegar para página de login
                print("\n🔐 FASE 1: Navegando para página de login...")
                page.goto(f"{self.base_url}index.php", timeout=60000)
                page.screenshot(path=str(self.screenshots_dir / "00_login_page.png"))
                
                # FASE 1.5: Aguardar login manual
                if not self.wait_for_manual_login(page):
                    print("\n❌ POC ABORTADO: Login não foi completado")
                    browser.close()
                    return
                
                # FASE 2: Scraping Outbound com filtro VianaCastelo
                print("\n💡 Capturando Outbound com filtro VianaCastelo...")
                outbound_data = self.scrape_outbound(
                    page, 
                    test_date="Feb 27, 2026",
                    zone_filter="VianaCastelo"
                )
                
                # Salvar dados em JSON
                output_data = {
                    "timestamp": start_time.isoformat(),
                    "outbound": outbound_data,
                }
                
                output_file = self.screenshots_dir / "delnext_data_vianaCastelo.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                print(f"\n💾 Dados salvos: {output_file}")
                
                # Relatório final
                print("\n" + "=" * 70)
                print("📊 RELATÓRIO FINAL")
                print("=" * 70)
                print(f"✅ LOGIN: SUCESSO (manual)")
                print(f"📤 OUTBOUND: {len(outbound_data)} entregas (VianaCastelo)")
                
                if len(outbound_data) > 0:
                    print("\n📦 Primeiras 5 entregas:")
                    for i, item in enumerate(outbound_data[:5], 1):
                        print(f"   {i}. {item['product_id']} - {item['customer_name']}")
                        print(f"      {item['city']} ({item['postal_code']})")
                
                print("\n✅ POC CONCLUÍDO COM SUCESSO!")
                print(f"📁 Screenshots salvos em: {self.screenshots_dir}")
                print(f"📄 JSON gerado: {output_file}")
                
            except Exception as e:
                print(f"\n❌ ERRO CRÍTICO: {e}")
                try:
                    if not page.is_closed():
                        page.screenshot(path=str(self.screenshots_dir / "error_critical.png"))
                except:
                    pass
            
            finally:
                print("\n⏸️  Pressione Enter para fechar o navegador...")
                input()
                browser.close()
        
        # Calcular tempo de execução
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        print(f"\n⏱️ Tempo total: {execution_time:.1f}s")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║  DELNEXT POC - VERSÃO LOGIN MANUAL                         ║
║  Contorna Cloudflare Turnstile                             ║
╚══════════════════════════════════════════════════════════════╝

Este script abrirá um navegador e AGUARDARÁ você fazer login
manualmente. Use suas credenciais:

   Usuário: VianaCastelo
   Senha: HelloViana23432

Após o login, o script continuará automaticamente.

Pressione Enter para iniciar...
    """)
    input()
    
    poc = DelnextPOCManualLogin()
    poc.run_poc()
