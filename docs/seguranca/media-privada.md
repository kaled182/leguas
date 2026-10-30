# Ficheiros privados em `/media/`

**Estado:** implementado no branch `fix/media-privada`. Sem deploy.

## Mecanismo

1. O browser pede `/media/...` ao Caddy.
2. O Caddy pergunta ao Django em `/media-auth/` (`forward_auth`).
3. O Django responde 204 (pode), 302 (login) ou 403 (recusado).
4. Com 204, o Caddy serve o ficheiro.

## Regras

| Quem | Pode abrir |
|---|---|
| Público | `company/` e `system_config/logos/` |
| Gestão | Tudo |
| Operador | Documentos de motoristas e veículos, reclamações, tickets, incidências, OCR, fotos de perfil e contratos |
| Motorista | Só os próprios: documentos, veículos, reclamações, provas, pré-faturas, acertos e contratos |
| Frota | Só os próprios: documentos, contratos, anexos de faturas e comprovativos |
| App do motorista | URL assinado, válido 24 horas, só para imagens de incidências |

**NOTA:** uma pasta fora desta lista fica só para Gestão.

## Deploy

**AVISO:** faça estes passos por esta ordem. O Caddy tem de mudar depois do Django. Caso contrário, nenhum ficheiro abre.

**NOTA:** o `update.sh` não aplica o `Caddyfile`, porque não recria o Caddy. O certificado fica no volume `caddy_data`.

1. Junte o branch e faça o deploy normal:

   ```bash
   cd /root/leguas
   git merge --ff-only fix/media-privada
   git push origin main
   cd production && ./update.sh
   ```

2. Recrie o Caddy:

   ```bash
   docker compose up -d --force-recreate --no-deps caddy
   ```

3. Confirme que um ficheiro privado pede login e que `/health/` responde 200.

## Rollback

1. Altere `PERMISSIONS_ENFORCE=0` no `.env`. Isto desliga também as permissões das páginas.
2. Execute `docker compose up -d web`.

## Testado

Caddy 2.11.4 real com Django: 16 cenários, incluindo nomes com espaços e acentos, tentativa de `../`, outro motorista, outra frota e URL assinado.

**Não testado:** a app do motorista real. Se guardar `package_image` por mais de 24 horas, a imagem deixa de abrir até voltar a pedir os dados à API.
