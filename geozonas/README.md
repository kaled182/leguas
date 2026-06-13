# Módulo GeoZonas

Catálogo de códigos postais (via **GeoAPI.pt**) e desenho de **zonas de entrega**
(Zona A/B/C/D) sobre um mapa interativo.

Substitui o antigo script `catalogar-cps` (força bruta de 1000 pedidos por prefixo)
por ingestão eficiente: **1 chamada `/cp/{CP4}` devolve todos os CP3 do prefixo**.

## O que tem

- **Modelos**: `Concelho`, `Freguesia` (polígono GeoJSON), `Localidade`,
  `CodigoPostal` (CP4-CP3, GPS), `ZonaGeo` (polígono desenhado, liga a `pricing.PostalZone`).
- **Catálogo** (`/geozonas/catalogo/`): pesquisa um CP / CP4 / localidade e identifica a zona.
- **Mapa** (`/geozonas/mapa/`): cadastrar área (CP4) → carregar pontos → desenhar
  polígono → ver os CPs lá dentro → guardar como Zona.
- **Ingestão**: comando `manage.py ingest_cp` + task Celery `geozonas.ingest_cp4`.

## Dependências

- `shapely` (point-in-polygon em Python puro — **não** usa GeoDjango/GDAL).
  Já está no `requirements.txt`; é preciso **rebuild da imagem web** para instalar.
- Chave GeoAPI: variável `GEOAPI_TOKEN` no `.env` (já configurada).

## Deploy em produção (servidor) — automático

O deploy é feito pelo script de atualização, que faz **tudo automaticamente**
(backup → `git pull origin main` → rebuild da imagem com o shapely → migrations →
recriar web + celery):

```bash
cd <projeto>/production
./update.sh
```

O `entrypoint.sh` corre `migrate` + `collectstatic` no arranque, por isso as tabelas
`geozonas_*` são criadas sozinhas. Não é preciso correr migrations à mão.

### Cadastrar áreas (códigos postais)

A única ação de dados é cadastrar os prefixos que queres. Duas formas:

- **Pela UI** (recomendado): no *Mapa de Códigos Postais* → cartão "Cadastrar área",
  escreve o CP4 (ex.: `4990`) e clica *Importar*. Corre em segundo plano (Celery).
- **Por comando**:
  ```bash
  docker exec leguas_web python manage.py ingest_cp 4990 --coords
  docker exec leguas_web python manage.py ingest_cp 4740 4900 --coords
  ```

> `--coords` faz 1 chamada extra por CP3 para obter o GPS (necessário para os pontos
> no mapa). Sem `--coords`, o catálogo funciona mas o mapa não tem pontos.

## Notas

- A GeoAPI **não devolve freguesia** no endpoint de CP — a freguesia/​polígonos
  virão por GPS reverso (`/gps/{lat},{lon}/base`) num passo de enriquecimento futuro.
- Limite premium GeoAPI: 10.000 pedidos/dia.
