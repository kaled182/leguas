# Rede PUDO — Plano do Módulo (Add-on)

> Documento de planeamento **vivo**. Consolida a visão operacional (Paulo), a
> crítica arquitetural e a verificação contra o código real da Léguas. As decisões
> em aberto do rascunho original (Q1, Q4, Q5, numeração, escopo) foram **fechadas**
> nesta revisão. Última revisão: 2026-07-01.

---

## 0. TL;DR — estado atual

- **"PUDO" já existe, mas só metade.** Hoje é uma *regra de remuneração do
  motorista* (Cainiao marca `Delivery Type=PUDO`, pagamos 1ª + (N-1)×adicional,
  deteção de "fake delivery" por distância). **Não existe** loja gerida, portal do
  lojista, custódia, aging, devoluções nem faturação à loja. O módulo novo é essa
  camada em falta. Ver §2.
- **Stack real (verificada):** Django + PostgreSQL, Django Templates + Alpine.js +
  Tailwind (`django-tailwind 3.6.0`), Celery + Redis + Beat. Sem Vue/React/HTMX.
  Máquinas de estado **manuais** (`can_transition_to()` + histórico imutável),
  **sem django-fsm**. API do app do motorista em views Django + JSON com token
  (`@app_token_required`, `app_api/`) — DRF existe mas o app não o usa.
- **~40% da engenharia difícil já está feita:** pagamento ao motorista, bigbags,
  OTP, auditoria, crons, API por token.

### Decisões fechadas nesta revisão
- **Escopo desta fase de construção:** entregar **todo o lado WEB do PUDO 100%
  pronto** (admin, portal do lojista, custódia, POD, faturação, dashboard). A **app
  Android do estafeta NÃO é construída** — deixa-se **preparada e documentada**:
  os endpoints da API (backend, construído aqui) + documentação (OpenAPI + Postman,
  como em `docs/api`). O frontend móvel fica planeado, para quem o construir depois.
- **Q4 — App novo `pudo_network`** (não estender o `sorting`).
- **Identidade por numeração:** cada PUDO tem `numero` sequencial automático
  (`PUDO-0001`, imutável após criação). É a chave de negócio — aparece em
  etiquetas, bigbags, QR do handshake e faturas. O `nome` é apenas descritivo.
- **Q3 — Pivô do pacote:** camada de ligação genérica (carrier-agnostic), não
  amarrada a `CainiaoOperationTask`.
- **Q2 — POD híbrido:** OTP + NIF/CC conforme o caso, desenho preparado para
  evoluir.
- **Q1 — Reconciliação a montante:** largar no PUDO **já conta como delivered**
  para a Cainiao; o **levantamento pelo cliente é interno**; só **devoluções/não
  levantados** precisam de callback a montante. Hook modelado desde já, **ativado
  na Fase 2**.
- **Q5 — App do estafeta:** offline com **redundância** (driver e PUDO podem ambos
  atualizar a mesma custódia; servidor reconcilia por UUID). Scanner = câmara do
  telemóvel; no balcão web usa-se **leitor de código de barras tipo teclado**.
  Armazenamento mantém a estrutura padrão do projeto. Publicação por **APK direto**
  (futuro). Nada disto bloqueia as Fases 0-3 — só a Fase 4.

---

## 1. O que já existe hoje (base factual, verificada)

| Peça | Onde | Reuso |
|---|---|---|
| PUDO billing (motorista) | `settlements/services_pudo.py` (`pudo_key:79`, `compute_pudo_payment:116`, `find_fake_delivery_suspects:164`), `core/models.py:92` (`pudo_*`), `settlements/models.py:1723` (`PreInvoicePudo`) | Pagamento ao motorista **já resolvido**. Não reimplementar. |
| Sorting em bigbags | `sorting/models.py` (`SortingSession:12`, `SortingBigbag:63`, `SortingParcel:104`), `sorting/services.py` | Base do "assinar bigbag ao PUDO". |
| Acessos externos + OTP | `customauth/models.py` (`EmpresaAccess:182`, `DriverAccess:17`, `DriverLoginOTP:133`), `customauth/empresa_auth_views.py` | Molde de `PudoAccess` + login do lojista. |
| Entidade parceira | `drivers_app/models.py:9` (`EmpresaParceira`) | Molde do `PudoStore`. |
| Pacote + POD + incidentes | `orders_manager/models.py` (`Order:9`, `OrderStatusHistory:241`, `OrderIncident:290`) | Padrão de POD, histórico e incidentes. |
| EPOD Cainiao | `settlements/models.py` (`CainiaoOperationTask`) | Fonte "isto é PUDO" + coordenadas. |
| Auditoria imutável | `settlements/models.py:2932` (`PreInvoiceAuditLog`), `OrderStatusHistory` | Molde do `PudoCustodyEvent`. |
| Celery + Beat | `my_project/celery.py` | Aging, notificações, auto-faturação. |
| API do app | `app_api/views.py`, `app_api/auth.py` (`app_token_required:52`) | Estilo dos endpoints de handshake. |
| Faturação (padrão) | `settlements/models.py` (`DriverPreInvoice`, `PartnerInvoice`), `settlements/services.py` | Molde do extrato da loja. |

