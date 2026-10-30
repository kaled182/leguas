# Allowlist do middleware de permissões — por aprovar

**Estado:** aprovada e implementada no branch `fix/seguranca-permissoes`, em `core/permissions.py`.
**Método:** teste anónimo de 560 rotas, mais leitura de `@csrf_exempt` e do código de autenticação.

## 1. Sem sessão

| # | Rota | Motivo | Proteção própria |
|---|---|---|---|
| 1 | `/health/` | Healthcheck do Docker e do Caddy | Nenhuma |
| 2 | `/auth/`, `/auth/authenticate/`, `/auth/login/` | Login interno | Password |
| 3 | `/auth/logout/`, `/auth/driver/logout/`, `/auth/empresa/logout/`, `/driversapp/logout/` | Terminar sessão | Sessão |
| 4 | `/auth/driver/`, `/auth/driver/login/`, `/auth/driver/send-code/`, `/auth/driver/verify-code/` | Login do motorista | Password ou OTP |
| 5 | `/auth/empresa/`, `/auth/empresa/login/` | Login da frota | Password |
| 6 | `/driversapp/cadastro/`, `/driversapp/cadastro-completo/` | Registo público de motoristas | Nenhuma |
| 7 | `/api/app/v1/` (prefixo, 17 rotas) | App do motorista | Token Bearer, 401 sem token |
| 8 | `/geozonas/api/zonas/export/` | ReliableMaps | Bearer `ZONAS_EXPORT_KEY` |
| 9 | `/system/whatsapp/webhook/` | Webhook do WPPConnect, em uso | Nenhuma: ver N3 |
| 10 | `/core/pre-invoice/sign/<token>/` | Assinatura remota de pré-fatura | Token no URL |
| 11 | `/static/`, `/media/` | Em produção, o Caddy serve-os antes do Django | Nenhuma: ver N2 |

## 2. Com sessão própria

O middleware deixa passar. A view mantém a sua proteção.

| Rota | Proteção |
|---|---|
| `/driversapp/portal/`, `/contracts/portal/` | `portal_access_required`: só o próprio motorista ou staff |
| `/settlements/empresas/<id>/portal/` | `empresa_login_required`: só a própria frota ou staff |

## 3. Fora da allowlist

| Rota | Motivo |
|---|---|
| `/settlements/cainiao/operation/import/` | Hoje abre sem login. Só `core/partner_detail.html` a usa, com sessão: ver N1 |
| `/settlements/cainiao/parcel-list/preview/` | Igual à anterior |
| `/dashboard_v2/` | Fechada com `login_required` neste branch |
| `/admin/` | Só Gestão. O middleware recusa o Operador, para o admin não contornar o mapa |

## 4. Factos

- **Reset de password:** não existe rota pública. O reset é feito por um administrador em `/system/users/`.
- **Webhooks de parceiros:** o único POST externo sem CSRF é o do WPPConnect. O projeto tem 2 vistas `@csrf_exempt` fora de `app_api`: esse webhook e `/converter/`, que exige login.
- **Sincronização de integrações:** os dados da Cainiao vêm por API da Reliable. O sistema vai buscá-los em Celery (`settlements.sync_epod_from_reliable`), por isso o pedido não passa pelo middleware. O botão manual usa a sessão do utilizador.

## 5. Interruptor

`PERMISSIONS_ENFORCE=0` desliga o middleware. Valor por omissão: `1`.

**NOTA:** a variável não precisa de build nem de deploy, mas precisa de recriar o container:

```bash
cd /root/leguas/production
# edite PERMISSIONS_ENFORCE no ficheiro .env
docker compose up -d web
```

## 6. Resultado das verificações

| Item | Facto | Ação |
|---|---|---|
| N1 | `DEBUG = False` em produção. Hotfix no branch `hotfix/cainiao-import-login` | Deploy antes deste PR |
| N2 | Ver a secção 7 | PR seguinte, com prioridade alta |
| N3 | O WPPConnect envia para este sistema. O OTP do motorista usa WhatsApp | A rota fica na allowlist. Não bloquear no Caddy |
| Token de assinatura | `secrets.token_urlsafe(32)`. Corrigido (B14): expira 7 dias depois do envio, assina 1 vez e só em `RASCUNHO` ou `CALCULADO` | Feito |
| OTP do motorista | 6 dígitos, 5 min, 5 tentativas, 1 envio por número a cada 60 s. **Sem limite por IP** | Feito: 10 envios e 30 validações por hora, por IP |
| Cadastro público | 10 envios por hora, por IP | Feito |
| API da app | 15 rotas exigem token. 2 rotas são o próprio login | Teste por rota em `app_api/test_auth_required.py` |

**B14:** um novo POST em `/core/pre-invoice/sign/<token>/` volta a pôr a pré-fatura em `APROVADO`, em qualquer estado, incluindo `PAGO` e `CANCELADO`.

## 7. Ficheiros em `/media/`

- O caminho é `pasta/ano/mês/nome-original`, por exemplo `driver_documents/2026/10/cc.pdf`.
- O nome não tem parte aleatória. O Django só acrescenta um sufixo em caso de colisão.
- O Caddy não lista pastas, mas um nome comum pode ser adivinhado por tentativa.
- A cache é pública por 7 dias.
- `DriverDocument` tem 0 registos, mas os comprovativos de pré-faturas, as reclamações e os documentos de frota usam a mesma regra.

**Conclusão:** os nomes são adivinháveis. A prioridade é alta, no PR seguinte.
