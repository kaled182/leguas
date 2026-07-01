# Rede PUDO — Plano do Módulo (Add-on)

> Documento de planeamento. Consolida a visão operacional discutida com o Paulo,
> a crítica arquitetural e — o mais importante — **verifica tudo contra o código
> real da Léguas** para o módulo nascer como add-on nativo e não como sistema
> paralelo. Última revisão: 2026-07-01.

---

## 0. TL;DR — o que muda face ao plano inicial

O escopo operacional (handshake por QR, custódia, logística reversa, dashboard do
lojista) está maduro. Mas ao conferir o repositório, três coisas mudam o rumo:

1. **"PUDO" já existe no sistema — mas só metade.** Hoje PUDO é uma *regra de
   remuneração do motorista* (Cainiao marca `Delivery Type=PUDO`, pagamos 1ª +
   (N-1)×adicional, e detetamos "fake delivery" por distância). **Não existe**
   entidade de loja, portal do lojista, custódia, aging, devoluções nem
   faturação à loja. O novo módulo é exatamente essa **camada que falta**: a
   rede física de PUDOs geridos. Ver §2.
2. **A stack que o Gemini assumiu está errada.** Não é Vue SPA. É **Django
   Templates + Alpine.js + Tailwind CSS 4**, sem HTMX, sem React/Vue. E
   **não usamos django-fsm** — as máquinas de estado são manuais
   (`can_transition_to()` + modelos de histórico). Ver §3.
3. **A minha própria preocupação com "reconciliação a montante" precisa de ser
   suavizada.** Para a Cainiao, largar no PUDO **já é** a entrega (é o que
   dispara o pagamento hoje). O evento de *levantamento pelo cliente* é
   provavelmente interno. O que de facto precisa de voltar a montante são as
   **devoluções/não-levantados**. Fica como pergunta em aberto (§8, Q1).

---

## 1. O que já existe hoje (base factual, com caminhos)

| Peça | Onde | O que faz | Reuso para a Rede PUDO |
|---|---|---|---|
| **PUDO billing (motorista)** | `core/models.py:91-138` (campos `pudo_*` no `Partner`), `settlements/services_pudo.py`, `settlements/views_pudo.py`, `settlements/models.py:1723` (`PreInvoicePudo`) | Preço 1ª+adicional, `pudo_key()`, `compute_pudo_payment()`, `find_fake_delivery_suspects()` (haversine), breakdown na pré-fatura do motorista | **Pagamento ao motorista já resolvido.** Reutilizar tal e qual. A faturação **à loja** é nova e separada. |
| **Sorting em bigbags virtuais** | `sorting/models.py` (`SortingSession`, `SortingBigbag`, `SortingParcel`), `sorting/services.py` (`scan_parcel`) | Agrupa parcels por CP4/Geozona em bigbags, 1 motorista por bigbag, deteta divergentes, código único `BB-{sessão}-{cp4}-{zona}` | **Fundação do "assinar bigbag ao PUDO".** Estender bigbag para poder ser destinada a um `PudoStore` (não só a zona/motorista). |
| **Acesso de parceiros externos** | `customauth/models.py` (`EmpresaAccess`, `DriverAccess`, `DriverLoginOTP`) | Login próprio (fora do `User` Django) para frota + OTP por SMS/WhatsApp | **Padrão pronto para `PudoAccess`** (login do lojista) e OTP do cliente final. |
| **Entidade parceira externa** | `drivers_app/models.py:9-52` (`EmpresaParceira`) | Empresa externa com morada, NIF, IBAN, IVA, preço default, `ativo` | **Molde para o `PudoStore`** (loja com contrato, preço, ciclo pagamento, estado). |
| **Pacote moderno + POD + incidentes** | `orders_manager/models.py` (`Order`, `OrderStatusHistory` imutável, `delivery_proof` JSON, `OrderIncident`) | Estados PENDING→…→DELIVERED/RETURNED, histórico append-only, prova em JSON | Padrão de **POD, histórico e incidentes** a replicar na custódia PUDO. |
| **EPOD de entrada (Cainiao)** | `settlements/models.py` (`CainiaoOperationTask`) | Importa tarefas Cainiao com `delivery_type` (inclui "PUDO"), `receiver_lat/lng`, `actual_lat/lng` | Fonte do dado "isto é um pacote PUDO" e das coordenadas para deteção de fraude. |
| **Auditoria imutável** | `settlements/models.py:2932` (`PreInvoiceAuditLog`), `orders_manager` (`OrderStatusHistory`), `system_config/models.py:571` (`ConfigurationAudit`), `core` (`SyncLog`) | Logs append-only, `auto_now_add`, `diff` JSON | **Não há `AuditEvent` unificado.** Criar `PudoCustodyEvent` no mesmo padrão por domínio. |
| **Celery + Beat** | `my_project/celery.py:43-190` (30 tarefas agendadas) | Crons diários (sync parceiros, roll-forward, auto-emissão de faturas) | **Onde entram** o aging, notificações e auto-faturação do PUDO. |
| **API do app do motorista** | `app_api/views.py`, `app_api/auth.py` (`@app_token_required`), `app_api/serializers.py` | Views Django + JSON (não DRF), auth por token Bearer, login OTP | **Estilo a seguir** nos endpoints de handshake. DRF existe mas o app não o usa. |
| **Faturação (padrão)** | `settlements/models.py` (`DriverPreInvoice`, `PartnerInvoice`, `SettlementRun`), `settlements/services.py` | Totais denormalizados + linhas + audit log + snapshot periódico | Molde para a **fatura/extrato da loja PUDO**. |
| **Portal do motorista já cita PUDO** | `drivers_app/templates/drivers_app/portal/pudos.html` | Vista PUDO no portal do motorista | Referência de UI e de como o motorista já "vê" PUDO. |

