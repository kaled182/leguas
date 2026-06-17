# API da App do Motorista — Léguas Franzinas

**Versão:** 1.0 · **Base URL:** `/api/app/v1`

Documento de referência para integração da **app móvel do motorista** com o
sistema Léguas Franzinas. Autenticação por **token Bearer** obtido via código
OTP enviado por WhatsApp.

- Servidor atual: `http://89.153.26.181:8090/api/app/v1`
- Produção (TLS, quando publicado): `https://app.leguasfranzinas.pt/api/app/v1`
- Especificação máquina: [`openapi-app.yaml`](openapi-app.yaml) ·
  Coleção Postman: [`leguas-driver-app.postman_collection.json`](leguas-driver-app.postman_collection.json)

---

## 1. Convenções

- Todos os corpos de pedido e resposta são **JSON** (`Content-Type: application/json`),
  exceto o PDF da pré-fatura (`application/pdf`).
- **Datas/horas** em ISO 8601 (`2026-06-14T11:44:00Z`); **datas** em `YYYY-MM-DD`.
- **Valores monetários** em euros, como *string* decimal (ex.: `"482.50"`).
- **Rotas sem barra final** (ex.: `/auth/request-code`, **não** `.../request-code/`).
- Erros devolvem `{ "error": "mensagem" }` (ou `{ "success": false, "error": ... }`
  nos endpoints de escrita) com o código HTTP adequado.

### Códigos HTTP

| Código | Significado |
|---|---|
| 200 | OK |
| 201 | Criado (POST /complaints) |
| 204 | Sem conteúdo (logout) |
| 400 | Pedido inválido (validação, código errado/expirado) |
| 401 | Token ausente ou inválido |
| 404 | Recurso não encontrado / não pertence ao motorista |
| 429 | Demasiados pedidos (anti-spam OTP / tentativas) |
| 500 | Erro interno |
| 502 | Falha ao enviar o código por WhatsApp |

---

## 2. Autenticação (OTP → token)

Fluxo idêntico ao das apps de entregas: o motorista entra com o **número de
telemóvel** e um **código de 6 dígitos** recebido por WhatsApp.

```
1. POST /auth/request-code   { phone }            → envia código por WhatsApp
2. POST /auth/verify-code     { phone, code }      → devolve { token, driver }
3. (todos os pedidos)         Authorization: Bearer <token>
```

- O número é resolvido pelos **últimos 9 dígitos** (aceita `+351`/formatação).
- Código **válido 5 minutos**, máximo **5 tentativas**, **1 pedido por 60 s**.
- O **token é válido 90 dias** e pode ser revogado (`/auth/logout`).
- Não usa cookies de sessão — apenas o cabeçalho `Authorization`.

### 2.1 `POST /auth/request-code`

Sem autenticação.

**Pedido**
```json
{ "phone": "912345678" }
```

**Resposta `200`**
```json
{ "sent": true, "masked_phone": "••• ••• 678" }
```

**Erros:** `400` (número inválido / motorista não encontrado),
`429` (pedido demasiado frequente), `502` (falha no WhatsApp).

```bash
curl -X POST "$BASE/auth/request-code" \
  -H "Content-Type: application/json" \
  -d '{"phone":"912345678"}'
```

### 2.2 `POST /auth/verify-code`

Sem autenticação.

**Pedido**
```json
{ "phone": "912345678", "code": "472662" }
```

**Resposta `200`**
```json
{
  "token": "9f3c…(64 hex)",
  "token_type": "Bearer",
  "expires_in": 7776000,
  "driver": {
    "id": 77,
    "nome_completo": "Affonso LF",
    "apelido": "affonso",
    "telefone": "+351912345678",
    "email": "driver@exemplo.pt",
    "nif": "123456789",
    "status": "ATIVO",
    "status_display": "Ativo",
    "is_active": true,
    "tipo_vinculo": "DIRETO",
    "courier_id_cainiao": "",
    "created_at": "2026-01-10T09:00:00Z"
  }
}
```

**Erros:** `400` (código incorreto/expirado), `429` (demasiadas tentativas).

### 2.3 `POST /auth/logout`

Requer `Authorization`. Revoga o token atual. Resposta `204` (sem corpo).

---

## 3. Perfil

### 3.1 `GET /me`

Requer `Authorization`. Devolve o objeto `driver` (mesma estrutura de `verify-code`).

```bash
curl "$BASE/me" -H "Authorization: Bearer $TOKEN"
```

---

## 4. Faturas (pré-faturas)

### 4.1 `GET /invoices`

Lista as pré-faturas do motorista. Filtros opcionais: `?status=PAGO`, `?ano=2026`.

**Resposta `200`**
```json
{
  "results": [
    {
      "id": 12,
      "numero": "PF-0012",
      "periodo_inicio": "2026-05-01",
      "periodo_fim": "2026-05-31",
      "status": "PAGO",
      "status_display": "Pago",
      "total_a_receber": "482.50",
      "data_pagamento": "2026-06-05"
    }
  ]
}
```

### 4.2 `GET /invoices/{id}`

Detalhe completo (inclui rubricas). `404` se não pertencer ao motorista.

```json
{
  "id": 12,
  "numero": "PF-0012",
  "periodo_inicio": "2026-05-01",
  "periodo_fim": "2026-05-31",
  "status": "PAGO",
  "status_display": "Pago",
  "total_a_receber": "482.50",
  "data_pagamento": "2026-06-05",
  "base_entregas": "420.00",
  "total_bonus": "30.00",
  "total_pudo": "12.50",
  "total_extras": "20.00",
  "total_pacotes_perdidos": "30.00",
  "total_adiantamentos": "0.00",
  "referencia_pagamento": "MB WAY"
}
```

