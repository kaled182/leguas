# Guia da App do Estafeta — Módulo PUDO

Material para **construir a app Android** (ou PWA) que opera a Rede PUDO. O
backend está **implementado e em produção**; a app ainda não existe — este
documento é o contrato completo a implementar.

Complementa: `PUDO_HANDSHAKE.md` (handshake online), `PUDO_OFFLINE.md` (offline
assinado). Coleção Postman pronta: `leguas-pudo.postman_collection.json`.

> `{BASE}` = `{HOST}/api/app/v1` — em produção tipicamente
> `http://89.153.26.181:8090/api/app/v1` (ajustar ao `DOMAIN`/`.env`).

---

## 1. Autenticação (partilhada com a app do motorista)

A app PUDO usa **o mesmo login OTP** da app do motorista. Não há login separado.

1. **Pedir código** — `POST {BASE}/auth/request-code`
   ```json
   { "phone": "912345678" }
   ```
   → `{ "sent": true, "masked_phone": "91****678" }` (código enviado por WhatsApp)

2. **Validar código** — `POST {BASE}/auth/verify-code`
   ```json
   { "phone": "912345678", "code": "123456" }
   ```
   →
   ```json
   {
     "token": "e3b0c4...<key>",
     "token_type": "Bearer",
     "expires_in": 7776000,
     "driver": { "...": "perfil do motorista" }
   }
   ```

3. **Usar o token** em todos os pedidos seguintes:
   ```
   Authorization: Bearer <token>
   ```
   Validade ~90 dias. `POST {BASE}/auth/logout` revoga o token.

---

## 2. Handshake online (com rede)

`POST {BASE}/pudo/handshake` — regista a entrega/devolução de um pacote a um PUDO.
**Idempotente pela `uuid`** (gerada no dispositivo): reenviar devolve o mesmo
estado, nunca duplica → seguro para retry.

Body:
```json
{
  "uuid": "5f3c2b1a-1111-2222-3333-abcdef012345",
  "pudo": "PUDO-0007",
  "tracking_ref": "LP00812345678PT",
  "tipo": "ENTREGA",
  "device_ts": "2026-07-01T14:32:00+01:00",
  "payload": { "client_phone": "+351912345678" }
}
```
- `tipo`: `ENTREGA` (default) ou `DEVOLUCAO`.
- `pudo`: número (`PUDO-0007`) ou id da loja.
- `payload.client_phone` (opcional) alimenta a notificação ao cliente.

Resposta 200:
```json
{
  "success": true,
  "idempotent": false,
  "transaction_uuid": "5f3c2b1a-...",
  "package": {
    "id": 42, "tracking_ref": "LP00812345678PT",
    "status": "EM_STOCK_PUDO", "store": "PUDO-0007",
    "received_at": "2026-07-01T14:32:05+01:00",
    "aging_deadline": "2026-07-08T14:32:05+01:00"
  }
}
```

Detalhe e erros: `PUDO_HANDSHAKE.md`.

---

## 3. Offline-first (sem rede)

### 3.1 Fila offline + sync em lote
Sem rede, a app **enfileira** localmente cada handshake (com a sua `uuid`). Ao
recuperar rede, envia tudo:
```
POST {BASE}/pudo/sync
{ "items": [ {handshake}, {handshake}, ... ] }
```
Cada item pode ser simples (como §2) ou assinado (§3.3). Idempotente por `uuid`;
um item com erro não bloqueia os outros. Resposta:
```json
{ "success": true, "processed": 3, "ok": 2, "results": [
  {"ref": "uuid-1", "success": true, "idempotent": false, "status": "EM_STOCK_PUDO"},
  {"ref": "uuid-2", "success": false, "error": "Nonce já usado (replay)."}
]}
```

### 3.2 Obter o segredo de assinatura
```
GET  {BASE}/pudo/device-key   → devolve o segredo (cria se preciso)
POST {BASE}/pudo/device-key   → roda o segredo
```
→
```json
{ "success": true, "driver": 42, "secret": "<64 hex>",
  "algo": "HMAC-SHA256",
  "sign_fields": ["uuid","pudo","tracking_ref","tipo","nonce","exp"],
  "max_ttl_seconds": 300 }
```
Guardar o `secret` em Keystore/Keychain.

