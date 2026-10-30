# Checklist de smoke test — depois do deploy

**AVISO:** se um passo falhar por 403 ou redirect inesperado, execute o rollback da secção final.

1. **Gestão:** entre em `/auth/login/`. Abra `/`, `/accounting/hub/` e `/system/users/`.
2. **Operador:** entre em `/auth/login/`. Abra `/` e `/driversapp/admin/central/`. Confirme que o bloco de pagamentos não aparece.
3. **Operador:** abra `/accounting/hub/`, `/pricing/tariffs/` e `/system/users/`. Confirme que o acesso é recusado.
4. **Motorista:** entre em `/auth/driver/`. Abra o portal, as faturas e os contratos.
5. **Frota:** entre em `/auth/empresa/`. Abra o portal e as faturas.
6. **App do motorista:** faça login, abra a lista e registe uma entrega de teste.
7. **Sincronização:** abra `/analytics/integrations/logs/`. Confirme que o último ciclo de sincronização terminou depois do deploy.
8. **Importação:** importe um ficheiro Cainiao em `/core/partners/<id>/`.
9. **Modo ecrã:** abra `/?tv=1`. Confirme a atualização automática ao fim de 60 s.
10. **ReliableMaps:** confirme que a exportação de zonas responde com a chave.

## Rollback

1. Altere `PERMISSIONS_ENFORCE=0` no `.env`.
2. Execute `docker compose up -d web`.
3. Repita os passos 1 e 6.