**Conclusão:** ~40% da engenharia difícil já está feita (pagamento ao motorista,
bigbags, OTP, auditoria, crons, API por token). O módulo novo é sobretudo a
**loja como entidade gerida + custódia + portal do lojista + faturação à loja**.

---

## 2. Reenquadramento conceptual: PUDO v1 vs Rede PUDO

Há uma colisão de nomes que **temos de resolver antes de escrever código**:

- **PUDO v1 (existe):** classificação de uma entrega Cainiao. É sobre **pagar o
  motorista** por largar N pacotes num ponto. Não há loja gerida por nós.
- **Rede PUDO (novo):** o ponto de recolha é um **parceiro nosso**, com contrato,
  portal, stock, custódia, prazo de levantamento e a quem **pagamos por pacote
  entregue ao cliente**.

São dois pagamentos diferentes sobre o mesmo pacote:
`motorista` (PUDO v1, já feito) **e** `loja` (Rede PUDO, novo). O plano abaixo
assume esta separação. Sugestão de naming no código: manter `pudo_*` no `Partner`
para v1 e usar o namespace **`pudo_network`** (novo app) ou prefixo `PudoStore*`
para a rede, para não confundir.

> **Decisão em aberto (Q4, §8):** app novo `pudo_network` vs estender `sorting`?
> Recomendação: **app novo** `pudo_network`, importando de `sorting` e
> `settlements`. Mantém o `sorting` focado e o histórico limpo.

---

## 3. Correções de arquitetura (vs plano do Gemini e vs a minha crítica)

1. **Frontend do portal = Django Templates + Alpine.js + Tailwind 4**, herdando
   `dashboard_leguas/.../base.html`. **Nada de Vue/HTMX.** (Confirmado: Alpine via
   CDN, Tailwind browser build, zero `hx-*` no repo.)
2. **Máquina de estados = manual**, no padrão `settlements.PartnerInvoice`
   (`can_transition_to()` / `available_transitions()`) + modelo de histórico
   imutável tipo `OrderStatusHistory`. **Não introduzir django-fsm** (não está no
   `requirements.txt`; seria uma dependência nova só para isto).
3. **Offline-first está sobredimensionado para o MVP.** O lojista tem internet.
   Fazer o **PUDO como fonte-de-verdade online** do handshake (loja lê o QR
   online → transferência fecha, síncrono). Manter desde o dia 1 apenas o barato
   e necessário: **UUID de transação + endpoint idempotente** (encaixa no estilo
   `app_api`). Fila offline no lado do estafeta fica para Fase 2, e só se os dados
   de campo mostrarem zonas cegas a doer. Se for mesmo para QR assinado offline:
   **timestamp não previne replay** → precisa de `nonce + TTL curto + uso-único`
   validado no servidor.