### 3.3 QR assinado (anti-replay)
Para o PUDO validar um handshake gerado **offline** pelo estafeta, o QR leva
assinatura. Algoritmo:

- **canonical** = `uuid|pudo|tracking_ref|tipo|nonce|exp` (ordem fixa, `|`).
- `nonce`: aleatório único por QR (ex. UUID v4).
- `exp`: epoch (segundos), **agora + ≤ 300 s**.
- `sig = hex(HMAC_SHA256(secret, canonical))`.

QR (JSON):
```json
{ "uuid":"...", "pudo":"PUDO-0007", "tracking_ref":"LP...", "tipo":"ENTREGA",
  "nonce":"b7f1...", "exp":1751370000, "sig":"9a2c...", "driver":42 }
```
`driver` é obrigatório quando quem submete é o PUDO (não tem o token do estafeta).

Submeter (estafeta com token):
```
POST {BASE}/pudo/handshake-signed   (body = o JSON do QR)
```
O PUDO submete o mesmo JSON no portal web (`/pudo/rececao-offline/`).

Detalhe: `PUDO_OFFLINE.md`.

---

## 4. Estados do pacote (`package.status`)

| Estado | Significado |
|---|---|
| `ATRIBUIDO_HUB` | Associado à bigbag do PUDO no sorting |
| `EM_TRANSITO` | Saca assinada à rota do estafeta |
| `EM_STOCK_PUDO` | Recebido no PUDO (handshake concluído) — arranca aging |
| `ENTREGUE_CLIENTE` | Levantado pelo cliente (POD) — **terminal** |
| `EXPIRADO` | Passou o prazo de levantamento |
| `AGUARDA_DEVOLUCAO` | Marcado para devolução (com motivo) |
| `EM_DEVOLUCAO` | Handshake reverso estafeta↔PUDO |
| `DEVOLVIDO_HUB` | Rececionado de volta no hub — **terminal** |
| `DIVERGENCIA` | Exceção (falta/sobra) — exige resolução humana |

> Largar no PUDO (`EM_STOCK_PUDO`) **não** é "entregue ao cliente". O POD é um
> passo posterior, feito no PUDO.

---

## 5. Códigos de erro

Todas as respostas de erro: `{ "success": false, "error": "<mensagem>" }`.

| Status | Casos |
|---|---|
| 400 | campos em falta · `tipo` inválido · `exp` inválido · TTL demasiado longo · `items` não é lista |
| 401 | token ausente/inválido · **assinatura inválida** |
| 404 | PUDO ou estafeta não encontrado |
| 409 | QR expirado · **nonce já usado (replay)** · QR de outro PUDO · sem chave de dispositivo ativa |

---

## 6. Fluxo de referência da app

```
Login OTP → guardar token
Ao chegar a um PUDO:
  scan do código do pacote (câmara)
  se há rede:  POST /pudo/handshake            (uuid local, idempotente)
  se offline:  gerar nonce+exp, assinar, enfileirar; mostrar QR ao PUDO se preciso
Ao recuperar rede: POST /pudo/sync  (drena a fila)
Rodar o segredo (device-key POST) se o dispositivo mudar/for comprometido.
```

Boas práticas:
- **Uma `uuid` por scan**, reutilizada em todos os retries desse scan.
- Persistir a fila offline em SQLite/armazenamento local; só remover item após
  `success` no `sync`.
- Tratar `idempotent: true` como sucesso silencioso.
- `exp` curto (≤5 min) e `nonce` único por QR — o servidor rejeita replays.

---

## 7. Recursos

- Coleção Postman: `docs/api/leguas-pudo.postman_collection.json`
- Contratos detalhados: `PUDO_HANDSHAKE.md`, `PUDO_OFFLINE.md`
- Referência do módulo (portal, admin, modelos): `docs/modules/PUDO_NETWORK.md`
- Código-fonte de referência: `pudo_network/api.py`, `pudo_network/services.py`
