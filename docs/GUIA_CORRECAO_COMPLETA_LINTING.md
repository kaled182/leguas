# Guia Completo: Como Corrigir TODOS os Warnings do Pylance

## 🎯 Objetivo
Deixar o código 100% limpo, sem nenhum warning, seguindo as melhores práticas.

## 📊 Tipos de Problemas e Soluções

### 1. **Line too long (X > 79 characters)**

#### Problema:
```python
# ❌ Linha muito longa
return JsonResponse({'error': 'Motorista não vinculado'}, status=400)
```

#### Solução:
```python
# ✅ Quebrar em múltiplas linhas
return JsonResponse(
    {'error': 'Motorista não vinculado'},
    status=400
)

# ✅ Ou usar variável intermediária
error_message = {'error': 'Motorista não vinculado'}
return JsonResponse(error_message, status=400)

# ✅ Quebrar strings longas
mensagem = (
    'Esta é uma mensagem muito longa que precisa '
    'ser quebrada em múltiplas linhas'
)
```

### 2. **Trailing whitespace**

#### Problema:
```python
def funcao():  
    return True  
```

#### Solução:
```python
def funcao():
    return True
```

**Como corrigir automaticamente:**
```bash
# No VS Code: Find and Replace (Ctrl+H)
# Find: (\s+)$
# Replace: (vazio)
# Use regex: Ativar
```

### 3. **Expected 2 blank lines, found 1**

#### Problema:
```python
def funcao1():
    return True

def funcao2():  # ❌ Precisa de 2 linhas em branco antes
    return False
```

#### Solução:
```python
def funcao1():
    return True


def funcao2():  # ✅ 2 linhas em branco
    return False
```

**Regra PEP8:**
- 2 linhas em branco entre funções/classes de nível superior
- 1 linha em branco entre métodos dentro de uma classe

### 4. **Imports não utilizados**

#### Problema:
```python
from django.contrib.auth import authenticate, login, logout, get_user_model
# Mas só usa 'login'
```

#### Solução:
```python
from django.contrib.auth import login
```

**Como corrigir automaticamente:**
```bash
docker-compose exec web autoflake --in-place --remove-all-unused-imports arquivo.py
```

### 5. **Imports duplicados**

#### Problema:
```python
from datetime import datetime
import re
from datetime import datetime  # ❌ Duplicado
import re  # ❌ Duplicado
```

#### Solução:
```python
import re
from datetime import datetime
```

### 6. **Ordem dos imports**

#### Problema:
```python
from django.http import JsonResponse
import json
from .models import Driver
import re
```

#### Solução (ordem PEP8):
```python
# 1. Biblioteca padrão
import json
import re

# 2. Bibliotecas terceiros
from django.http import JsonResponse

# 3. Imports locais
from .models import Driver
```

## 🔧 Comandos de Correção Automática

### Correção Completa (Recomendado):

```bash
# Dentro do container Docker
cd /app

# 1. Remover imports não usados
autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive --exclude=migrations,staticfiles,media .

# 2. Organizar imports
isort . --skip migrations --skip .venv --profile black

# 3. Formatar código (quebra linhas longas, corrige espaçamento)
black . --exclude "(migrations|\.venv|staticfiles|media)"

# 4. Correções PEP8 adicionais
autopep8 --in-place --aggressive --aggressive --recursive --exclude=migrations,staticfiles,media .
```

### Correção de Arquivo Específico:

```bash
FILE="caminho/para/arquivo.py"

autoflake --in-place --remove-all-unused-imports "$FILE"
isort "$FILE"
black "$FILE"
autopep8 --in-place --aggressive "$FILE"
```

## 📝 Casos Especiais

### Linhas Muito Longas (Regex, URLs, etc.)

```python
# ❌ Regex muito longa
if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
    ...

# ✅ Usar variável
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
if not re.match(EMAIL_REGEX, email):
    ...

# ✅ Ou usar constante no topo do arquivo
# No início do arquivo
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+'
    r'@[a-zA-Z0-9.-]+'
    r'\.[a-zA-Z]{2,}$'
)

# Uso
if not EMAIL_PATTERN.match(email):
    ...
```

### Mensagens de Erro Longas

```python
# ❌ Mensagem longa
messages.error(request, 'NIF invalido. Deve conter exatamente 9 digitos numericos.')

# ✅ Quebrar mensagem
messages.error(
    request,
    'NIF inválido. Deve conter exatamente 9 dígitos numéricos.'
)

# ✅ Ou usar constante
NIF_ERROR_MSG = 'NIF inválido. Deve conter exatamente 9 dígitos numéricos.'
messages.error(request, NIF_ERROR_MSG)
```

### Dicionários com Muitas Chaves

```python
# ❌ Uma linha muito longa
data = {'id': 1, 'nome': 'João', 'email': 'joao@example.com', 'telefone': '123456789'}

# ✅ Quebrar em múltiplas linhas
data = {
    'id': 1,
    'nome': 'João',
    'email': 'joao@example.com',
    'telefone': '123456789'
}
```

### List Comprehensions Longas

```python
# ❌ Muito longa
missing_fields = [field for field in required_fields if not data.get(field)]

# ✅ Quebrar
missing_fields = [
    field
    for field in required_fields
    if not data.get(field)
]

# ✅ Ou usar loop normal
missing_fields = []
for field in required_fields:
    if not data.get(field):
        missing_fields.append(field)
```

## 🚀 Script de Correção Único (PowerShell)

```powershell
# Salve como: fix_all_code.ps1

Write-Host "🔧 Corrigindo todos os problemas de código..." -ForegroundColor Cyan

docker-compose exec web bash -c @"
cd /app

echo '1. Removendo imports não utilizados...'
autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive --exclude=migrations,staticfiles,media,.venv .

echo '2. Organizando imports...'
isort . --skip migrations --skip .venv --skip staticfiles --skip media --profile black

echo '3. Formatando código com Black...'
black . --exclude '(migrations|\.venv|staticfiles|media|__pycache__)'

echo '4. Aplicando correções PEP8...'
autopep8 --in-place --aggressive --aggressive --recursive --exclude=migrations,staticfiles,media,.venv .

echo '✅ Concluído!'
"@

Write-Host "✅ Código corrigido! Recarregue o VS Code." -ForegroundColor Green
```

**Uso:**
```powershell
.\fix_all_code.ps1
```

## ✅ Verificação Final

```bash
# Verificar problemas restantes
docker-compose exec web flake8 . --exclude=migrations,staticfiles,media,.venv

# Django check
docker-compose exec web python manage.py check --deploy

# Contar linhas de código formatadas
docker-compose exec web bash -c "find . -name '*.py' -not -path '*/migrations/*' | xargs wc -l"
```

## 📋 Checklist de Código Limpo

- [ ] Sem imports não utilizados
- [ ] Sem imports duplicados  
- [ ] Imports ordenados (stdlib → terceiros → locais)
- [ ] Nenhuma linha > 88 caracteres
- [ ] Sem trailing whitespace
- [ ] 2 linhas em branco entre funções de nível superior
- [ ] 1 linha em branco entre métodos de classe
- [ ] Código formatado com Black
- [ ] Sem warnings do Pylance
- [ ] `manage.py check` passa sem erros

## 🎯 Resultado Esperado

**Antes:** 3.838 problemas  
**Depois:** 0 problemas  

---

**Última atualização:** 01/03/2026  
**Padrão:** Black + isort + autoflake + autopep8
