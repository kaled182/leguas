import requests

# Criar uma sessão para manter cookies
session = requests.Session()

# Tentar acessar a página de login para pegar o CSRF token
login_url = "http://localhost:8000/login/"
response = session.get(login_url)

# Pegar o CSRF token
import re
csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.text)
if csrf_match:
    csrf_token = csrf_match.group(1)
    print(f"✅ CSRF Token obtido: {csrf_token[:20]}...")
    
    # Fazer login (ajuste as credenciais se necessário)
    login_data = {
        'csrfmiddlewaretoken': csrf_token,
        'username': 'admin',  # Ajuste conforme necessário
        'password': 'admin',  # Ajuste conforme necessário
    }
    
    login_response = session.post(login_url, data=login_data, headers={'Referer': login_url})
    
    if login_response.status_code == 200 and 'login' not in login_response.url:
        print("✅ Login realizado com sucesso!")
    else:
        print(f"⚠️ Login pode ter falhado (status: {login_response.status_code}, url: {login_response.url})")
        print("   Tentando acessar a página mesmo assim...")
else:
    print("⚠️ Não foi possível obter o CSRF token, tentando sem login...")

# Agora tentar acessar a página de geocoding failures
url = "http://localhost:8000/orders/geocoding-failures/"
response = session.get(url)

print(f"\n{'='*60}")
print(f"STATUS: {response.status_code}")
print(f"URL FINAL: {response.url}")
print(f"TAMANHO: {len(response.content)} bytes ({len(response.content) // 1024}KB)")
print(f"{'='*60}\n")

html = response.text

# Verificações
checks = {
    '<main class="flex-1': "Tag <main> com flex-1",
    'Falhas de Geocodificação': "Título da página",
    'Não Resolvidos': "Card de não resolvidos",
    'Taxa de Sucesso': "Card de taxa de sucesso",
    'bg-red-500': "Border vermelho",
    'bg-green-500': "Border verde",
    'class="text-3xl font-bold text-red-600"': "Número vermelho (não resolvidos)",
}

print("🔍 VERIFICAÇÕES:\n")
for text, description in checks.items():
    if text in html:
        print(f"✅ {description}")
    else:
        print(f"❌ {description}")

# Mostrar preview se encontrou main
if '<main' in html:
    idx = html.find('<main')
    print(f"\n--- Preview (600 chars a partir de <main>) ---")
    print(html[idx:idx+600])
else:
    print("\n⚠️ Tag <main> não encontrada!")
    if 'login' in response.url.lower() or 'login' in html[:1000].lower():
        print("❌ Redirecionado para login - precisa autenticar!")
    else:
        if '<body' in html:
            idx = html.find('<body')
            print("\n--- Preview (400 chars depois de <body>) ---")
            print(html[idx:idx+400])