4. **Faturação à loja = ledger imutável, não recontagem.** Emitir uma linha/evento
   imutável no momento do POD (padrão `PreInvoicePudo` + `PreInvoiceAuditLog`). O
   extrato do lojista **lê o ledger**, nunca recontagem de linhas vivas (senão uma
   mudança de estado altera receita histórica em silêncio).
5. **RGPD — falta a peça contratual.** Mascarar NIF/CC na UI (✓) e nunca guardar
   fotos de documento (✓) não chega: o lojista torna-se **subcontratante de
   dados**. Precisa de cláusula de subcontratação no contrato do PUDO + período de
   retenção do POD + base legal. Ver §8 Q2 (OTP como default vs NIF).
6. **Capacidade a 100% não pode encravar o hub.** Definir regra de *overflow*
   (reencaminhar para porta-a-porta ou PUDO mais próximo). Contagem é proxy
   grosseiro de espaço — ok para MVP, mas a regra de overflow tem de existir.

---

## 4. Máquina de estados de custódia (no padrão real do projeto)

Implementar como `status` (CharField + choices) num modelo de custódia, com
`can_transition_to()` e um `PudoCustodyEvent` append-only (à la `OrderStatusHistory`).
Cada transição regista quem/quando/onde e dispara os hooks.

```
ATRIBUIDO_HUB      sorting associou o pacote à bigbag daquele PUDO
   → EM_TRANSITO       (estafeta assina a saca à rota)
   → EM_STOCK_PUDO     (handshake QR concluído)
        ↳ dispara: notificação ao cliente + arranca relógio de aging
        ↳ NÃO marca "entregue" a montante
   → ENTREGUE_CLIENTE  (POD: OTP ou NIF validado)         [terminal feliz]
        ↳ dispara: LINHA DE FATURAÇÃO À LOJA (imutável)
        ↳ dispara: reconciliação a montante (ver Q1)
   → EXPIRADO          (cron de aging ultrapassa SLA)
        ↳ dispara: alerta no dashboard do PUDO
   → AGUARDA_DEVOLUCAO (hub/PUDO marca retorno, com motivo)
   → EM_DEVOLUCAO      (handshake reverso estafeta↔PUDO)
   → DEVOLVIDO_HUB     (receção conferida no hub)          [terminal]
        ↳ dispara: update de devolução a montante

DIVERGENCIA   exceção acessível de EM_STOCK_PUDO e DEVOLVIDO_HUB (falta/sobra).
              Nunca terminal: força resolução humana antes de reentrar no fluxo.
```

Os dois hooks caros (faturação da loja + reconciliação a montante) disparam num
**único ponto cada** (POD e devolução) → testáveis, auditáveis, e reaproveitam o
padrão de audit log existente.

---

## 5. Modelo de dados proposto (novos models + relações)

App novo `pudo_network` (nomes indicativos):

- **`PudoStore`** — a loja. Molde: `EmpresaParceira`.
  `nome, morada, cp, lat, lng, nif, iban, taxa_iva, status (ATIVO/PAUSADO/INATIVO),
  capacidade_max (int), horario (JSON), preco_1a_entrega, preco_adicional,
  ciclo_pagamento (SEMANAL/MENSAL), partner (FK core.Partner, nullable → multi-carrier),
  created_at`.
  → **carrier-agnostic desde o dia 1** (ver §7): pacote pode originar de qualquer
  cliente, não só Cainiao.
- **`PudoAccess`** — login do lojista. Molde: `EmpresaAccess`
  (`store OneToOne, username, password hash, is_active, last_login`). Papéis:
  `DONO` (vê financeiro) vs `ATENDENTE` (só operação) — resolve a rotatividade de
  balcão sem expor faturação.
- **`PudoCustodyPackage`** — o pacote sob custódia do PUDO. Liga ao pacote real
  (ver Q3: `orders_manager.Order` **ou** `CainiaoOperationTask`).
  `status (máquina §4), store (FK), driver (FK DriverProfile), bigbag (FK
  sorting.SortingBigbag, nullable), localizacao_prateleira (char, opcional),
  received_at, aging_deadline, delivered_at`.
- **`PudoTransaction`** — o handshake (custódia). `uuid (unique), tipo
  (ENTREGA/DEVOLUCAO), store, driver, status, created_at_device, synced_at`.
  **Idempotência pela `uuid`.**
- **`PudoCustodyEvent`** — histórico append-only. Molde: `OrderStatusHistory`
  (`package FK, from_status, to_status, actor, actor_type, motivo, meta JSON,
  created_at auto_now_add`).
