# API da App do Motorista — Léguas Franzinas

Material para construção de uma **app móvel do motorista**.

## Ficheiros

| Ficheiro | O que é |
|---|---|
| [`openapi-app.yaml`](openapi-app.yaml) | Especificação **OpenAPI 3.1** — o *contrato* da API. Importável em Swagger UI, Stoplight, Postman, Insomnia, e gera código cliente (Swift, Kotlin, Dart/Flutter, TS) via `openapi-generator`. |
| [`leguas-driver-app.postman_collection.json`](leguas-driver-app.postman_collection.json) | Coleção **Postman** pronta a testar. Guarda o token automaticamente após validar o código. |

## Autenticação (OTP → token)

O modelo é o mesmo que as apps de entregas usam — **telemóvel + código por WhatsApp**:

1. `POST /auth/request-code` com `{ "phone": "912345678" }` → envia código de 6 dígitos por WhatsApp (válido 5 min).
2. `POST /auth/verify-code` com `{ "phone": "...", "code": "472662" }` → devolve `{ token, driver }`.
3. A app guarda o `token` e envia-o em todos os pedidos: `Authorization: Bearer <token>`.

Sem cookies de sessão, sem CSRF — adequado a app nativa.

## Estado de implementação — ✅ IMPLEMENTADO

A camada **`app_api`** está implementada e montada em **`/api/app/v1/`**.
A anotação `x-status` na spec é histórica (`existe` = já havia lógica web;
`a-implementar` = criado agora nesta camada) — **todos os endpoints abaixo
estão funcionais** após `migrate` (tabela `app_api_driverapptoken`).

### Como está construído (backend)

App Django `app_api` (registada em `INSTALLED_APPS`, rotas em `/api/app/v1/`):

- **Token** — modelo `app_api.DriverAppToken` (chave opaca de 64 hex, validade
  90 dias, revogável). Emitido em `/auth/verify-code`, validado pelo decorator
  `app_token_required` que resolve o `DriverProfile` a partir do `Authorization:
  Bearer <token>` (sem sessão/cookies). POST são `csrf_exempt`.
- **OTP partilhado** — `customauth/otp_service.py` (`resolve_driver_by_phone`,
  `send_otp`, `verify_otp`) é usado tanto pelo login web (sessão) como pela app
  (token) — uma só fonte de verdade. Reaproveita `DriverLoginOTP`,
  `to_whatsapp_number` e `send_text_reliable`.
- **Recursos** — faturas/descontos/reclamações usam os mesmos modelos
  (`DriverPreInvoice`, `DriverClaim`, `CustomerComplaint`); PDF da PF via
  `PDFGenerator`. Respostas JSON em `app_api/serializers.py`.

> **Rotas sem barra final** (`/auth/request-code`, não `.../request-code/`).
> Token devolvido em `/auth/verify-code` no campo `token` (válido 90 dias).

## Como usar a coleção Postman

1. Importar `leguas-driver-app.postman_collection.json`.
2. Ajustar a variável `base_url` (default: `http://89.153.26.181:8090/api/app/v1`).
3. Definir `phone`, correr **Pedir código OTP**, preencher `code` com o que chegou
   ao WhatsApp e correr **Validar código** — o token fica guardado e os restantes
   pedidos passam a estar autenticados.

> O `base_url` aponta para o prefixo `/api/app/v1` previsto. Enquanto a camada
> `app-api` não existir, os endpoints `existe` podem ser testados nos seus
> caminhos web atuais (ver `x-maps-to` em cada operação da spec).
