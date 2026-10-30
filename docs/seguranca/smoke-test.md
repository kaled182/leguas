# Checklist de smoke test — depois do deploy

**NOTA:** produção não tem Operadores. Crie um utilizador de teste `is_staff`, sem superuser, para os passos do Operador. Apague-o no fim.

**AVISO:** se um passo falhar por 403 ou redirect inesperado, execute o rollback da secção final.

1. **Gestão:** entre em `/auth/login/`. Abra `/`, `/accounting/hub/` e `/system/users/`.
2. **Operador:** entre em `/auth/login/`. Abra `/` e `/driversapp/admin/central/`. Confirme que o bloco de pagamentos não aparece.
3. **Operador:** abra `/accounting/hub/`, `/pricing/tariffs/` e `/system/users/`. Confirme que o acesso é recusado.
4. **Motorista:** entre em `/auth/driver/`. Abra o portal, as faturas e os contratos.
5. **Frota:** entre em `/auth/empresa/`. Abra o portal e as faturas.
**AVISO:** não registe entregas de teste. Uma entrega fictícia pode chegar à Cainiao como estado real.

6. **App do motorista:** faça login, abra a lista e abra um pacote. Não registe nada.
7. **Sincronização:** abra `/analytics/integrations/logs/`. Confirme que o último ciclo de sincronização terminou depois do deploy.
8. **Sincronização Reliable:** confirme que entram dados novos depois do próximo ciclo. O ciclo corre aos minutos 5 e 35, das 7h às 23h.
9. **Modo ecrã:** abra `/?tv=1`. Confirme a atualização automática ao fim de 60 s.
10. **ReliableMaps:** confirme que a exportação de zonas responde com a chave.
11. **Operador:** abra `/settlements/packages/` e faça uma pesquisa.
12. **Operador:** abra `/admin/`. Confirme que o acesso é recusado.
13. **Operador:** abra a ficha da Cainiao em `/core/partners/`. Confirme que vê o painel de Courier ID, sem contrato nem preços.

14. **Ficheiros:** abra um documento numa ficha de motorista com sessão. Depois, abra o mesmo URL numa janela anónima. Confirme que pede login.
15. **Logótipos:** confirme que aparecem nos PDF e nas páginas de login.

## Rollback

1. Altere `PERMISSIONS_ENFORCE=0` no `.env`.
2. Execute `docker compose up -d web`.
3. Repita os passos 1 e 6.
