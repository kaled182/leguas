# Módulos e páginas sem uso — levantamento

**Estado:** Fase 0.7. A classificação é **provisória**. Falta a contagem de produção.
**AVISO:** não remova nada com base neste ficheiro antes da aprovação da lista.

## 1. Evidência que falta

Execute estes passos no servidor. O comando só lê dados e mostra só contagens e datas.

**NOTA:** o comando ainda não está na imagem de produção. O passo 1 copia-o para o container. O próximo deploy apaga essa cópia, sem efeito nos dados.

1. Copie o comando para o container:

   ```bash
   cd /root/leguas-rebrand
   docker cp core/management/commands/usage_report.py leguas_web:/app/core/management/commands/usage_report.py
   ```

2. Execute o relatório:

   ```bash
   docker exec leguas_web python manage.py usage_report --json > docs/rebrand/dados/usage_report.json
   ```

3. Conte as visitas por URL:

   ```bash
   docker logs leguas_web 2>&1 | grep -oE '"(GET|POST) /[^ ?"]*' | sed -E 's#/[0-9]+#/N#g' | sort | uniq -c | sort -rn > docs/rebrand/dados/visitas.txt
   ```

**CUIDADO:** o passo 3 mostra só os pedidos desde o último deploy. O container é recriado em cada deploy. O projeto não tem registo de 90 dias. Por isso, o critério dos 90 dias do briefing não pode ser cumprido com os dados atuais.

## 2. Classificação provisória

| Candidato | Rotas | Modelos | Dependências | Classe provisória |
|---|---|---|---|---|
| Frota: Painel, Veículos, Manutenções, Incidentes | 12 | `Vehicle`, `VehicleAssignment`, `VehicleMaintenance`, `VehicleIncident` | Ver 3.1 | **Remover com cuidado** |
| Incidências, Performance de veículos, Custos de frota | 3 | Nenhum próprio | `analytics/views.py:15` importa modelos de frota | **Remover com cuidado**, junto com a Frota |
| Tarifas | parte de 13 | `PartnerTariff` | FK para `core.Partner`. Sem imports fora da app | **Remover**, se 0 registos |
| Calculadora de Preços | 1 | Nenhum próprio | Usa só tarifas e zonas da app `pricing` | **Remover**, junto com Tarifas |
| Zonas Postais | parte de 13 | `PostalZone` | `geozonas.ZonaGeo.postal_zone` (FK, `SET_NULL`), comando `seed_postal_zones` | **Remover com cuidado** |
| Contratos: Modelos, Por assinar, Assinados | 13 | `ContractTemplate`, `DriverContract`, `GeneratedContract` | Ver 3.2 | **Manter** |

### 3.1 Dependências da Frota

- `settlements.DriverClaim.vehicle_incident` é uma FK para `VehicleIncident`, com `SET_NULL` (`settlements/models.py:576`).
- `settlements/calculators/claim_processor.py:23` cria reclamações a partir de incidentes.
- `settlements/views.py:560` e `:758` usam `select_related("vehicle_incident")`.
- `settlements/templates/settlements/claim_detail.html:213` mostra o incidente.
- 2 FK para `drivers_app.DriverProfile`: `VehicleAssignment.driver` e `VehicleIncident.driver`.
- Sem signals e sem tarefas Celery.

**NOTA:** a Etapa A mantém os modelos. A FK de `DriverClaim` continua válida depois da remoção das páginas.

### 3.2 Por que Contratos fica

- `drivers_app/context_processors.py:58`, `ficha_views.py:278` e `central_views.py:69` leem estes modelos.
- `services_cp_pricing.py:37` e `services_hubs.py:30` leem `ContractSettings` e `HubZoneTariff`. Estes modelos definem preços por CP.
- A página "Assinados" sem registos não prova falta de uso. É preciso a contagem de `DriverContract` e `GeneratedContract`.

**AVISO:** `contracts.HubZoneTariff` é diferente de `pricing.PartnerTariff`. Remover "Tarifas" não pode tocar em `HubZoneTariff`, porque o cálculo de pagamentos a motoristas usa este modelo.

## 4. Candidatos novos, encontrados na Fase 0

| Candidato | Facto | Classe provisória |
|---|---|---|
| `/dashboard_v2/` e `dashboard_sidebar.html` | Página estática antiga, com 30 ligações, sem login. A página real é `/` | **Remover** |
| `/accounting/receitas/`, `/receitas/<pk>/`, `/despesas/`, `/despesas/<pk>/`, `/relatorios/` | Os 5 templates não existem. As rotas devolvem 500 | **Remover**, se as visitas forem 0 e o modelo estiver vazio |
| Tabelas `sorting_*` | Sem páginas desde 2026-10-30. Opção A em vigor | **Manter** até a contagem. Etapa B só com ordem |

## 5. Erros que apoiam a classificação

Estas rotas devolvem 500 quando existe 1 registo. Isto indica que a função não é usada em produção, mas não o prova.

| Rota | Erro | Local |
|---|---|---|
| `/fleet/vehicles/<pk>/` | `FieldError`: `start_date` não existe em `VehicleAssignment` | `fleet_management/views.py:93` |
| `/fleet/vehicles/<pk>/toggle-status/` | `NoReverseMatch`: `vehicle-detail` | `fleet_management/views.py:201` |
| `/fleet/incidents/` | `TypeError`: formato de hora aplicado a uma data | `fleet_management/templates/fleet_management/incident_list.html:111` |
| `/pricing/zones/<pk>/` | Filtro `selectattr` inválido | `pricing/templates/pricing/zone_detail.html:192` |
| `/pricing/tariffs/<pk>/` | `models.Decimal` não existe | `pricing/models.py:334` e `:419` |

## 6. Remoção em 2 etapas, depois da aprovação

1. **Etapa A, neste branch:** retire menu, URL, views, templates, formulários, JS, CSS e testes. Adicione redirect 301 para a página-mãe. Modelos e tabelas ficam.
2. **Etapa B, PR separado:** faça backup. Depois, crie a migration que apaga modelos e tabelas. Execute só com ordem explícita.
