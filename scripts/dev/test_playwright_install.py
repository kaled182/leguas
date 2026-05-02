#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Validação de Instalação Playwright

Script rápido para verificar se Playwright está instalado e funcionando.
"""

def test_playwright_installation():
    """Testa se Playwright está instalado corretamente"""
    print("=" * 60)
    print("🧪 TESTE DE INSTALAÇÃO PLAYWRIGHT")
    print("=" * 60)
    
    # Teste 1: Importação
    print("\n1️⃣ Testando importação...")
    try:
        from playwright.sync_api import sync_playwright
        print("   ✅ Playwright importado com sucesso")
    except ImportError as e:
        print(f"   ❌ ERRO: Playwright não está instalado")
        print(f"      {e}")
        print("\n   Para instalar:")
        print("      pip install playwright")
        print("      playwright install chromium")
        return False
    
    # Teste 2: Lançar navegador
    print("\n2️⃣ Testando lançamento do navegador...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            print("   ✅ Navegador Chromium lançado com sucesso")
            
            # Teste 3: Criar página
            print("\n3️⃣ Testando criação de página...")
            page = browser.new_page()
            print("   ✅ Página criada")
            
            # Teste 4: Navegar
            print("\n4️⃣ Testando navegação...")
            page.goto("https://www.google.com")
            title = page.title()
            print(f"   ✅ Navegou para Google")
            print(f"      Título: {title}")
            
            browser.close()
            print("\n5️⃣ Navegador fechado")
            
    except Exception as e:
        print(f"   ❌ ERRO ao testar navegador: {e}")
        print("\n   O navegador pode não estar instalado.")
        print("   Execute: playwright install chromium")
        return False
    
    print("\n" + "=" * 60)
    print("✅ TODOS OS TESTES PASSARAM!")
    print("=" * 60)
    print("\n🎯 Playwright está pronto para uso!")
    print("   Você pode executar: python delnext_poc_playwright.py")
    print()
    
    return True


if __name__ == "__main__":
    success = test_playwright_installation()
    exit(0 if success else 1)
