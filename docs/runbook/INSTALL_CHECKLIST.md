# UAT — Install From Zero Checklist

Checklist para validar que um utilizador pode instalar e operar o sistema **do zero** sem assistência. Cada item tem um critério de sucesso objectivo.

> Tempo estimado: **45-60 min** (depende da rede e especialmente do build inicial Docker)

---

## Fase 1 — Máquina limpa (5 min)

### Opção A — Host fresh sem nada instalado

Corre o bootstrap (instala Docker, Compose v2 e git automaticamente):

```bash
curl -fsSL https://raw.githubusercontent.com/kaled182/leguas/main/production/bootstrap.sh | bash
```

- [ ] Output termina com `✓ Pré-requisitos instalados`
- [ ] **Logout + login** (para o user entrar no grupo docker)
- [ ] `docker info` sem `sudo` responde sem erro

### Opção B — Já tens Docker

Verifica:

- [ ] **Docker Engine** instalado (`docker --version` ≥ 20.10)
- [ ] **Docker Compose v2** (`docker compose version` ≥ 2.0)
- [ ] **Git** (`git --version`)

### Em ambos casos

- [ ] Pelo menos **4 GB RAM livre** + **10 GB disco**
- [ ] Portas livres: **80, 443** (Caddy), **3306** opcional (DB)
- [ ] Ligação à internet (para puxar imagens Docker e clonar repo)

**Critério**: `docker info` responde sem `sudo`, `docker compose version` mostra ≥ 2.0.

---

## Fase 2 — Clone + install wizard (10 min)

```bash
git clone https://github.com/kaled182/leguas.git
cd leguas/production
chmod +x install.sh
./install.sh
```

O wizard pergunta:
- [ ] **Domínio** (deixa em branco para HTTP-only no IP, ou preenche para HTTPS automático)
- [ ] **Email Let's Encrypt** (se domínio preenchido)
- [ ] **Username admin** (default: `admin`)
- [ ] **Password admin** (mínimo 8 caracteres)
- [ ] **Email admin**

O script gera automaticamente:
- [ ] `SECRET_KEY` (50 chars)
- [ ] `DB_PASSWORD`, `DB_ROOT_PASSWORD` (24 hex)
- [ ] `WPPCONNECT_SECRET` (32 hex)
- [ ] **`UPDATER_SECRET` (32 hex)** ← crítico para o auto-update
- [ ] `FERNET_KEY` (Fernet)
- [ ] `BACKUP_ZIP_PASSWORD` (16 hex)

**Critério**:
- `production/.env` criado com todas as variáveis preenchidas
- Mensagem `✓ Instalação concluída`
- `docker compose ps` mostra ≥ 6 serviços (db, redis, web, celery_worker, celery_beat, caddy, updater, wppconnect) com STATUS `healthy` ou `running`

---

## Fase 3 — Health checks iniciais (5 min)

```bash
# Containers todos UP
docker compose ps

# Health endpoint do web
curl -sS http://localhost/health/

# Updater operacional (não exposto, só na rede interna)
docker compose exec updater wget -qO- http://localhost:9999/health
```

- [ ] `/health/` devolve 200
- [ ] Caddy (`http://localhost/`) redireciona para login Django
- [ ] Updater responde "OK" no health
- [ ] **Sem `unhealthy` em** `docker compose ps`

**Critério**: todos verdes.

---

## Fase 4 — Primeiro login admin (5 min)

- [ ] Abre `http://localhost/` (ou `https://<domínio>/`) no browser
- [ ] É redirecionado para a página de login
- [ ] Faz login com username/password do admin criado no install
- [ ] Vê o dashboard principal sem erros 500
- [ ] **Configurações → Empresa**: preenche Nome, NIF, Morada, Logo, guarda
- [ ] **Configurações → Mapas**: escolhe provedor (Google/Mapbox/OSM), guarda
- [ ] **Configurações → Atualização → Configurar GitHub**: cola URL `https://github.com/kaled182/leguas` e branch `main`. (Token só se for repo privado)
- [ ] Clica **Verificar atualizações** — deve aparecer "Sistema actualizado" ou lista de commits

**Critério**: nenhum 500 no dashboard, configurações guardadas (refresh confirma persistência).

---

## Fase 5 — Criar primeiro motorista (10 min)

### 5.1 — Cadastro pelo admin

