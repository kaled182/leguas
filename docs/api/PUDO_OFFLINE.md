# API — Offline-first do estafeta (Rede PUDO, Fase 4)

Protocolo de suporte a operação **sem rede** para a app Android do estafeta.
O backend está pronto; a app **ainda não existe** — este documento é o contrato
que ela deve implementar. Base: `pudo_network/api.py` + `pudo_network/services.py`.

Complementa `docs/api/PUDO_HANDSHAKE.md` (handshake online). Autenticação: mesmo
token Bearer da app do motorista.

## Princípios

1. **Fila offline + sync idempotente.** Sem rede, a app enfileira handshakes
   localmente (cada um com a sua `uuid`). Ao recuperar rede, envia o lote a
   `POST /api/app/v1/pudo/sync`. A idempotência por `uuid` garante que reenvios
   não duplicam.
2. **Redundância driver ↔ PUDO.** Ambos os lados podem reportar o mesmo pacote;
   o servidor reconcilia por (`pudo`, `tracking_ref`). O QR assinado permite que
   o PUDO valide um handshake gerado offline pelo estafeta.
3. **QR assinado anti-replay.** Um timestamp não chega. Cada QR offline leva
   **`nonce` + `exp` (TTL curto ≤ 300 s) + assinatura HMAC-SHA256**, validados no
   servidor: assinatura correta, dentro do TTL, e `nonce` nunca visto (uso-único).

## 1. Obter o segredo de assinatura

```
GET  /api/app/v1/pudo/device-key      → devolve o segredo atual (cria se preciso)
POST /api/app/v1/pudo/device-key      → roda o segredo
```

Resposta:
```json
{
  "success": true,
  "driver": 42,
  "secret": "e3b0c44298fc1c14...<64 hex>",
  "algo": "HMAC-SHA256",
  "sign_fields": ["uuid", "pudo", "tracking_ref", "tipo", "nonce", "exp"],
  "max_ttl_seconds": 300
}
```

A app guarda o `secret` de forma segura (Keystore/Keychain). Usa-o para assinar
QR offline. Rodar o segredo invalida QR ainda não sincronizados.

## 2. Assinar um QR offline

Canonical string (ordem fixa, separador `|`):
```
uuid|pudo|tracking_ref|tipo|nonce|exp
```
- `nonce`: aleatório único por QR (ex.: UUID v4).
- `exp`: epoch em segundos, **agora + ≤ 300 s**.
- `sig = hex( HMAC_SHA256(secret, canonical) )`.

QR = JSON:
```json
{
  "uuid": "5f3c2b1a-...",
  "pudo": "PUDO-0007",
  "tracking_ref": "LP00812345678PT",
  "tipo": "ENTREGA",
  "nonce": "b7f1...",
  "exp": 1751370000,
  "sig": "9a2c...",
  "driver": 42
}
```
`driver` é obrigatório quando quem submete é o **PUDO** (não tem o token do
estafeta) — o servidor usa-o para carregar a chave e verificar a assinatura.

## 3. Submeter

### Estafeta (com token), assinado
```
POST /api/app/v1/pudo/handshake-signed
Authorization: Bearer <token>
```
Body = o JSON do QR. Verifica sig + TTL + nonce, depois processa. 200 idempotente.

### Estafeta (com token), lote da fila offline
```
POST /api/app/v1/pudo/sync
Authorization: Bearer <token>
{ "items": [ {handshake}, {handshake assinado}, ... ] }
```
Cada item pode ser simples (como `/handshake`) ou assinado (com `sig`). Resposta:
```json
{ "success": true, "processed": 3, "ok": 3, "results": [
  {"ref": "uuid-1", "success": true, "idempotent": false, "status": "EM_STOCK_PUDO"},
  {"ref": "uuid-2", "success": false, "error": "Nonce já usado (replay)."}
]}
```

### PUDO (portal web), lê o QR do estafeta
`/pudo/rececao-offline/` — o lojista cola/lê o JSON do QR; o servidor valida
(assinatura pela chave do estafeta indicado em `driver`, TTL, nonce) e regista a
receção para a **sua** loja. Rejeita QR destinado a outro PUDO.

## Erros (todos JSON `{success:false, error}`)

| Status | Caso |
|---|---|
| 400 | campos em falta / `tipo` inválido / `exp` inválido / TTL demasiado longo |
| 401 | token inválido **ou** assinatura inválida |
| 404 | PUDO ou estafeta não encontrado |
| 409 | QR expirado · **nonce já usado (replay)** · QR de outro PUDO · sem chave ativa |

## Housekeeping

`purge_expired_nonces()` (em `services.py`) remove nonces expirados — pode ligar-se
a um cron se o volume crescer. A validação de replay não depende da limpeza (um
nonce expirado é rejeitado pelo TTL antes de chegar ao uso-único).
