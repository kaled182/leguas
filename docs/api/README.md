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

## Estado de implementação

A spec é o **contrato-alvo**. Cada endpoint está anotado com `x-status`:

- **`existe`** — a lógica já existe no backend (hoje servida por sessão/AJAX web).
  Para a app, precisa de ser exposta sob auth por token.
- **`a-implementar`** — faz parte da camada **`app-api`** a criar: emissão de
  token a partir do OTP (`/auth/verify-code`), `/me`, e respostas JSON limpas
  para faturas e descontos.

### Recomendação de implementação (backend)

Criar uma app Django `app_api` montada em `/api/app/v1/` com:

- **Token**: tabela de tokens por motorista (ou JWT/`rest_framework` TokenAuth),
  emitido no `verify-code` e validado num *authentication middleware* próprio
  (resolve o `DriverProfile` a partir do token, sem sessão).
- **Reutilização**: o OTP (`DriverLoginOTP`) e o normalizador de número
  (`to_whatsapp_number`) já existem; o `verify-code` só muda o retorno
  (token em vez de `redirect`). Faturas/descontos/reclamações reaproveitam
  os mesmos modelos (`DriverPreInvoice`, `DriverClaim`, `CustomerComplaint`).

## Como usar a coleção Postman

1. Importar `leguas-driver-app.postman_collection.json`.
2. Ajustar a variável `base_url` (default: `http://89.153.26.181:8090/api/app/v1`).
3. Definir `phone`, correr **Pedir código OTP**, preencher `code` com o que chegou
   ao WhatsApp e correr **Validar código** — o token fica guardado e os restantes
   pedidos passam a estar autenticados.

> O `base_url` aponta para o prefixo `/api/app/v1` previsto. Enquanto a camada
> `app-api` não existir, os endpoints `existe` podem ser testados nos seus
> caminhos web atuais (ver `x-maps-to` em cada operação da spec).
