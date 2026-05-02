import requests

url = "http://localhost:8000/orders/geocoding-failures/"

try:
    response = requests.get(url)
    html = response.text
    
    print(f"✅ STATUS: {response.status_code}")
    print(f"✅ TAMANHO: {len(response.content)} bytes\n")
    
    # Verificações básicas
    checks = {
        '<main class="flex-1': "Tag <main> com flex-1",
        'Falhas de Geocodificação': "Título da página",
        'Não Resolvidos': "Card de não resolvidos",
        'Taxa de Sucesso': "Card de taxa de sucesso",
        'bg-red-500': "Border vermelho",
        'bg-green-500': "Border verde",
    }
    
    print("🔍 VERIFICAÇÕES:\n")
    for text, description in checks.items():
        if text in html:
            print(f"✅ {description}")
        else:
            print(f"❌ {description}")
    
    print(f"\n📏 Tamanho comparativo:")
    print(f"  - Template standalone: ~22KB")
    print(f"  - Template integrado anterior: ~48KB")
    print(f"  - Template atual: {len(response.content) // 1024}KB")
    
    # Mostrar um pedaço do HTML onde deveria estar o main
    if '<main' in html:
        idx = html.find('<main')
        print(f"\n--- Preview (500 chars a partir de <main>) ---")
        print(html[idx:idx+500])
    else:
        print("\n⚠️ Tag <main> não encontrada no HTML!")
        # Mostrar o que tem depois do body
        if '<body' in html:
            idx = html.find('<body')
            print("\n--- Preview (500 chars depois de <body>) ---")
            print(html[idx:idx+500])
            
except Exception as e:
    print(f"❌ ERRO: {e}")
