# Passagem final — páginas restantes

## Resumo
A captura global abriu 169 páginas. 20 páginas sem cabeçalho único foram tratadas, e o scroll em telemóvel desceu de 7 para 0.

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Cadastro público e completo com `brand/portal.html`, sem Tailwind por CDN, e acentos corrigidos |
| 2 | Novo motorista, Aprovar, Pedidos de alteração, Reclamações, Frotas subcontratadas |
| 3 | Painel financeiro, Faturas de clientes, Liquidações, ficha da fatura |
| 4 | Nova vista `/atencao/`, com contador no menu e 5 minutos de cache |
| 5 | 88 valores de moeda em JavaScript e Alpine passam a `lfEur` |

## Erro corrigido na passagem
Retirar `gradient-bg` deixou o botão "Próximo" branco sobre branco no cadastro completo. A captura detetou o erro. O botão ficou com `lf-btn-primary`, e um teste protege a página.

## Pendente
- `alert()`: 169 chamadas. Não troquei por toast, porque muitas vêm antes de um `reload` e a mensagem perdia-se.
- Faturação Cainiao fica fora, por decisão do utilizador.

## Métricas
261 testes, 0 regressões. 338 capturas, 0 erros reais.