---

## 2. PUDO v1 vs Rede PUDO (resolver a colisão de nomes)

- **PUDO v1 (existe):** classificação de uma entrega Cainiao → **paga o motorista**.
- **Rede PUDO (novo):** o ponto é um **parceiro nosso**, com contrato, portal,
  custódia, prazo e a quem **pagamos por pacote entregue ao cliente**.

Dois pagamentos sobre o mesmo pacote: `motorista` (v1, feito) **e** `loja` (novo).
Naming: manter `pudo_*` no `Partner` para v1; usar app/namespace **`pudo_network`**
e prefixo `PudoStore*` para a rede.

---

## 3. Correções de arquitetura (confirmadas no código)

1. **Portal = Django Templates + Alpine + Tailwind**, herdando o base do dashboard.
   Sem Vue/HTMX.
2. **Máquina de estados manual** (`can_transition_to()` / `available_transitions()`,
   ver `settlements/models.py:379`) + histórico imutável. Sem django-fsm.
3. **Online-first no MVP com redundância.** A custódia é fonte-de-verdade online;
   driver e PUDO podem ambos atualizar → **reconciliação idempotente por UUID**.
   Offline real (fila local + QR assinado com nonce+TTL+uso-único) fica para a
   Fase 4.
4. **Faturação = ledger imutável, não recontagem** (padrão `PreInvoicePudo` +
   audit log). Extrato lê o ledger.
5. **RGPD:** mascarar NIF/CC na UI, nunca guardar foto de documento; cláusula de
   subcontratação no contrato (fora do código) + retenção do POD.
6. **Capacidade a 100% não encrava o hub:** regra de *overflow* (reencaminhar).

---

## 4. Máquina de estados de custódia

```
ATRIBUIDO_HUB      sorting associou o pacote à bigbag daquele PUDO
   → EM_TRANSITO       (estafeta assina a saca à rota)
   → EM_STOCK_PUDO     (handshake QR concluído)
        ↳ notificação ao cliente + arranca relógio de aging
        ↳ NÃO marca "entregue" a montante
   → ENTREGUE_CLIENTE  (POD: OTP ou NIF validado)         [terminal feliz]
        ↳ LINHA DE FATURAÇÃO À LOJA (imutável)
        ↳ reconciliação a montante (levantamento = interno; ver §0/Q1)
   → EXPIRADO          (cron de aging ultrapassa SLA)
        ↳ alerta no dashboard do PUDO
   → AGUARDA_DEVOLUCAO (hub/PUDO marca retorno, com motivo)
   → EM_DEVOLUCAO      (handshake reverso estafeta↔PUDO)
   → DEVOLVIDO_HUB     (receção conferida no hub)          [terminal]
        ↳ callback de devolução a montante (Fase 2)

DIVERGENCIA   exceção acessível de EM_STOCK_PUDO e DEVOLVIDO_HUB (falta/sobra).
              Nunca terminal: força resolução humana.
```

---

## 5. Modelo de dados (app `pudo_network`)

- **`PudoStore`** — molde `EmpresaParceira`. `numero` (sequencial `PUDO-0001`,
  unique, imutável — **identidade**), `nome` (descritivo), `morada, cp, cidade,
  lat, lng, nif, iban, taxa_iva, email, telefone, contacto_nome,
  status (ATIVO/PAUSADO/INATIVO), capacidade_max (int), horario (JSON),
  preco_1a_entrega, preco_adicional, ciclo_pagamento (SEMANAL/MENSAL),
  partner (FK core.Partner, null → carrier-agnostic §7), created_at/updated_at`.
- **`PudoAccess`** — molde `EmpresaAccess`. `store OneToOne, username unique,
  password (hash), email, is_active, last_login, papel (DONO/ATENDENTE),
  created_by, timestamps`, com `set_password`/`check_password`.
- **`PudoCustodyPackage`** (Fase 1) — pacote sob custódia. `status (§4),
  store (FK), driver (FK DriverProfile), bigbag (FK sorting.SortingBigbag, null),
  ref genérica ao pacote (carrier-agnostic), localizacao_prateleira (opcional),
  received_at, aging_deadline, delivered_at`.
- **`PudoTransaction`** (Fase 1) — handshake. `uuid (unique), tipo
  (ENTREGA/DEVOLUCAO), store, driver, status, created_at_device, synced_at`.
  **Idempotência pela `uuid`** (reenvio devolve o mesmo estado).
