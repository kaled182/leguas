# Módulo GeoZonas — Mapa de Códigos Postais & Zonas de Entrega

> App Django `geozonas`. Cataloga códigos postais (via **GeoAPI.pt**) e permite
> desenhar/gerir **zonas de entrega** sobre um mapa interativo.
> URL: `/geozonas/mapa/` · Sidebar: **"Mapa de Códigos Postais"**.

## 1. Visão geral

Substitui um script externo (`catalogar-cps`) que fazia força bruta de ~1000
pedidos por prefixo. Aqui, **1 chamada `/cp/{CP4}`** traz todos os CP3 do prefixo,
e o módulo enriquece com GPS, contornos, freguesias e ferramentas de zonamento.

**Stack:** Django + MySQL 8 · Celery (Redis) · Leaflet + Leaflet.draw ·
`shapely` (point-in-polygon, **sem** GeoDjango/GDAL para manter a imagem leve).

## 2. Modelos (`geozonas/models.py`)

| Modelo | Descrição |
|---|---|
| `Concelho`, `Localidade` | Hierarquia administrativa. |
| `Freguesia` | Freguesia com `geojson` (polígono). |
| `CodigoPostal` | CP4-CP3, `latitude`/`longitude`, FK `localidade`/`freguesia`/`concelho`, `fonte`. unique (cp4, cp3). |
| `AreaCP4` | Contorno (divisas) da área de um CP4 (`poligono` GeoJSON, centro). |
| `ZonaGeo` | Zona desenhada: `nome`, `codigo` (slug), `cor`, `poligono` (GeoJSON), FK→`pricing.PostalZone`, FK→`drivers_app.DriverProfile`. |
| `IngestJob` | Progresso de uma importação (status, total, coords_feitas/falhadas, `percent`). |

Migrations: `0001_initial` · `0002_ingestjob` · `0003_areacp4`.
(O campo `geoapi_token` da chave fica em `system_config.SystemConfiguration`,
migration `system_config/0010`.)

## 3. Ingestão (GeoAPI) — `geozonas/services/`

- `geoapi.py` — `GeoAPIClient`: header `X-API-Key`, backoff/aviso em 429.
  - Chave resolvida por `resolver_api_key()`: **SystemConfiguration → `.env` GEOAPI_TOKEN**.
  - Quota lida dos cabeçalhos `RateLimit-*` e guardada em cache Redis
    (`_capturar_quota`/`get_quota`) a cada chamada (custo zero).
  - `consultar_cp4`, `consultar_cp`, `gps_reverso`, `consultar_freguesias`.
- `ingest.py`:
  - `ingest_cp4(cp4, com_coordenadas, forcar_coords)` — 1 chamada bulk cria/atualiza
    todos os CP3; guarda `AreaCP4` (contorno); ingere as **freguesias** do(s)
    concelho(s); 2º passo de **coordenadas em paralelo** (ThreadPool 8) — por
    defeito só busca o **GPS em falta** (poupa tokens; `forcar_coords` força tudo).
  - `preencher_coordenadas_em_falta(cp4)` — só os CP3 sem GPS, sem a chamada bulk.
  - `atribuir_freguesias(cp4s)` — point-in-polygon (shapely) liga cada CP à sua freguesia.
- `espacial.py` — `cps_dentro_poligono(geometry, cps)` (Polygon/MultiPolygon).
- Tasks Celery (`tasks.py`): `geozonas.ingest_cp4`, `geozonas.coords_faltam`.
- Comando: `python manage.py ingest_cp 4990 --coords [--forcar]`.

## 4. Frontend (`templates/geozonas/mapa.html`)

Camadas Leaflet: `pontosLayer` (CPs), `freguesiaLayer` (fronteiras finas, toggle
ON por defeito, **só as freguesias do CP4**), `zonasLayer` (zonas guardadas),
`drawnItems` (desenho/edição). As camadas de fundo são `interactive:false` para
**não bloquearem o editor de desenho**.

**Carregar/filtrar:** por CP4 (auto-desenha ao selecionar), por **HUB Cainiao**
(chips por CP4, multi-seleção), múltiplos CP4.

**Zonas — criar/editar/apagar:**
- Criar: desenho livre · "Criar zona deste CP4" · "Criar zona do HUB".
- Painel "Zonas guardadas": 🎨 cor · ✎ renomear · ✐ **editar forma** (arrastar
  vértices via Leaflet.draw) · 🗑 apagar.

**Config/Status na página:** badge de **quota** (`X/10000 · reinicia em Nh`) +
secção **chave GeoAPI** (admin: inserir/atualizar/remover, encriptada).

## 5. Endpoints (`geozonas/urls.py`)

| URL | Método | Função |
|---|---|---|
| `mapa/`, `catalogo/` | GET | Páginas. |
| `api/cps/` | GET | Pontos GeoJSON por `cp4`(s)/`hub_id` + meta (completude). |
| `api/freguesias/` | GET | Fronteiras das freguesias do CP4/HUB. |
| `api/selecionar/` | POST | CPs dentro de um polígono. |
| `api/zonas/` `…/criar/` `…/from-cp4s/` `…/from-hub/` `…/update/` `…/delete/` | GET/POST | Zonas: listar, criar, editar (nome/cor/forma), apagar. |
| `api/hubs/` | GET | HUBs Cainiao + CP4 (`settlements.CainiaoHub`). |
| `api/ingest/` `…/coords-faltam/` `…/status/` `…/active/` | POST/GET | Importar, preencher GPS, progresso. |
| `api/quota/` `api/geoapi-key/` | GET/POST | Quota e chave GeoAPI. |

## 6. Integração com HUBs

HUBs vêm de `settlements.CainiaoHub` (+ `CainiaoHubCP4`), geridos em
`/core/partners/`. O mapa filtra por HUB e cria uma zona com o MultiPolígono das
divisas dos seus CP4.

## 7. Operação / Deploy

- Deploy: `./update.sh` (entrypoint corre migrations).
- **Re-importar** os CP4 uma vez para obter contorno + freguesias + ligação
  CP→freguesia (barato: só busca o que falta).
- Quota GeoAPI: 10.000 pedidos/dia (chave premium).

## 8. Pendente / roadmap

- **UX:** mapa fullscreen + painéis flutuantes; chave GeoAPI atrás de ⚙️; clique
  na freguesia → "Criar zona mágica".
- **Qualidade de cobertura:** "CPs sem zona" (órfãos) e deteção de **sobreposição**.
- **Modo Triagem (Sorting):** barra de scan (CP7) → zoom + cor da zona + motorista.
- **Cheat sheet PDF** por HUB.
- **Integração:** ligar `ZonaGeo` à `pricing.PostalZone`/`route_allocation`;
  auto-atribuição de pacotes via point-in-polygon (signal) → `zona_id`.

---
_Memória viva do projeto: ver `project_geozonas_module` nas memórias do Claude._
