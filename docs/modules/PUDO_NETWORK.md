# Rede PUDO — Referência do Módulo (`pudo_network`)

Documentação operacional e técnica do módulo **Rede PUDO**: lojas de recolha
geridas pela Léguas (custódia de pacotes, portal do lojista, POD, faturação à
loja e handshake com a app do estafeta).

- **Plano/decisões:** `docs/modules/PUDO_NETWORK_PLAN.md`
- **Guia para a app do estafeta:** `docs/api/PUDO_APP_GUIDE.md`
- **Contratos de API:** `docs/api/PUDO_HANDSHAKE.md`, `docs/api/PUDO_OFFLINE.md`
- **Coleção Postman:** `docs/api/leguas-pudo.postman_collection.json`

> Nos exemplos, `{HOST}` é o host servido pelo Caddy — em produção tipicamente
> `http://89.153.26.181:8090` (ou o `DOMAIN` configurado). Ajuste conforme o `.env`.

---

## 1. Como aceder

### 1.1 Portal do lojista (PUDO) — sessão própria
Login fora do `User` Django (molde `EmpresaAccess`). Papéis: **DONO** (vê
financeiro) e **ATENDENTE** (só operação).

| Página | URL | Papel | Função |
|---|---|---|---|
| Login | `{HOST}/pudo/login/` | — | Entrar com username + password |
| Dashboard | `{HOST}/pudo/` | ambos | KPIs: em stock, ocupação, ações; ganhos do mês (só DONO) |
| Receção | `{HOST}/pudo/rececao/` | ambos | Ler códigos (leitor de barras = teclado, ou câmara) |
| Receção offline | `{HOST}/pudo/rececao-offline/` | ambos | Ler QR **assinado** gerado offline pelo estafeta |
| Stock | `{HOST}/pudo/stock/` | ambos | Pacotes prontos para levantamento |
| POD / pacote | `{HOST}/pudo/pacote/<id>/` | ambos | Entregar ao cliente (OTP/NIF) ou marcar devolução |
| Extrato | `{HOST}/pudo/extrato/` | **DONO** | Ledger de faturação à loja + totais por período |
| Logout | `{HOST}/pudo/logout/` | — | Terminar sessão |

### 1.2 Admin Django (staff) — gestão central
`{HOST}/admin/pudo_network/…`

| Modelo | URL admin | Uso |
|---|---|---|
| PUDOs (Rede) | `…/pudostore/` | Criar/editar lojas, preços, capacidade, estado |
| Acessos de PUDO | `…/pudoaccess/` | Credenciais do lojista + ação "definir password" |
| Pacotes em custódia | `…/pudocustodypackage/` | Estado, aging, histórico (inline de eventos) |
| Transações (handshake) | `…/pudotransaction/` | Auditoria de handshakes (uuid) |
| Eventos de custódia | `…/pudocustodyevent/` | Histórico append-only (só leitura) |
| Provas de entrega (POD) | `…/pudodeliveryproof/` | POD por OTP/NIF (só leitura) |
| Faturação à loja | `…/pudostorebillingline/` | Ledger imutável (só leitura) |
| Extratos periódicos | `…/pudostorestatement/` | Snapshots de fecho (só leitura) |
| Reconciliação a montante | `…/pudoupstreamreconciliation/` | Fila de devoluções ao carrier |
| Chaves de dispositivo | `…/pudodevicekey/` | Segredos de assinatura offline |
| Nonces de handshake | `…/pudohandshakenonce/` | Anti-replay (só leitura) |

### 1.3 API da app do estafeta (token Bearer)
`{HOST}/api/app/v1/pudo/…` — ver §4 e o guia da app.

---

## 2. Criar um PUDO e dar acesso ao lojista (passo a passo)

1. **Admin → PUDOs (Rede) → Adicionar.** Preencher nome (descritivo), morada,
   NIF/IBAN, `capacidade_max`, `preco_1a_entrega`, `ciclo_pagamento`. O **número**
   (`PUDO-0001`) é gerado automaticamente e é a identidade da loja.
2. No mesmo formulário, secção **Acessos de PUDO** (inline): criar um acesso com
   `username`, `papel` (DONO/ATENDENTE). Ao gravar sem password, é gerada uma
   password inicial mostrada uma vez (ou usar a ação "definir password aleatória").
3. Entregar credenciais ao lojista → ele entra em `{HOST}/pudo/login/`.

---

## 3. Fluxo operacional (ciclo de vida do pacote)

```
ATRIBUIDO_HUB → EM_TRANSITO → EM_STOCK_PUDO → ENTREGUE_CLIENTE   (caminho feliz)
                                   │
                                   ├─ EXPIRADO (aging)
                                   └─ AGUARDA_DEVOLUCAO → EM_DEVOLUCAO → DEVOLVIDO_HUB
DIVERGENCIA = exceção (falta/sobra), nunca terminal.
```