- **`PudoCustodyEvent`** (Fase 1) — histórico append-only. Molde `OrderStatusHistory`.
- **`PudoDeliveryProof`** (Fase 2) — POD. `metodo (OTP/NIF/TERCEIRO),
  levantador_nome, doc_mascarado, otp_ok, assinatura (opcional)`. Nunca foto.
- **`PudoStoreBillingLine`** (Fase 3) — ledger imutável, emitido no POD.

**Extensão `sorting.SortingBigbag`:** `pudo_store (FK, null)` + `consumida (bool)`.
Migração aditiva no app `sorting` (campos nullable, sem risco de dados).

---

## 6. Plano faseado

- **Fase 0 — Fundações (WEB):** app `pudo_network`, `PudoStore` (+ `numero`) + admin
  CRUD, `PudoAccess` + login do lojista (molde `EmpresaAccess`), extensão da bigbag.
  Migrações escritas, **não aplicadas no Docker** sem confirmação.
- **Fase 1 — Custódia online + handshake (WEB + API) — FEITA:** `PudoCustodyPackage`
  (máquina §4 manual), `PudoTransaction` (uuid idempotente, reconciliação
  driver↔PUDO por `store`+`tracking_ref`), `PudoCustodyEvent` (append-only),
  service `process_handshake`, endpoint `POST /api/app/v1/pudo/handshake`
  (`pudo_network/api.py`, token `app_token_required`), receção no portal do lojista
  (`/pudo/rececao/`, leitor de barras/câmara via Alpine), gancho de notificação ao
  cliente (`notifications.py`, best-effort WhatsApp). Documentado em
  `docs/api/PUDO_HANDSHAKE.md`. Migração `pudo_network/0002`, **por aplicar**.
- **Fase 2 — POD + aging + devoluções — FEITA:** `PudoDeliveryProof` (OTP via
  `PudoPickupOTP` + NIF/CC mascarado, RGPD, sem foto), task Celery
  `pudo_network.mark_expired` + management command `pudo_mark_expired` + entrada no
  Beat (07:30), devoluções com motivo (`AGUARDA_DEVOLUCAO`→`EM_DEVOLUCAO`→
  `DEVOLVIDO_HUB`), `DIVERGENCIA`, e callback de devolução a montante enfileirado
  em `PudoUpstreamReconciliation` (envio real por definir — Q1). Portal: `/pudo/stock/`,
  `/pudo/pacote/<id>/` (POD), ações via Alpine.
- **Fase 3 — Faturação à loja + dashboard — FEITA:** `PudoStoreBillingLine` (ledger
  IMUTÁVEL, emitido no POD por `_emit_billing_line`, `save()` bloqueia updates),
  extrato do lojista `/pudo/extrato/` (lê o ledger, só papel DONO), dashboard com
  ganhos/ocupação/ações. **Faturação FLAT por pacote** (decidido): cada entrega =
  `preco_1a_entrega`, sem lógica 1ª+adicionais. Auto-emissão periódica de extratos
  (`PudoStoreStatement`) via task `pudo_network.emit_statements` (Beat 06:40),
  fechando o mês anterior (dia 1) ou a semana anterior (segunda) conforme o
  `ciclo_pagamento` da loja; snapshot imutável que congela e linka as linhas.
- **Reconciliação a montante (devoluções) — infra FEITA:** fila
  `PudoUpstreamReconciliation` + task `pudo_network.process_upstream` (Beat 07:40)
  que compõe e persiste o payload de cada devolução. O envio real (`_send_upstream`)
  fica por ligar até o spec do carrier estar fechado (Q1) — registos ficam PENDENTE
  com o payload pronto.
- **Fase 4 — Offline-first do estafeta — FEITA (backend + protocolo):** fila offline
  com sync em lote idempotente (`POST /api/app/v1/pudo/sync`), QR assinado
  HMAC-SHA256 com **nonce + TTL curto (≤300 s) + uso-único** validado no servidor
  (`PudoDeviceKey`, `PudoHandshakeNonce`, `process_signed_handshake`), endpoints
  `device-key`/`handshake-signed`/`sync` e receção offline no portal do lojista
  (`/pudo/rececao-offline/`). Contrato em `docs/api/PUDO_OFFLINE.md`. A app Android
  (APK) que consome isto fica por construir — só documentada.

---

## 7. Reframe estratégico — carrier-agnostic

Modelar `PudoStore` e o pricing carrier-agnostic desde o dia 1 (pacote pode
originar de qualquer `Partner`). `PudoStore.partner` é FK nullable e a custódia
liga a um pacote genérico. Torna a rede um ativo B2B vendável a outros carriers.
