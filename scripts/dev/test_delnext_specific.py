#!/usr/bin/env python
"""
Teste específico Delnext - Identificar ponto exato do erro
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from playwright.sync_api import sync_playwright
import time
import random
import json
import urllib.parse
from datetime import datetime, timedelta

print("=" * 70)
print("TESTE DELNEXT - DIAGNÓSTICO ESPECÍFICO")
print("=" * 70)

base_url = "https://www.delnext.com/admind"
username = "VianaCastelo"
password = "HelloViana23432"

# Calcular última sexta-feira
today = datetime.now()
if today.weekday() == 5:  # Sábado
    last_friday = today - timedelta(days=1)
elif today.weekday() == 6:  # Domingo
    last_friday = today - timedelta(days=2)
else:
    last_friday = today
date = last_friday.strftime("%Y-%m-%d")
zone = "VianaCastelo"

print(f"\nParâmetros:")
print(f"  Data: {date}")
print(f"  Zona: {zone}")
print(f"  URL: {base_url}")

try:
    with sync_playwright() as p:
        print("\n1. Lançando browser...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        print("   ✅ Browser lançado")
        
        print("\n2. Criando contexto...")
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            locale='pt-PT',
            timezone_id='Europe/Lisbon'
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        print("   ✅ Contexto criado")
        
        print("\n3. Criando página...")
        page = context.new_page()
        print("   ✅ Página criada")
        
        print(f"\n4. Navegando para login ({base_url}/index.php)...")
        page.goto(f"{base_url}/index.php", timeout=90000)
        print("   ✅ Página de login carregada")
        
        print("\n5. Aguardando Cloudflare (8s)...")
        time.sleep(8)
        print("   ✅ Espera concluída")
        
        print("\n6. Pr eenchendo formulário de login...")
        page.fill("input[type='text']", username)
        time.sleep(random.uniform(0.5, 1.5))
        page.fill("input[type='password']", password)
        time.sleep(random.uniform(0.5, 1.5))
        print("   ✅ Formulário preenchido")
        
        print("\n7. Submetendo login...")
        page.click("input[type='submit']")
        time.sleep(5)
        print("   ✅ Login submetido")
        
        print("\n8. Construindo URL com filtros...")
        date_range = {"start": date, "end": date}
        date_range_encoded = urllib.parse.quote(json.dumps(date_range))
        url = f"{base_url}/outbound_consult.php?date_range={date_range_encoded}&zone={zone}"
        print(f"   URL: {url}")
        
        print("\n9. Navegando para página de resultados...")
        page.goto(url, timeout=30000)
        time.sleep(3)
        print("   ✅ Página de resultados carregada")
        
        print("\n10. Procurando por tabela...")
        tables = page.query_selector_all("table")
        print(f"   ✅ Encontradas {len(tables)} tabela(s)")
        
        if tables:
            print("\n11. Extraindo linhas da primeira tabela...")
            rows = page.query_selector_all("table tr")
            print(f"   ✅ Encontradas {len(rows)} linha(s)")
            
            print("\n12. Extraindo dados (apenas primeiras 3 linhas)...")
            for i, row in enumerate(rows[:3]):
                print(f"\n   Linha {i}:")
                cells = row.query_selector_all("td")
                print(f"     - Células: {len(cells)}")
                if cells:
                    # Extrair dados de forma segura
                    cell_data = []
                    for cell in cells:
                        cell_data.append(cell.text_content().strip())
                    print(f"     - Dados: {cell_data[:5]}...")  # Apenas primeiros 5
        
        print("\n13. Fechando browser...")
        browser.close()
        print("   ✅ Browser fechado")
        
    print("\n" + "=" * 70)
    print("✅ TESTE COMPLETO - SEM ERROS!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERRO: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 70)