- **`PudoDeliveryProof`** — POD. `package OneToOne, metodo (OTP/NIF/TERCEIRO),
  levantador_nome, doc_mascarado, otp_ok, assinatura (opcional), created_at`.
  **Nunca** foto de documento.
- **`PudoStoreBillingLine`** — ledger imutável de faturação à loja. Molde:
  `PreInvoicePudo` + `PreInvoiceAuditLog`. Emitida no POD, nunca recalculada.

**Extensão a `sorting.SortingBigbag`:** adicionar destino opcional a `PudoStore`
(hoje só tem `zona`/`driver`). É isto que permite "usar só a bigbag assinada ao
PUDO" e bloquear reutilização (a bigbag já tem sessão + código único; basta
marcar `pudo_store` e um flag `consumida`).

---

## 6. Mapa ideia → reuso (checklist de implementação)

| Ideia (Paulo) | Reusa | Novo |
|---|---|---|
| Admin CRUD de PUDOs + preço + ciclo pagamento | padrão `EmpresaParceira` + views admin | `PudoStore` |
| Assinar bigbag ao PUDO / bloquear reutilização | `sorting.SortingBigbag` (código único, sessão) | campo `pudo_store` + flag `consumida` |
| Capacidade 100% bloqueia sorting | — | validação em `scan`/assinação + **regra de overflow** |
| Handshake QR (driver↔PUDO) | `app_api` (token, JSON), OTP | `PudoTransaction` + endpoint idempotente por `uuid` |
| Recebimento por QR ou etiqueta de bigbag | `sorting.scan_parcel` | fluxo de receção no portal do lojista |
| Localização de prateleira (opcional) | — | campo `localizacao_prateleira` |
| POD com NIF/CC ou OTP | `DriverLoginOTP` (OTP), `Order.delivery_proof` | `PudoDeliveryProof` + mascaramento |
| Aging / expirar | Celery Beat (`my_project/celery.py`) | cron `pudo_mark_expired` |
| Notificar cliente (chegou / expira) | infra WhatsApp/SMS já usada em lembretes | tarefas de notificação |
| Devoluções + handshake reverso | mesma `PudoTransaction` (tipo=DEVOLUCAO) | motivos de retorno (dropdown) |
| Receção conferida no hub + faltas | padrão `SyncLog`/divergência do sorting | estado `DIVERGENCIA` |
| Pagamento ao **motorista** por PUDO | `services_pudo.py` **(já feito)** | — |
| Faturação/extrato à **loja** | padrão `PreInvoicePudo` + audit | `PudoStoreBillingLine` (ledger) |
| Dashboard do lojista (ganhos/ocupação/ações) | Templates + Alpine + Tailwind | vistas do portal |
| Deteção de fake delivery | `find_fake_delivery_suspects` **(já feito)** | — |

---

## 7. Reframe estratégico — carrier-agnostic

Com o fim do *de minimis* a reduzir volume Cainiao, a Rede PUDO não é só para
absorver volume em queda — é um **ativo B2B** vendável a outros carriers/shippers.
Modelar `PudoStore` e o pricing **carrier-agnostic desde o dia 1** (pacote pode
originar de qualquer `Partner`, não só Cainiao). Custo marginal hoje ≈ zero;
evita um refactor doloroso amanhã. Por isso `PudoStore.partner` é FK nullable e a
custódia liga a um pacote genérico (Q3), não a um `CainiaoOperationTask` fixo.

---

## 8. Decisões

> **Estado: FASE DE DISCUSSÃO.** Nada se constrói até o escopo estar todo
> fechado. Este documento é o caderno vivo dessa discussão.

**Decididas:**

- **Q2 — POD (DECIDIDO): solução híbrida.** OTP + NIF/CC conforme o caso, com
  desenho preparado para evoluir no futuro. *(A detalhar: quando cada método se
  aplica — valor, tipo de carrier, exigência do shipper.)*
- **Q3 — Pivô do pacote (DECIDIDO): camada de ligação genérica.**
  `PudoCustodyPackage` aponta para qualquer pacote via referência genérica
  (carrier-agnostic), não amarrado a `CainiaoOperationTask`. Alinha com o reframe
  B2B (§7).

**Em aberto (a discutir):**

