import requests
from bs4 import BeautifulSoup

url = "http://localhost:8000/orders/geocoding-failures/"

response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

print(f"STATUS: {response.status_code}")
print(f"TAMANHO: {len(response.content)} bytes\n")

# Procurar pelo main tag
main_tag = soup.find('main')
if main_tag:
    print("✅ Tag <main> encontrada!")
    print(f"Classes: {main_tag.get('class')}\n")
else:
    print("❌ Tag <main> NÃO encontrada!\n")

# Procurar o título
title = soup.find('h1')
if title:
    print(f"✅ Título: {title.text.strip()}\n")
else:
    print("❌ Título não encontrado\n")

# Procurar os stats cards
stats_divs = soup.find_all('div', class_='grid grid-cols-1 md:grid-cols-4')
if stats_divs:
    print(f"✅ Grid de estatísticas encontrado ({len(stats_divs)} grids)\n")
    
    # Pegar os números
    numbers = soup.find_all('div', class_='text-3xl')
    if numbers:
        print("📊 Estatísticas:")
        for i, num in enumerate(numbers[:4]):
            print(f"  {i+1}. {num.text.strip()}")
else:
    print("❌ Grid de estatísticas não encontrado\n")

# Procurar failures
failures = soup.find_all('div', class_='bg-white dark:bg-gray-800 rounded-lg shadow p-4')
print(f"\n🗂️ Falhas encontradas: {len(failures)}")

print("\n--- Preview do HTML (primeiros 500 chars após <main>) ---")
if main_tag:
    print(str(main_tag)[:500])
