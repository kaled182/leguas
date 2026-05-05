# ════════════════════════════════════════════════════════════════════
# Léguas Franzinas — Updater Sidecar
# ────────────────────────────────────────────────────────────────────
# Container minimalista que recebe pedidos HTTP para atualizar o stack:
#   - git pull no /repo (mount do host)
#   - docker compose build + up via socket Docker
# Sem dependências externas: só Python stdlib + git + docker-cli.
# ════════════════════════════════════════════════════════════════════
FROM alpine:3.19

RUN apk add --no-cache git docker-cli docker-cli-compose python3 ca-certificates tini

WORKDIR /app
COPY production/updater_server.py /app/updater_server.py

EXPOSE 9999

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python3", "-u", "/app/updater_server.py"]