- **Q1 — Reconciliação a montante.** Para a Cainiao, largar no PUDO já conta como
  *delivered* (é o que paga o motorista hoje). Então: o **levantamento pelo
  cliente** precisa de ir de volta à Cainiao, ou é interno? E as **devoluções/não
  levantados** — como e em que formato a Cainiao/Ecoscooting espera receber?
  *(Hipótese: levantamento = interno; devolução = precisa de callback.)*
- **Q4 — App novo `pudo_network` vs estender `sorting`.** Recomendação: app novo.
- **Q5 — App móvel do estafeta:** com que stack foi feita? Define se o handshake
  offline (Fase 2) é viável e como.

---

## 9. Plano faseado

- **Fase 0 — Fundações (1 sprint):** app `pudo_network`, `PudoStore` + admin CRUD,
  `PudoAccess` + login do lojista (reuso `EmpresaAccess`), extensão da bigbag para
  destino PUDO. Resolver Q3 e Q4.
- **Fase 1 — Custódia online (núcleo):** `PudoTransaction` + endpoint idempotente,
  handshake QR online, receção no portal, máquina de estados §4 +
  `PudoCustodyEvent`, notificação ao cliente. Sem offline.
- **Fase 2 — POD + aging + devoluções:** `PudoDeliveryProof` (OTP/NIF), cron de
  aging, logística reversa + handshake reverso, estado `DIVERGENCIA`.
- **Fase 3 — Faturação à loja + dashboard:** `PudoStoreBillingLine` (ledger),
  extrato do lojista, dashboard (ganhos/ocupação/ações), auto-emissão via Beat.
- **Fase 4 (condicional) — Offline-first do estafeta:** só se os dados de campo o
  justificarem; com nonce+TTL+uso-único.

---

## 10. Prompt Master (corrigido para a stack real)

> Aja como Arquiteto de Software Sénior e Programador **Django**.
>
> **Contexto:** módulo add-on **Rede PUDO** para o sistema de last-mile da Léguas
> Franzinas, já em produção. Stack real: **Django + PostgreSQL, Django Templates +
> Alpine.js + Tailwind CSS 4** (SEM React/Vue/HTMX), **Celery + Redis + Beat**,
> API do app do motorista em **views Django + JSON com auth por token**
> (`@app_token_required`, ver `app_api/`) — **não DRF**. Máquinas de estado são
> **manuais** (`can_transition_to()` + modelo de histórico imutável tipo
> `OrderStatusHistory`) — **NÃO usar django-fsm**. Auditoria = logs append-only por
> domínio (`PreInvoiceAuditLog`, `OrderStatusHistory`) — não há `AuditEvent`
> unificado.
>
> **Já existe (NÃO reimplementar):** pagamento ao motorista por PUDO
> (`settlements/services_pudo.py`: `compute_pudo_payment`, `find_fake_delivery_suspects`,
> campos `pudo_*` em `core.Partner`, `PreInvoicePudo`); sorting em bigbags virtuais
> (`sorting/models.py`, `sorting/services.py`); OTP e acessos de parceiros
> (`customauth`: `EmpresaAccess`, `DriverLoginOTP`).
>
> **Construir (app novo `pudo_network`):** `PudoStore` (molde `EmpresaParceira`,
> carrier-agnostic, capacidade, ciclo pagamento, estado ATIVO/PAUSADO/INATIVO),
> `PudoAccess` (molde `EmpresaAccess`, papéis DONO/ATENDENTE), `PudoCustodyPackage`
> (máquina de estados §4), `PudoTransaction` (handshake, **UUID único + endpoint
> idempotente**), `PudoCustodyEvent` (histórico append-only), `PudoDeliveryProof`
> (OTP default / NIF mascarado, RGPD, sem foto de doc), `PudoStoreBillingLine`
> (ledger imutável emitido no POD). Estender `sorting.SortingBigbag` com destino
> `pudo_store` + flag de consumo.
>
> **Regras críticas:** custódia online (loja é fonte-de-verdade); endpoint de
> handshake idempotente pela UUID (aceita duplicados → 200/204); largar no PUDO
> NÃO marca "entregue a montante"; POD dispara faturação imutável + reconciliação;
> capacidade tem regra de *overflow*, não encrava o hub.
>
> **Entregar primeiro:** (1) `models.py` do `pudo_network` com a máquina de estados
> manual e o ledger; (2) o endpoint idempotente de handshake no estilo `app_api`
> (token + JSON), com resolução por UUID.
