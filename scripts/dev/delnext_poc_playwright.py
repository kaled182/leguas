#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
POC Delnext - Web Scraping com Playwright

Este script demonstra a viabilidade de scraping do sistema Delnext.
Funcionalidades:
- Login automatizado
- Network interception (detecta APIs JSON escondidas)
- Extração de dados de Inbound, Outbound e Stats
- Geração de relatório + JSON + screenshots

Autor: Léguas Franzinas IT Team
Data: 01/03/2026
"""

import json
import os
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Response


class DelnextPlaywrightPOC:
    """Proof of Concept - Scraping Delnext com Playwright"""
    
    def __init__(self):
        self.base_url = "https://www.delnext.com/admind/"
        self.username = "VianaCastelo"
        self.password = "HelloViana23432"
        self.api_endpoints_found = []
        self.screenshots_dir = Path("debug_files/delnext_poc")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Estatísticas
        self.stats = {
            "login_success": False,
            "inbound_records": 0,
            "outbound_records": 0,
            "stats_page_accessed": False,
            "api_endpoints_found": 0,
            "execution_time_seconds": 0,
            "errors": [],
        }
    
    def log_response(self, response: Response):
        """
        Monitora requisições de rede - detecta APIs JSON escondidas
        Esta é a FEATURE KILLER do Playwright vs Selenium!
        """
        url = response.url
        
        # Procurar por endpoints API/JSON/AJAX
        api_keywords = ['api', 'json', 'ajax', 'data', 'fetch', 'xhr']
        
        if any(keyword in url.lower() for keyword in api_keywords):
            content_type = response.headers.get('content-type', '')
            
            print(f"\n🔴 API DETECTADA:")
            print(f"   URL: {url}")
            print(f"   Status: {response.status}")
            print(f"   Content-Type: {content_type}")
            
            # Tentar capturar resposta JSON
            try:
                if 'json' in content_type.lower():
                    json_data = response.json()
                    print(f"   📦 JSON Response (primeiras 200 chars):")
                    print(f"      {str(json_data)[:200]}...")
                    
                    self.api_endpoints_found.append({
                        "url": url,
                        "status": response.status,
                        "content_type": content_type,
                        "has_json": True,
                    })
            except:
                self.api_endpoints_found.append({
                    "url": url,
                    "status": response.status,
                    "content_type": content_type,
                    "has_json": False,
                })
    
    def login(self, page: Page) -> bool:
        """Realiza login no Delnext"""
        try:
            print("\n🔐 FASE 1: Login no Delnext")
            print(f"   URL: {self.base_url}index.php")
            print(f"   Usuário: {self.username}")
            
            # Navegar para página de login (timeout maior para Cloudflare)
            page.goto(f"{self.base_url}index.php", wait_until="networkidle", timeout=60000)
            
            # Tirar screenshot da página de login
            page.screenshot(path=str(self.screenshots_dir / "01_login_page.png"))
            print("   📸 Screenshot: 01_login_page.png")
            
            # Detectar Cloudflare e aguardar se necessário
            page_content = page.content().lower()
            if "cloudflare" in page_content or "turnstile" in page_content:
                print("   🛡️ Cloudflare Turnstile detectado - aguardando 10s...")
                page.wait_for_timeout(10000)  # Aguardar challenge completar
                page.screenshot(path=str(self.screenshots_dir / "01b_after_cloudflare.png"))
            
            # Tentar encontrar campos de login (vários seletores possíveis)
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
            
            # Encontrar campo de username
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = page.query_selector(selector)
                    if username_field:
                        print(f"   ✅ Campo username encontrado: {selector}")
                        break
                except:
                    continue
            
            if not username_field:
                print("   ❌ Campo de username não encontrado!")
                page.screenshot(path=str(self.screenshots_dir / "error_no_username_field.png"))
                return False
            
            # Encontrar campo de password
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = page.query_selector(selector)
                    if password_field:
                        print(f"   ✅ Campo password encontrado: {selector}")
                        break
                except:
                    continue
            
            if not password_field:
                print("   ❌ Campo de password não encontrado!")
                page.screenshot(path=str(self.screenshots_dir / "error_no_password_field.png"))
                return False
            
            # Preencher credenciais
            username_field.fill(self.username)
            password_field.fill(self.password)
            print("   ✅ Credenciais preenchidas")
            
            # Procurar botão de submit
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Login')",
                "button:has-text('Entrar')",
                "button:has-text('Sign in')",
                ".btn-login",
                "#login-button",
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = page.query_selector(selector)
                    if submit_button:
                        print(f"   ✅ Botão de login encontrado: {selector}")
                        break
                except:
                    continue
            
            if not submit_button:
                print("   ⚠️ Botão de submit não encontrado, tentando Enter...")
                password_field.press("Enter")
            else:
                submit_button.click()
            
            print("   ⏳ Aguardando redirecionamento...")
            
            # Aguardar navegação (várias possibilidades)
            try:
                # Opção 1: URL muda para dashboard
                page.wait_for_url("**/dashboard**", timeout=5000)
                print("   ✅ Redirecionado para dashboard")
            except:
                try:
                    # Opção 2: URL muda para qualquer outra página
                    page.wait_for_load_state("networkidle", timeout=5000)
                    print(f"   ✅ Página carregada: {page.url}")
                except:
                    print("   ⚠️ Timeout no redirecionamento, continuando...")
            
            # Verificar se login foi bem-sucedido
            current_url = page.url
            
            # Screenshots pós-login
            page.screenshot(path=str(self.screenshots_dir / "02_after_login.png"))
            print("   📸 Screenshot: 02_after_login.png")
            
            # Verificar se ainda está na página de login
            if "index.php" in current_url or "login" in current_url.lower():
                print("   ❌ Login falhou - ainda na página de login")
                
                # Procurar mensagem de erro
                error_selectors = [".error", ".alert", ".message", "#error"]
                for selector in error_selectors:
                    error_msg = page.query_selector(selector)
                    if error_msg:
                        print(f"      Erro: {error_msg.text_content()}")
                
                return False
            
            print(f"   ✅ Login realizado com sucesso!")
            print(f"      URL atual: {current_url}")
            self.stats["login_success"] = True
            return True
            
        except Exception as e:
            print(f"   ❌ Erro no login: {e}")
            page.screenshot(path=str(self.screenshots_dir / "error_login.png"))
            self.stats["errors"].append(f"Login error: {str(e)}")
            return False
    
    def scrape_inbound(self, page: Page) -> list:
        """Extrai dados de Inbound Partners"""
        try:
            print("\n📥 FASE 2: Capturando Inbound Partners")
            print(f"   URL: {self.base_url}inbound_partners.php")
            
            page.goto(f"{self.base_url}inbound_partners.php", wait_until="networkidle")
            page.screenshot(path=str(self.screenshots_dir / "03_inbound_page.png"))
            
            # Aguardar tabela aparecer
            try:
                page.wait_for_selector("table", timeout=10000)
                print("   ✅ Tabela encontrada")
            except:
                print("   ⚠️ Tabela não encontrada - página pode estar vazia")
                return []
            
            # Extrair dados da tabela
            rows = page.query_selector_all("table tr")
            print(f"   📋 Total de linhas na tabela: {len(rows)}")
            
            # Verificar se tabela está vazia
            if len(rows) <= 1:
                page_text = page.text_content("body").lower()
                if "no data available" in page_text or "showing 0 to 0" in page_text:
                    print("   ⚠️ TABELA VAZIA - Nenhum recebimento para esta data")
                    return []
            
            data = []
            headers = []
            
            for i, row in enumerate(rows):
                # Primeira linha: headers
                if i == 0:
                    header_cells = row.query_selector_all("th")
                    if header_cells:
                        headers = [cell.text_content().strip() for cell in header_cells]
                        print(f"   📌 Colunas: {', '.join(headers[:8])}")
                    continue
                
                # Linhas de dados
                cells = row.query_selector_all("td")
                
                if len(cells) >= 8:
                    # Extrair dados de cada célula
                    cell_data = [cell.text_content().strip() for cell in cells]
                    parcel_id = cell_data[0]
                    
                    if parcel_id and parcel_id != "":
                        row_dict = {
                            "parcel_id": parcel_id,
                            "admin_name": cell_data[1] if len(cell_data) > 1 else "",
                            "warehouse": cell_data[2] if len(cell_data) > 2 else "",
                            "destination_zone": cell_data[3] if len(cell_data) > 3 else "",
                            "country": cell_data[4] if len(cell_data) > 4 else "",
                            "city": cell_data[5] if len(cell_data) > 5 else "",
                            "date": cell_data[6] if len(cell_data) > 6 else "",
                            "comment": cell_data[7] if len(cell_data) > 7 else "",
                        }
                        data.append(row_dict)
                        print(f"   ✅ {i:3d}. {parcel_id} - {row_dict['city']}")
            
            print(f"\n   🎯 Total capturado: {len(data)} registros")
            self.stats["inbound_records"] = len(data)
            
            return data
            
        except Exception as e:
            print(f"   ❌ Erro ao capturar Inbound: {e}")
            page.screenshot(path=str(self.screenshots_dir / "error_inbound.png"))
            self.stats["errors"].append(f"Inbound error: {str(e)}")
            return []
    
    def select_date_in_datepicker(self, page: Page, date_str: str):
        """Seleciona data no datepicker (formato: Feb 27, 2026)"""
        try:
            print(f"   📅 Selecionando data: {date_str}")
            
            # Procurar campo de data
            date_selectors = [
                "input[name='date']",
                "input[id='date']",
                "#dateInput",
                ".datepicker",
                "input[type='text'].hasDatepicker"
            ]
            
            date_input = None
            for selector in date_selectors:
                try:
                    date_input = page.query_selector(selector)
                    if date_input:
                        print(f"      Campo de data encontrado: {selector}")
                        break
                except:
                    continue
            
            if date_input:
                # Limpar e preencher data
                date_input.click()
                date_input.fill("")
                date_input.type(date_str)
                date_input.press("Enter")
                
                # Aguardar página recarregar
                page.wait_for_load_state("networkidle", timeout=5000)
                print(f"      ✅ Data selecionada: {date_str}")
                return True
            else:
                print("      ⚠️ Campo de data não encontrado")
                return False
                
        except Exception as e:
            print(f"      ⚠️ Erro ao selecionar data: {e}")
            return False
    
    def scrape_outbound(self, page: Page, test_date: str = "Feb 27, 2026", zone_filter: str = None) -> list:
        """Extrai previsão de pacotes (Outbound) - PRIORIDADE ALTA
        
        Args:
            test_date: Data para consultar (formato: "Feb 27, 2026")
            zone_filter: Filtrar por Destination Zone (ex: "VianaCastelo", "2.0 Lisboa")
                        Se None, retorna todas as zonas
        """
        try:
            print("\n📤 FASE 3: Capturando Outbound (Previsão de Entregas)")
            print(f"   URL: {self.base_url}outbound_consult.php")
            print("   ⭐⭐⭐⭐⭐ Página CRÍTICA para planejamento de rotas!")
            
            page.goto(f"{self.base_url}outbound_consult.php", wait_until="networkidle")
            
            # Tentar selecionar data específica (se houver datepicker)
            self.select_date_in_datepicker(page, test_date)
            
            page.screenshot(path=str(self.screenshots_dir / "04_outbound_page.png"))
            
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
            if len(rows) <= 1:  # Só header ou vazia
                # Procurar mensagem "No data available"
                no_data_messages = [
                    "No data available in table",
                    "Showing 0 to 0 of 0 entries",
                    "sem dados",
                    "vazio"
                ]
                
                page_text = page.text_content("body").lower()
                is_empty = any(msg.lower() in page_text for msg in no_data_messages)
                
                if is_empty:
                    print("   ⚠️ TABELA VAZIA - Nenhuma entrega agendada para esta data")
                    print(f"      Dica: Tente outra data com dados (ex: {test_date})")
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
                        print(f"      {', '.join(headers[:8])}")  # Primeiras 8 colunas
                    continue
                
                # Linhas de dados
                cells = row.query_selector_all("td")
                
                if cells and len(cells) >= 8:  # Estrutura real: 11+ colunas
                    cell_data = [cell.text_content().strip() for cell in cells]
                    
                    # Estrutura REAL baseada nas screenshots:
                    # 0: Product ID
                    # 1: Destination Zone
                    # 2: Name (cliente)
                    # 3: Address
                    # 4: Postal Code
                    # 5: City
                    # 6: Date
                    # 7: Status
                    # 8: Admin
                    # 9: Inbound date
                    # 10: Inbound by
                    
                    product_id = cell_data[0]
                    
                    if product_id and product_id != "":
                        row_dict = {
                            "product_id": product_id,
                            "parcel_id": product_id,  # Alias para compatibilidade
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
                        
                        # Log resumido
                        destination = f"{row_dict['city']} ({row_dict['destination_zone']})"
                        print(f"   ✅ {i:3d}. {product_id} → {destination}")
            
            print(f"\n   🎯 Total extraído: {len(data)} entregas agendadas")
            
            # Aplicar filtro por zona se especificado
            if zone_filter:
                original_count = len(data)
                data = [item for item in data if zone_filter.lower() in item['destination_zone'].lower()]
                print(f"   🔍 Filtro aplicado: Destination Zone = '{zone_filter}'")
                print(f"   ✅ Resultados filtrados: {len(data)} de {original_count} ({len(data)/original_count*100:.1f}%)")
                
                if len(data) == 0:
                    print(f"   ⚠️ Nenhuma entrega encontrada para zona '{zone_filter}'")
                    print(f"   💡 Zonas disponíveis detectadas: Verifique os logs acima")
            
            self.stats["outbound_records"] = len(data)
            
            if len(data) == 0 and not zone_filter:
                print("   💡 DICA: Se a tabela estiver vazia, tente:")
                print("      - Selecionar outra data no site")
                print("      - Verificar se há entregas agendadas")
                print("      - Testar com data que sabidamente tem dados (ex: 27/02/2026)")
            
            return data
            
        except Exception as e:
            print(f"   ❌ Erro ao capturar Outbound: {e}")
            page.screenshot(path=str(self.screenshots_dir / "error_outbound.png"))
            self.stats["errors"].append(f"Outbound error: {str(e)}")
            return []
    
    def scrape_application_stats(self, page: Page) -> dict:
        """Captura estatísticas de operação"""
        try:
            print("\n📊 FASE 4: Capturando Application Stats")
            print(f"   URL: {self.base_url}application_stats.php")
            
            page.goto(f"{self.base_url}application_stats.php", wait_until="networkidle")
            page.screenshot(path=str(self.screenshots_dir / "05_stats_page.png"))
            
            # Procurar por diferentes elementos
            stats_data = {
                "drivers": [],
                "incidents": [],
                "deliveries_summary": {},
            }
            
            # Tentar capturar motoristas (vários seletores possíveis)
            driver_selectors = [
                ".driver-item",
                ".motorista",
                "[data-driver]",
                "table tr",  # Fallback: procurar em tabelas
            ]
            
            for selector in driver_selectors:
                drivers = page.query_selector_all(selector)
                if drivers:
                    print(f"   ✅ Encontrados {len(drivers)} elementos com '{selector}'")
                    stats_data["drivers"] = [d.text_content().strip() for d in drivers[:10]]
                    break
            
            self.stats["stats_page_accessed"] = True
            print(f"   ✅ Página de stats acessada com sucesso")
            
            return stats_data
            
        except Exception as e:
            print(f"   ❌ Erro ao capturar Stats: {e}")
            page.screenshot(path=str(self.screenshots_dir / "error_stats.png"))
            self.stats["errors"].append(f"Stats error: {str(e)}")
            return {}
    
    def run_poc(self):
        """Executa POC completo"""
        start_time = datetime.now()
        
        print("=" * 70)
        print("🚀 DELNEXT POC - PLAYWRIGHT WEB SCRAPING")
        print("=" * 70)
        print(f"Início: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Screenshots: {self.screenshots_dir}")
        
        with sync_playwright() as p:
            # Lançar navegador
            browser = p.chromium.launch(
                headless=False,  # headless=True para produção
                args=['--start-maximized']
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            
            # 🔴 FEATURE KILLER: Monitorar todas as requisições de rede!
            page.on("response", self.log_response)
            
            try:
                # FASE 1: Login
                if not self.login(page):
                    print("\n❌ POC ABORTADO: Falha no login")
                    browser.close()
                    return
                
                # FASE 2: Scraping Inbound
                inbound_data = self.scrape_inbound(page)
                
                # FASE 3: Scraping Outbound (PRIORITÁRIO)
                # Testar com data conhecida que tem dados: 27/02/2026
                # Filtrar apenas pela zona VianaCastelo
                print("\n💡 Testando Outbound com data 27/02/2026 + filtro VianaCastelo...")
                outbound_data = self.scrape_outbound(
                    page, 
                    test_date="Feb 27, 2026",
                    zone_filter="VianaCastelo"  # 🎯 Filtro para sua zona específica
                )
                
                # Se vazio, tentar data atual (mantendo filtro)
                if len(outbound_data) == 0:
                    print("\n💡 Tentando com data atual...")
                    outbound_data = self.scrape_outbound(
                        page, 
                        test_date="Mar 1, 2026",
                        zone_filter="VianaCastelo"  # Mantém filtro
                    )
                
                # FASE 4: Stats
                stats_data = self.scrape_application_stats(page)
                
                # Salvar dados em JSON
                output_data = {
                    "timestamp": start_time.isoformat(),
                    "inbound": inbound_data,
                    "outbound": outbound_data,
                    "stats": stats_data,
                    "api_endpoints": self.api_endpoints_found,
                }
                
                output_file = self.screenshots_dir / "delnext_data_sample.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                print(f"\n💾 Dados salvos: {output_file}")
                
            except Exception as e:
                print(f"\n❌ ERRO CRÍTICO: {e}")
                try:
                    if not page.is_closed():
                        page.screenshot(path=str(self.screenshots_dir / "error_critical.png"))
                except:
                    pass  # Ignorar se página já foi fechada
                self.stats["errors"].append(f"Critical error: {str(e)}")
            
            finally:
                # Screenshot final (verificar se página ainda está aberta)
                try:
                    if not page.is_closed():
                        page.screenshot(path=str(self.screenshots_dir / "06_final_page.png"))
                except:
                    pass  # Ignorar erro se página já foi fechada
                
                browser.close()
        
        # Calcular tempo de execução
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        self.stats["execution_time_seconds"] = round(execution_time, 2)
        self.stats["api_endpoints_found"] = len(self.api_endpoints_found)
        
        # RELATÓRIO FINAL
        self.print_final_report()
    
    def print_final_report(self):
        """Imprime relatório final do POC"""
        print("\n" + "=" * 70)
        print("📊 RELATÓRIO FINAL DO POC")
        print("=" * 70)
        
        print(f"\n✅ LOGIN:")
        print(f"   Status: {'SUCESSO ✅' if self.stats['login_success'] else 'FALHA ❌'}")
        
        print(f"\n📥 INBOUND:")
        print(f"   Registros capturados: {self.stats['inbound_records']}")
        if self.stats['inbound_records'] == 0:
            print("   ⚠️ Tabela vazia - sem recebimentos para a data consultada")
        
        print(f"\n📤 OUTBOUND (Planejamento de Entregas):")
        print(f"   Entregas agendadas: {self.stats['outbound_records']}")
        if self.stats['outbound_records'] == 0:
            print("   ⚠️ Tabela vazia - sem entregas agendadas")
            print("   💡 Solução: Selecionar data específica no datepicker")
            print("      Exemplo: 27/02/2026 (data com dados confirmados)")
        else:
            print(f"   ✅ Dados capturados com sucesso!")
            print("   📋 Campos extraídos:")
            print("      - Product ID (parcel_id)")
            print("      - Destination Zone (ex: VianaCastelo, 2.0 Lisboa)")
            print("      - Customer Name")
            print("      - Full Address")
            print("      - Postal Code")
            print("      - City")
            print("      - Date/Time")
            print("      - Status (ex: Enviada)")
            print("      - Admin")
        
        print(f"\n📊 STATS:")
        print(f"   Página acessada: {'SIM ✅' if self.stats['stats_page_accessed'] else 'NÃO ❌'}")
        
        print(f"\n🔴 NETWORK INTERCEPTION:")
        print(f"   APIs detectadas: {self.stats['api_endpoints_found']}")
        
        if self.api_endpoints_found:
            print("\n   🎯 ENDPOINTS ENCONTRADOS:")
            for endpoint in self.api_endpoints_found:
                status = "JSON ✅" if endpoint.get("has_json") else "Texto"
                print(f"      [{status}] {endpoint['url']}")
            
            print("\n   💡 RECOMENDAÇÃO:")
            print("      Se estes endpoints retornam JSON estruturado,")
            print("      considere usar REQUESTS direto (muito mais rápido!)")
        else:
            print("   ⚠️ Nenhuma API JSON escondida detectada")
            print("      ✅ Continuar com Playwright para scraping de HTML")
            print("      ✅ Sistema PHP tradicional (server-side rendering)")
        
        print(f"\n⏱️ PERFORMANCE:")
        print(f"   Tempo de execução: {self.stats['execution_time_seconds']}s")
        
        if self.stats["errors"]:
            print(f"\n❌ ERROS ({len(self.stats['errors'])}):")
            for error in self.stats["errors"]:
                print(f"   - {error}")
        
        print(f"\n📁 ARQUIVOS GERADOS:")
        print(f"   Screenshots: {self.screenshots_dir}")
        print(f"   JSON: {self.screenshots_dir / 'delnext_data_sample.json'}")
        
        print("\n" + "=" * 70)
        print("🎯 PRÓXIMOS PASSOS:")
        print("=" * 70)
        
        if self.stats["login_success"]:
            print("✅ POC BEM-SUCEDIDO!")
            print("\n📋 VALIDAÇÕES:")
            print(f"   {'✅' if self.stats['inbound_records'] > 0 else '⚠️'} Inbound: Estrutura de tabela validada")
            print(f"   {'✅' if self.stats['outbound_records'] > 0 else '⚠️'} Outbound: Parser funcionando corretamente")
            print(f"   {'✅' if self.stats['stats_page_accessed'] else '⚠️'} Stats: Página acessível")
            
            print("\n🚀 IMPLEMENTAÇÃO:")
            print("1. Revisar screenshots em debug_files/delnext_poc/")
            print("2. Analisar JSON gerado (estrutura de dados)")
            print("3. Confirmar: Nenhuma API REST (usar Playwright)")
            print("4. Criar estrutura: orders_manager/adapters/delnext/")
            print("5. Implementar:")
            print("   - scraper.py (Playwright)")
            print("   - mapper.py (Delnext → Order genérico)")
            print("   - status_mapping.py")
            print("6. Configurar sincronização automática (Celery)")
            
            print("\n💡 OBSERVAÇÕES IMPORTANTES:")
            print("   - Outbound precisa de seleção de data (datepicker)")
            print("   - Estrutura: 11 colunas (Product ID até Inbound By)")
            print("   - Datas com dados confirmados: 27/02/2026")
            print("   - Sistema é PHP server-side (sem API REST)")
            
        else:
            print("❌ POC FALHOU - Problemas no login")
            print("\n1. Verificar credenciais")
            print("2. Revisar screenshots de erro")
            print("3. Ajustar seletores CSS se necessário")
            print("4. Tentar novamente")
        
        print("\n" + "=" * 70)


if __name__ == "__main__":
    print("\n🎬 Iniciando POC Delnext com Playwright...\n")
    
    # Verificar se Playwright está instalado
    try:
        from playwright.sync_api import sync_playwright
        print("✅ Playwright instalado corretamente\n")
    except ImportError:
        print("❌ ERRO: Playwright não instalado!")
        print("\nPara instalar:")
        print("  pip install playwright")
        print("  playwright install chromium")
        exit(1)
    
    poc = DelnextPlaywrightPOC()
    poc.run_poc()
    
    print("\n✅ POC CONCLUÍDO!\n")