- [ ] **Sidebar → Motoristas → Aprovar Cadastros** (ou Central de Motoristas)
- [ ] Botão **Criar Motorista** → preenche nome, NIF, telefone, email
- [ ] Aprova
- [ ] Volta à **Central de Motoristas** (`/driversapp/admin/`) e o motorista aparece na lista

### 5.2 — Configurar credenciais (DriverAccess)

- [ ] Abre o portal do motorista (`/driversapp/portal/<id>/`)
- [ ] Clica em **Logins** (separador admin)
- [ ] Cria credencial: `username` + `password`
- [ ] Guarda

### 5.3 — Driver autentica-se

- [ ] Abre `/auth/driver/` numa janela anónima
- [ ] Faz login com as credenciais criadas
- [ ] É redirecionado para `/driversapp/portal/<id>/` (o seu próprio)
- [ ] Vê apenas as tabs do driver (Visão Geral, Relatórios, Faturas, Perfil, Contratos) — **sem sidebar admin**
- [ ] KPIs estão a 0 (não há entregas ainda)

**Critério**: driver autentica e vê só o seu portal.

---

## Fase 6 — Operação real (10 min)

### 6.1 — Importar dados Cainiao (se aplicável)

- [ ] **Sidebar → Operações → Importar XLSX** (ou via Cainiao integration)
- [ ] Carrega ficheiro `_EPOD_TASK_LIST_V2_*.xlsx` válido
- [ ] Mensagem `N pacotes importados`
- [ ] **Dashboard principal** mostra os pacotes do dia

### 6.2 — Driver vê os seus pacotes

- [ ] Login como driver
- [ ] **Visão Geral**: KPI HOJE / SEMANA / MÊS reflete os pacotes
- [ ] **Heatmap anual**: pelo menos um quadrado verde no dia de hoje
- [ ] Lista **Pacotes do mês** mostra os waybills
- [ ] Clica num waybill → abre a página de "vida do pacote"

**Critério**: KPIs do driver coincidem com os do dashboard admin para o mesmo período.

---

## Fase 7 — Fluxo financeiro completo (10 min)

> Este é o teste mais importante — toca em todas as peças novas.

### 7.1 — Emitir Pré-Fatura

Como **admin**:
- [ ] Abre o portal do motorista → tab **Faturas**
- [ ] Define período (ex: mês actual)
- [ ] Botão **Emitir Pré-Fatura** → confirma
- [ ] Aparece nova PF com número, base, total

### 7.2 — Driver anexa fatura-recibo

Como **driver** (logout admin, login driver):
- [ ] Abre **Faturas** → vê a PF emitida
- [ ] Estado mostra **"Pendente"** na coluna Recibo
- [ ] Clica no ícone **paperclip** → escolhe um PDF/JPG
- [ ] Toast: `Recibo anexado · Pagamento pode ser libertado`
- [ ] Estado muda para **"Anexado"** (badge verde)

### 7.3 — Admin marca como pago

Como **admin**:
- [ ] **Sidebar → Financeiro → A Pagar** (`/accounting/a-pagar/`)
- [ ] A PF aparece na lista, badge verde com estado **APROVADO** ou **PENDENTE**, botão **Pagar** habilitado
- [ ] Clica **Pagar** → preenche data + referência + (opcional) comprovativo → confirma
- [ ] Toast: `<numero> marcada como paga`
- [ ] PF desaparece de "A Pagar" (está pago, não está em aberto)

### 7.4 — Verificação cruzada (refresh tudo)

- [ ] **Driver** abre Faturas → PF mostra **"Pago"** (badge verde)
- [ ] **Admin → Análise → Dashboard** reflete o pagamento no KPI
- [ ] **Análise → DRE** mostra a despesa no mês

### 7.5 — Bloqueio sem recibo (regra crítica)

- [ ] Cria outra PF em rascunho (sem recibo)
- [ ] Em A Pagar, o botão **Pagar** está **desactivado** com tooltip "Aguarda recibo"
- [ ] Tenta forçar via DevTools (POST direto) → resposta 400 `PF sem fatura-recibo. Não pode ser paga.`

**Critério**: tudo passa, especialmente 7.5 (bloqueio duro).

---

## Fase 8 — Auto-update do GitHub (10 min)

> O teste mais arriscado — fá-lo com o sistema sem tráfego ativo.

