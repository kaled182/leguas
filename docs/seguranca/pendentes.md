# Falhas de teste já existentes em `main`

**Estado:** pendente separado. Estas 4 falhas não são regressões. O commit `469a7d8` tem as mesmas falhas.

| # | Teste | Causa | Relação |
|---|---|---|---|
| 1 | `core.tests.PartnerModelTest.test_nif_normalization` | O teste usa `123456789` e a validação do modelo recusa o valor | Causa exata a confirmar |
| 2 | `pricing.tests.PartnerTariffModelTest.test_calculate_price` | `models.Decimal` não existe, em `pricing/models.py:334` e `:419` | B10, espera pelo `usage_report` |
| 3 | `settlements.test_reliable_sync...test_ficheiro_que_ja_nao_existe_fica_falhado_e_usa_o_anterior` | A confirmar | Sem bug associado |
| 4 | `settlements.test_reliable_sync...test_importa_o_mais_recente_por_hub_e_nao_repete` | A confirmar | Sem bug associado |

## Outros pendentes

- **Página pública de assinatura:** usa `settlements/base.html`, um layout interno.
- **Traceback em resposta:** `converter/views_geoapi.py:101` e `drivers_app/views.py:2816` ainda devolvem detalhes da exceção.
- **Limite por IP partilhado:** o limite por IP pode afetar motoristas na mesma rede do hub. Ajuste em `core/ratelimit.py`.
- **`folium_map.html`:** página sem view, com uma ligação partida a `driversmanager_manager`.
