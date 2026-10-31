# Portais — /driversapp/portal/, /settlements/empresas/<id>/portal/

## Resumo
Os 2 portais usam agora um layout único, `brand/portal.html`, com CSS compilado, Poppins e logótipo novo. O Tailwind por CDN e a fonte Inter saíram. Os dados e as permissões não mudam.

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Estado |
|---|---|---|---|---|
| 1 | Lógica | Alto | Perfil da frota: `taxa_iva` saía como `23,00` num campo `number`. O campo abria vazio e guardar gravava IVA 0 (`views_fleet_portal.py:511`) | Corrigido na página. **Dados de produção por verificar** |
| 2 | Lógica | Alto | O preço por pacote por omissão tinha o mesmo defeito. Guardar deixava-o sem valor | Corrigido. **Dados de produção por verificar** |
| 3 | Lógica | Baixo | Fluxo de caixa: saldo inicial com o mesmo defeito | Corrigido |
| 4 | Visual | Médio | Separadores só com ícone em telemóvel | O texto fica sempre visível |
| 5 | Responsivo | Médio | Mini indicadores sobrepostos e nome do portal por cima do logótipo em telemóvel | Corrigido |
| 6 | Código | Baixo | Alpine carregado 2 vezes no `_app_ui.html` | Corrigido |

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Cabeçalho do motorista e da frota sem herói, com `lf-page-header` |
| 2 | Separadores `lf-tabs`, que quebram em linhas para o menu Operação não ficar cortado |
| 3 | Cartões roxos passam a `lf-kpi` e botões a `lf-btn` |
| 4 | Moeda e percentagem no formato pt-PT. A barra de `reports.html` mantém o `%` para CSS |
| 5 | O tema usa `lf-theme` e aceita a chave antiga `management-theme` |

## Pendente
- O cartão "Contratos" do painel do motorista diz "Disponível em breve": a função não existe no portal.
- Os gráficos e o `_app_ui.html` mantêm cores próprias nos toasts.
- O portal segue o tema guardado, e já não a preferência do sistema, como o shell.

## Métricas
257 testes: as mesmas 4 falhas antigas de `main`, 0 regressões. 69 capturas (23 páginas × 3 modos), todas 200, 0 erros de consola e 0 scroll horizontal. `drivers_app.tests` mudou numa asserção: o texto passou de "PF" para "pré-fatura". Dados sintéticos. Sem teste com sessão real nem na app.
