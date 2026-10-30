# Allowlist do middleware de permissões — por aprovar

**Estado:** proposta. O middleware não foi implementado.
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
| 9 | `/system/whatsapp/webhook/` | Webhook do WPPConnect | Nenhuma: ver N3 |
| 10 | `/core/pre-invoice/sign/<token>/` | Assinatura remota de pré-fatura | Token no URL |
| 11 | `/static/`, `/media/` | Em produção, o Caddy serve-os antes do Django | Nenhuma: ver N2 |

## 2. Com sessão própria

O middleware deixa passar. A view mantém a sua proteção.

| Rota | Proteção |
|---|---|
| `/admin/` | Login do Django admin |
| `/driversapp/portal/`, `/contracts/portal/` | `portal_access_required`: só o próprio motorista ou staff |
| `/settlements/empresas/<id>/portal/` | `empresa_login_required`: só a própria frota ou staff |

## 3. Fora da allowlist

| Rota | Motivo |
|---|---|
| `/settlements/cainiao/operation/import/` | Hoje abre sem login. Só `core/partner_detail.html` a usa, com sessão: ver N1 |
| `/settlements/cainiao/parcel-list/preview/` | Igual à anterior |
| `/dashboard_v2/` | Fechada com `login_required` neste branch |

## 4. Factos

- **Reset de password:** não existe rota pública. O reset é feito por um administrador em `/system/users/`.
- **Webhooks de parceiros:** o único POST externo sem CSRF é o do WPPConnect. O projeto tem 2 vistas `@csrf_exempt` fora de `app_api`: esse webhook e `/converter/`, que exige login.
- **Sincronização de integrações:** corre em Celery e não passa pelo middleware. O botão manual usa a sessão do utilizador.

## 5. Interruptor

`PERMISSIONS_ENFORCE=0` desliga o middleware. Valor por omissão: `1`.

**NOTA:** a variável não precisa de build nem de deploy, mas precisa de recriar o container:

```bash
cd /root/leguas/production
# edite PERMISSIONS_ENFORCE no ficheiro .env
docker compose up -d web
```

## 6. Decisões pedidas

| # | Questão | Recomendação |
|---|---|---|
| N1 | As 2 rotas de import Cainiao abrem sem login em produção. Um anónimo pode obter um token CSRF na página de login e enviar um ficheiro | Corrigir já com `login_required`, em hotfix próprio, sem esperar pelo PR |
| N2 | O Caddy serve `/media/` sem login. Quem tiver o URL de um documento abre-o | Registar como pendente. Corrigir exige mudar o Caddy e os links |
| N3 | O webhook diz "só acessível na rede interna", mas o Caddy encaminha tudo para o Django | Bloquear o caminho no Caddy, porque o WhatsApp não é usado |