### 4.3 `GET /invoices/{id}/pdf`

Devolve o **PDF** da pré-fatura (`application/pdf`).

---

## 5. Descontos

### 5.1 `GET /discounts`

Descontos financeiros (DriverClaim) do motorista, com estado de recurso e
contadores. Filtro opcional: `?status=APPROVED`.

```json
{
  "results": [
    {
      "id": 85,
      "claim_type": "CUSTOMER_COMPLAINT",
      "claim_type_display": "Reclamação de Cliente",
      "status": "APPROVED",
      "status_display": "Aprovado",
      "amount": "30.00",
      "waybill_number": "CNPRT49009291234007659709",
      "description": "Cliente não recebeu a encomenda.",
      "occurred_at": "2026-06-05T11:44:00Z",
      "operation_task_date": "2026-06-05",
      "situacao": {
        "label": "Desconto aplicado",
        "icon": "check-circle",
        "tone": "bad",
        "classes": "bg-rose-100 text-rose-800"
      }
    }
  ],
  "counts": { "total": 9, "pending": 0, "approved": 3, "rejected": 0, "appealed": 6 }
}
```

> O objeto `situacao` é um auxiliar de UI (rótulo/ícone/tom). A app pode usar o
> `label`/`icon`/`tone` e ignorar `classes` (específico da web).

---

## 6. Reclamações (tickets)

### 6.1 `GET /complaints`

Lista as reclamações de cliente do motorista + opções de filtro. `?status=ABERTO`.

```json
{
  "complaints": [ { "id": 92, "numero_pacote": "…", "tipo": "ENTREGA_FALSA", "status": "ABERTO", "...": "…" } ],
  "tipo_choices":   [ { "value": "ENTREGA_FALSA", "label": "Entrega Falsa" } ],
  "status_choices": [ { "value": "ABERTO", "label": "Aberto" } ]
}
```

### 6.2 `POST /complaints`

Cria uma reclamação. Campos **obrigatórios**: `numero_pacote`, `tipo`,
`descricao`, `nome_cliente`, `telefone_cliente`, `morada`, `codigo_postal`,
`cidade` (opcional: `email_cliente`).

**Pedido**
```json
{
  "numero_pacote": "CNPRT49009291234007659709",
  "tipo": "ENTREGA_FALSA",
  "descricao": "Cliente afirma não ter recebido a encomenda.",
  "nome_cliente": "Graciano Gomes",
  "telefone_cliente": "963960820",
  "morada": "Rua Exemplo, 12",
  "codigo_postal": "4900-123",
  "cidade": "VIANA DO CASTELO"
}
```

**Resposta `201`**
```json
{ "success": true, "complaint": { "id": 130, "...": "…" } }
```

**Erro `400`** (campos em falta / tipo inválido):
```json
{ "success": false, "error": "Campos obrigatórios em falta: morada, cidade" }
```

---

## 7. Valores de enumeração

**Perfil — `status`:** `PENDENTE`, `EM_ANALISE`, `ATIVO`, `BLOQUEADO`, `IRREGULAR`
· **`tipo_vinculo`:** `DIRETO`, `PARCEIRO`

**Pré-fatura — `status`:** `RASCUNHO`, `CALCULADO`, `APROVADO`, `PENDENTE`,
`CONTESTADO`, `REPROVADO`, `PAGO`

**Desconto — `status`:** `PENDING`, `APPROVED`, `REJECTED`, `APPEALED`,
`QUARANTINE`
· **`claim_type`:** `ORDER_LOSS`, `ORDER_DAMAGE`, `VEHICLE_FINE`,
`VEHICLE_DAMAGE`, `FUEL_EXCESS`, `MISSING_POD`, `LATE_DELIVERY`,
`CUSTOMER_COMPLAINT`, `FAKE_DELIVERY`, `OTHER`

**Reclamação — `status`:** `ABERTO`, `NOTIFICADO`, `RESPONDIDO`, `FECHADO`,
`CANCELADO`
· **`tipo`:** `ENTREGA_FALSA`, `ITEM_FALTANDO`, `PACOTE_DANIFICADO`,
`ENTREGA_ATRASADA`, `OUTRO`

> Para `tipo`/`status` de reclamações, usa preferencialmente as listas
> `tipo_choices`/`status_choices` devolvidas em `GET /complaints` (rótulos
> prontos para mostrar).

---

## 8. Resumo dos endpoints

| Método | Caminho | Auth | Descrição |
|---|---|:---:|---|
| POST | `/auth/request-code` | — | Pedir código OTP por WhatsApp |
| POST | `/auth/verify-code` | — | Validar código → token + perfil |
| POST | `/auth/logout` | ✔ | Revogar o token |
| GET | `/me` | ✔ | Perfil do motorista |
| GET | `/invoices` | ✔ | Listar pré-faturas (`?status`, `?ano`) |
| GET | `/invoices/{id}` | ✔ | Detalhe da pré-fatura |
| GET | `/invoices/{id}/pdf` | ✔ | PDF da pré-fatura |
| GET | `/discounts` | ✔ | Descontos + contadores (`?status`) |
| GET | `/complaints` | ✔ | Listar reclamações (`?status`) |
| POST | `/complaints` | ✔ | Criar reclamação |

*Auth ✔ = requer `Authorization: Bearer <token>`.*