1. **Sorting → bigbag assinada ao PUDO** (`sorting.SortingBigbag.pudo_store`).
2. **Handshake / receção:** estafeta (app) ou lojista (portal) regista a entrega →
   pacote fica `EM_STOCK_PUDO`, arranca o **aging** (prazo de levantamento, 7 dias
   por defeito) e o cliente é notificado (WhatsApp, se houver telefone).
3. **POD (levantamento):** no `/pudo/pacote/<id>/`, entregar por **OTP** (código
   WhatsApp ao cliente) ou **NIF/CC** (gravado mascarado, RGPD). Ao entregar,
   emite-se uma **linha de faturação imutável** à loja.
4. **Aging:** a task `pudo_network.mark_expired` passa a `EXPIRADO` os que passam
   do prazo.
5. **Devolução:** marcar com motivo → handshake reverso → receção no hub
   (`DEVOLVIDO_HUB`) → enfileira reconciliação a montante.
6. **Faturação:** o extrato lê o ledger; fecho periódico via
   `pudo_network.emit_statements` conforme o `ciclo_pagamento`.

---

## 4. Endpoints da API (resumo)

Base: `{HOST}/api/app/v1/pudo/` — auth Bearer (mesmo token da app do motorista).

| Método | Rota | Função |
|---|---|---|
| POST | `handshake` | Handshake online (idempotente por `uuid`) |
| POST | `handshake-signed` | Handshake **offline assinado** (nonce+TTL+uso-único) |
| GET/POST | `device-key` | Emite/roda o segredo de assinatura offline |
| POST | `sync` | Drena a fila offline (lote de handshakes) |

Detalhe completo (payloads, respostas, erros) em `docs/api/PUDO_APP_GUIDE.md`.

---

## 5. Modelos de dados

| Modelo | Papel |
|---|---|
| `PudoStore` | A loja. Identidade `numero` (`PUDO-0001`), preços, capacidade, ciclo, carrier-agnostic (`partner` nullable) |
| `PudoAccess` | Login do lojista (papéis DONO/ATENDENTE) |
| `PudoCustodyPackage` | Pacote sob custódia + máquina de estados manual |
| `PudoTransaction` | Handshake (âncora de idempotência por `uuid`) |
| `PudoCustodyEvent` | Histórico append-only das transições |
| `PudoPickupOTP` | OTP de levantamento (molde `DriverLoginOTP`) |
| `PudoDeliveryProof` | POD (OTP/NIF mascarado/terceiro) |
| `PudoUpstreamReconciliation` | Fila de devolução a montante (payload pronto) |
| `PudoStoreBillingLine` | Ledger **imutável** de faturação à loja (emitido no POD) |
| `PudoStoreStatement` | Snapshot periódico (fecho) do extrato |
| `PudoDeviceKey` | Segredo HMAC por estafeta (assinatura offline) |
| `PudoHandshakeNonce` | Nonce uso-único (anti-replay) |

Extensão em `sorting.SortingBigbag`: `pudo_store` (FK) + `consumida` (bool).

---

## 6. Tarefas agendadas (Celery Beat)

| Task | Horário | Função |
|---|---|---|
| `pudo_network.emit_statements` | 06:40 | Fecha extratos: mês anterior (dia 1) / semana anterior (segunda) |
| `pudo_network.mark_expired` | 07:30 | Aging → `EXPIRADO` os pacotes fora do prazo |
| `pudo_network.process_upstream` | 07:40 | Prepara/drena a fila de devoluções a montante |

Comandos manuais equivalentes: `manage.py pudo_mark_expired`,
`pudo_emit_statements`, `pudo_process_upstream`.

---

## 7. Configuração e regras de negócio

- **Faturação à loja = flat por pacote** (`PudoStore.preco_1a_entrega` por entrega).
- **Aging default:** 7 dias (`DEFAULT_AGING_DAYS` em `models.py`).
- **TTL do QR offline:** ≤ 300 s (`SIGNED_QR_MAX_TTL` em `services.py`).
- **RGPD:** NIF/CC gravado sempre **mascarado**; **nunca** foto de documento.
- **Devolução a montante (Q1):** o envio real ao carrier aguarda o spec; a fila
  compõe e guarda o payload (estado `PENDENTE`).

---

## 8. Deploy

Aplicar no servidor de produção com `production/update.sh` (backup → pull →
rebuild → `migrate` → recreate web+celery). Migrações: `pudo_network/0001–0005`
+ `sorting/0003` (aditivas). Detalhe e verificação pós-deploy no runbook de deploy.
