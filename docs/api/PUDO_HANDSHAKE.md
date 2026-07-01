# API — Handshake PUDO (app do estafeta)

Contrato do endpoint de custódia da **Rede PUDO** para a app Android do estafeta.
Estilo idêntico à restante API do motorista (`docs/api/API_APP.md`): **views Django
+ JSON, token Bearer, sem DRF**. Fonte-de-verdade do código: `pudo_network/api.py`.

> **Estado:** backend pronto (Fase 1). A app Android **ainda não existe** — este
> documento é o que ela deve implementar. Ver `docs/modules/PUDO_NETWORK_PLAN.md`.

## Autenticação

Mesmo token da app do motorista. Obter via o fluxo OTP existente
(`POST /api/app/v1/auth/request-code` → `verify-code` → `token`) e enviar:

```
Authorization: Bearer <token>
```

## POST `/api/app/v1/pudo/handshake`

Regista um handshake de custódia entre o estafeta e um PUDO. **Idempotente pela
`uuid`**: reenviar a mesma `uuid` devolve o mesmo estado (200), nunca duplica —
seguro para retry offline/perda de rede.

### Corpo (JSON)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `uuid` | string (UUID) | **sim** | Chave de idempotência gerada **no dispositivo**. Reutilizar no retry do mesmo scan. |
| `pudo` | string | **sim** | Identidade do PUDO: número (`PUDO-0001`) ou id numérico. |
| `tracking_ref` | string | **sim** | Código/waybill do pacote lido (câmara do telemóvel). |
| `tipo` | string | não | `ENTREGA` (default) ou `DEVOLUCAO`. |
| `device_ts` | string ISO-8601 | não | Timestamp do dispositivo (para reconciliação offline). |
| `payload` | objeto | não | Dados livres. Ex.: `{"client_phone": "+3519..."}` alimenta a notificação ao cliente. |

### Exemplo

```http
POST /api/app/v1/pudo/handshake
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "uuid": "5f3c2b1a-1111-2222-3333-abcdef012345",
  "pudo": "PUDO-0007",
  "tracking_ref": "LP00812345678PT",
  "tipo": "ENTREGA",
  "device_ts": "2026-07-01T14:32:00+01:00",
  "payload": { "client_phone": "+351912345678" }
}
```

### Respostas

**200** — processado (ou reenvio idempotente):

```json
{
  "success": true,
  "idempotent": false,
  "transaction_uuid": "5f3c2b1a-1111-2222-3333-abcdef012345",
  "package": {
    "id": 42,
    "tracking_ref": "LP00812345678PT",
    "status": "EM_STOCK_PUDO",
    "store": "PUDO-0007",
    "received_at": "2026-07-01T14:32:05+01:00",
    "aging_deadline": "2026-07-08T14:32:05+01:00"
  }
}
```

- `idempotent: true` → esta `uuid` já tinha sido processada; o `package` reflete o
  estado atual (a app pode tratar como sucesso silencioso).

**400** — campos em falta ou `tipo` inválido:
```json
{ "success": false, "error": "Campos obrigatórios em falta: tracking_ref" }
```

**401** — token ausente/inválido:
```json
{ "success": false, "error": "Token ausente ou inválido." }
```

**404** — PUDO não encontrado:
```json
{ "success": false, "error": "PUDO não encontrado." }
```

## Estados da custódia (`package.status`)

`ATRIBUIDO_HUB → EM_TRANSITO → EM_STOCK_PUDO → ENTREGUE_CLIENTE` (feliz);
ramos: `EXPIRADO`, `AGUARDA_DEVOLUCAO → EM_DEVOLUCAO → DEVOLVIDO_HUB`, e
`DIVERGENCIA` (exceção, nunca terminal). Um handshake `ENTREGA` leva o pacote a
`EM_STOCK_PUDO`; largar no PUDO **não** marca "entregue ao cliente" — o POD é um
passo posterior (Fase 2).

## Redundância driver ↔ PUDO

O balcão do PUDO também reporta a receção (portal web). Como ambos os lados podem
reportar o mesmo pacote, o backend reconcilia por (`pudo`, `tracking_ref`): o
segundo report é um **no-op de estado** (regista transação/evento, não avança duas
vezes). A app deve, ainda assim, enviar sempre o seu handshake — a convergência é
garantida pelo servidor.
