#!/usr/bin/env python
"""
Teste simples do Playwright - Diagnóstico
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_project.settings')
django.setup()

from playwright.sync_api import sync_playwright

print("=" * 70)
print("TESTE PLAYWRIGHT - DIAGNÓSTICO")
print("=" * 70)

try:
    print("\n1. Tentando inicializar Playwright...")
    with sync_playwright() as p:
        print("   ✅ Playwright inicializado")
        
        print("\n2. Tentando lançar navegador Chromium...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        print("   ✅ Browser lançado")
        
        print("\n3. Tentando criar contexto...")
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        print("   ✅ Contexto criado")
        
        print("\n4. Tentando criar página...")
        page = context.new_page()
        print("   ✅ Página criada")
        
        print("\n5. Tentando navegar para site simples...")
        page.goto("https://example.com", timeout=30000)
        title = page.title()
        print(f"   ✅ Navegação OK - Título: {title}")
        
        print("\n6. Fechando browser...")
        browser.close()
        print("   ✅ Browser fechado")
        
    print("\n" + "=" * 70)
    print("✅ TESTE COMPLETO - PLAYWRIGHT FUNCIONAL!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERRO: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    print("=" * 70)