### 8.1 — Verificação

- [ ] **Configurações → Atualização**
- [ ] **Verificar atualizações** → mostra:
  - "Sistema actualizado" (se nada mudou) **OU**
  - Lista de commits pendentes com SHAs e mensagens

### 8.2 — Trigger update

> Cria primeiro um commit trivial no GitHub (ex: editar um comentário no `README.md` e dar push) para teres algo a aplicar.

- [ ] Volta a clicar **Verificar atualizações** — agora mostra 1+ commits pendentes
- [ ] Clica **Atualizar agora** → confirma no modal
- [ ] Aparece painel de progresso com spinner
- [ ] Steps esperados (em ordem):
  1. `git fetch origin main` ✓
  2. `git reset --hard origin/main` ✓
  3. `docker compose build web` ✓ (~30-90s)
  4. `docker compose up -d --force-recreate web celery_worker celery_beat` ✓
- [ ] Web container reinicia (página pode pestanejar)
- [ ] **Toast** "Atualização concluída" aparece após reload automático
- [ ] **Verificar atualizações** novamente → "Sistema actualizado"

### 8.3 — Smoke pós-update

- [ ] Login admin continua a funcionar
- [ ] Driver portal continua a funcionar
- [ ] Dados não se perderam (PFs, motoristas, comentários)

**Critério**: update aplicado sem perda de dados, sistema serve tráfego < 60s após o reset.

**Se falhar**:
- Verifica `docker logs leguas_updater` (último step)
- Recovery manual:
  ```bash
  cd /caminho/para/leguas
  docker compose -p appleguasfranzinaspt -f production/docker-compose.yml up -d --no-deps --force-recreate web
  ```

---

## Fase 9 — Backup & restore (5 min)

- [ ] **Configurações → Backup → Criar backup** → completa < 30s
- [ ] Aparece em `production/backups/db_<timestamp>.sql.gz`
- [ ] Tenta restore num container de teste (ou apenas confirma o ficheiro existe e tem > 1KB)
- [ ] Cron de backup automático activo: `docker compose exec celery_beat celery -A my_project inspect scheduled` mostra a tarefa

---

## Fase 10 — Mobile / responsive (5 min)

Abre num telemóvel (ou DevTools mobile mode 375×667):

- [ ] **`/`** dashboard principal — sidebar collapse, KPIs em coluna
- [ ] **`/driversapp/portal/<id>/`** — tabs scrolláveis horizontalmente, cards empilhados
- [ ] **`/accounting/a-pagar/`** — tabela faz overflow-x sem cortar
- [ ] **`/system/atualizacao/`** — botões empilham verticalmente
- [ ] Modais (Anexar recibo, Pagar) cabem na viewport sem scroll horizontal

**Critério**: nada cortado, nenhum botão inacessível.

---

## ✓ Sistema validado para produção

Se todos os items acima forem ✓:

1. **Backup baseline**: `production/backup.sh` — guarda `.env`, DB, media num local seguro
2. **Documentar passwords**: SECRET_KEY, DB_PASSWORD, UPDATER_SECRET — guardar em password manager
3. **Configurar monitoring** (opcional): `docker compose ps` + healthchecks
4. **Notificar utilizadores** que o sistema está pronto

---

## Sinais de alerta — NÃO disponibilizar se:

- ❌ Algum container `unhealthy` persistente (> 5 min)
- ❌ Fase 7.5 (bloqueio de PF sem recibo) falhou
- ❌ Auto-update na Fase 8 falhou e exigiu recovery manual
- ❌ Driver consegue ver dados de outro driver (segurança)
- ❌ Logs do web mostram tracebacks 500 frequentes durante o UAT

---

## Comandos úteis para troubleshooting

```bash
# Logs em tempo real
docker compose -p appleguasfranzinaspt -f production/docker-compose.yml logs -f web

# Status dos containers
docker compose -p appleguasfranzinaspt -f production/docker-compose.yml ps

# Migration manual (se entrypoint falhar)
docker compose exec web python manage.py migrate

# Criar superuser manual
docker compose exec web python manage.py createsuperuser

# Reset de password admin
docker compose exec web python manage.py changepassword <user>

# Rebuild completo (último recurso)
docker compose -p appleguasfranzinaspt -f production/docker-compose.yml up -d --build --force-recreate
```
