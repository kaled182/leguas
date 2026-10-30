# Checklist de smoke test — depois do deploy

**AVISO:** se um passo falhar por 403 ou redirect inesperado, execute o rollback da secção final.

1. **Gestão:** entre em `/auth/login/`. Abra `/`, `/accounting/hub/` e `/system/users/`.
2. **Operador:** entre em `/auth/login/`. Abra `/` e `/driversapp/admin/central/`. Confirme que o bloco de pagamentos não aparece.
3. **Operador:** abra `/accounting/hub/`, `/pricing/tariffs/` e `/system/users/`. Confirme que o acesso é recusado.
4. **Motorista:** entre em `/auth/driver/`. Abra o portal, as faturas e os contratos.
5. **Frota:** entre em `/auth/empresa/`. Abra o portal e as faturas.
**AVISO:** não registe entregas de teste. Uma entrega fictícia pode chegar à Cainiao como estado real.

6. **App do motorista:** faça login, abra a lista e abra um pacote. Não registe nada.
7. **Sincronização:** abra `/analytics/integrations/logs/`. Confirme que o último ciclo de sincronização terminou depois do deploy.
**AVISO:** não use um ficheiro de teste. Importar altera dados reais.

8. **Importação:** confirme a importação só com a importação real do dia.
9. **Modo ecrã:** abra `/?tv=1`. Confirme a atualização automática ao fim de 60 s.
10. **ReliableMaps:** confirme que a exportação de zonas responde com a chave.
11. **Operador:** abra `/settlements/packages/` e faça uma pesquisa.
12. **Operador:** abra `/admin/`. Confirme que o acesso é recusado.

## Rollback

1. Altere `PERMISSIONS_ENFORCE=0` no `.env`.
2. Execute `docker compose up -d web`.
3. Repita os passos 1 e 6.
