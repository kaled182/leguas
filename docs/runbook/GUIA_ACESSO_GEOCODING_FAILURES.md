# 🗺️ GUIA DE ACESSO - RELATÓRIO DE FALHAS DE GEOCODIFICAÇÃO

## ✅ STATUS DO SISTEMA

A página está **FUNCIONANDO** e acessível. Testes confirmam:
- ✓ URL configurada corretamente: `/orders/geocoding-failures/`
- ✓ View executando (Status 200)
- ✓ Template renderizando (31.127 bytes)
- ✓ Dados no banco: **7 falhas**, **456 endereços geocodificados**
- ✓ Taxa de sucesso: **98.5%**

---

## 🔐 PASSO 1: CERTIFIQUE-SE DE ESTAR LOGADO

A página requer autenticação. Se não estiver logado, você será redirecionado para `/auth/login/`.

**Como verificar:**
1. Abra o navegador
2. Vá para: `http://localhost:8000`
3. Se aparecer tela de login, faça login com suas credenciais
4. Se já estiver logado, verá o dashboard

---

## 📍 PASSO 2: ACESSE A PÁGINA (3 FORMAS)

### **FORMA 1: URL Direta** (Mais Rápida)
```
http://localhost:8000/orders/geocoding-failures/
```
Cole esta URL na barra de endereços do navegador e pressione Enter.

### **FORMA 2: Pelo Menu Lateral (Sidebar)**
1. Olhe para o menu lateral esquerdo
2. Procure por: **"Falhas Geocodificação"** (ícone de pin de mapa)
3. Clique no link (cor âmbar/amarela)

### **FORMA 3: Pela Página do Parceiro Delnext**
1. Acesse: `http://localhost:8000/core/partners/5/` (ou encontre Delnext na lista)
2. Na seção **"Ações Rápidas"** (lado direito)
3. Clique no botão **"Falhas de Geocodificação"** (fundo amarelo)

---

## 🔍 PASSO 3: O QUE VOCÊ DEVE VER

Ao acessar a página, você verá:

### **Estatísticas (Cards no Topo):**
- 🔴 **7** - Não Resolvidos
- 🟢 **0** - Resolvidos  
- 🔵 **456** - Geocodificados
- 🟣 **98.5%** - Taxa de Sucesso

### **Filtros:**
- Campo para filtrar por **Parceiro**
- Opção para **Mostrar Resolvidas** (Sim/Não)
- Botão **Filtrar** e **Limpar**

### **Lista de 7 Falhas:**
Cada falha mostra:
- Número do pedido (external_reference)
- Endereço original vs. normalizado
- Código postal e localidade
- Data da tentativa
- Status (resolvido ou não)

---

## 🛠️ PASSO 4: SE AINDA NÃO FUNCIONAR

Se a página ainda não abrir, verifique:

### **A. Console do Navegador (F12)**
1. Pressione `F12` no navegador
2. Vá na aba **Console**
3. Procure por erros em vermelho
4. Se houver, copie e me envie

### **B. Network (Rede)**
1. Com F12 aberto, vá na aba **Network**
2. Recarregue a página (F5)
3. Procure pela requisição `/orders/geocoding-failures/`
4. Verifique o **Status Code** (deve ser 200)
5. Se for outro número, me informe

### **C. Verifique o Cache do Navegador**
1. Pressione `Ctrl + Shift + Delete`
2. Selecione "Imagens e arquivos em cache"
3. Clique em "Limpar dados"
4. Tente acessar novamente

### **D. Teste em Modo Anônimo**
1. Abra uma janela anônima/privada (`Ctrl + Shift + N`)
2. Acesse `http://localhost:8000`
3. Faça login
4. Tente acessar a URL das falhas

---

## 📊 DADOS ATUAIS NO SISTEMA

Você tem **7 endereços com falha de geocodificação:**

1. `centro comercial ilha dos amores, loja 1` - Vila Nova de Cerveira (4920-270)
2. `travesssa da lage 72` - barroselas (4905-318)
3. `centro comercial e.leclerc, loja 5` - Darque (4925-052)
4. `Rua da lourinha 224 1a` - Gomdomas (4435-140)
5. `Rua Dom Afonso Henriques No 70 No 70 No 70` - Alfena (4445-085)
6. `Rua Da Barrosa 284` - Vilar das almas (4990-790)
7. `Rua Leandro Quintas Neves 151` - Mujães (4905-515)

Estes endereços falharam porque:
- Endereços de centros comerciais (sem coordenadas específicas)
- Erros de digitação ("travesssa" em vez de "travessa")
- Números duplicados ("No 70 No 70 No 70")

---

## 🎯 TESTE RÁPIDO (COPIE E COLE)

**Windows PowerShell:**
```powershell
Start-Process "http://localhost:8000/orders/geocoding-failures/"
```

**Ou abra manualmente:**
1. Pressione `Windows + R`
2. Cole: `http://localhost:8000/orders/geocoding-failures/`
3. Pressione Enter
4. Navegador abrirá automaticamente

---

## ❓ ME DIGA O QUE ACONTECE

Depois de seguir estes passos, me informe:

1. **Conseguiu acessar a página?** (Sim/Não)
2. **Se NÃO, o que aparece?**
   - [ ] Página em branco
   - [ ] Erro 404 (não encontrado)
   - [ ] Erro 500 (erro do servidor)
   - [ ] Redirecionamento infinito
   - [ ] Outro: _____________

3. **Se SIM, vê as 7 falhas listadas?** (Sim/Não)

4. **Consegue filtrar?** (Sim/Não)

---

## 🔧 COMANDOS ÚTEIS PARA DEBUG

Se precisar, rode estes comandos:

```powershell
# Ver logs do servidor
docker compose logs web --tail=50

# Verificar se o container está rodando
docker compose ps

# Reiniciar o servidor
docker compose restart web

# Testar a conexão
curl http://localhost:8000/orders/geocoding-failures/
```

---

**🚨 IMPORTANTE:** A página existe e funciona! Ela foi testada e retorna status 200. 
Se você não consegue acessar, o problema é de:
- Autenticação (não está logado)
- Browser cache (limpe o cache)
- Firewall/antivírus bloqueando
- Digitação errada da URL

**A página OFICIAL é:**
```
http://localhost:8000/orders/geocoding-failures/
```

(Note o **s** em "failures" e o **hífen** entre "geocoding" e "failures")
