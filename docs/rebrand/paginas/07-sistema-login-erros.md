# Sistema, Ferramentas, Login e erros — /system/, /management/tools/, /converter/, /auth/, 403, 404, 500

## Resumo
Os 3 ecrãs de entrada usam agora o layout único `brand/auth.html`, com tokens e Poppins, sem Tailwind por CDN. As páginas 404 e 500 são novas. As páginas de Sistema e Ferramentas passam ao cabeçalho único.

## Erros encontrados
| # | Tipo | Gravidade | Descrição | Estado |
|---|---|---|---|---|
| 1 | Apresentação | Alto | `MESSAGE_TAGS` troca as etiquetas por classes CSS, por isso `'error' in m.tags` nunca era verdade. Erros apareciam a verde em 18 templates, incluindo o toast | Corrigido com `m.level` |
| 2 | Texto | Médio | Login com "Esqueceu sua senha?" (`href="#"`) e "Solicitar Acesso", sem função | Retirados, com o slider |
| 3 | Visual | Médio | Sem página 404 nem 500 da marca | Criadas. A 500 não usa tags |
| 4 | Visual | Médio | Conversor fora do shell, com Tailwind por CDN e ícones Bootstrap | Passou ao shell, com Lucide |
| 5 | Responsivo | Médio | Configurações e WhatsApp com scroll horizontal em telemóvel | Corrigido |

## Decisão técnica
Os blocos locais de mensagens ficam nas páginas de credenciais e de utilizadores. A nova palavra-passe vem numa mensagem. No toast, ela desapareceria em 5 segundos.

## O que foi feito
| # | Alteração |
|---|---|
| 1 | Login, Portal do motorista e Portal da frota com `lf-auth`, `lf-control` e `lf-btn` |
| 2 | O fluxo do código por WhatsApp mantém os mesmos elementos e o mesmo JavaScript |
| 3 | Erro de login fica visível no cartão, em vez de um toast de 5 segundos |
| 4 | Ligações entre os 3 ecrãs de entrada |
| 5 | Termos: palavra-passe, Utilizador, Ligação, Chaves de recuperação |
| 6 | Atualização, Chaves e Prazos SLA sem herói |

## Pendente
- `customauth/driver_dashboard.html`, `base_driver.html` e `customauth/base-login.html` não têm rota nem uso. Ficam para decisão de limpeza.
- `converter_table.html` não foi capturada: abre só depois de processar uma lista. A passagem automática não correu neste ficheiro, porque o regex ficou preso. Fiz a conversão à mão.
- As mensagens em `views.py` ainda dizem "password", "Username" e "Retry".
- `config.html` mantém os painéis por secção e os textos em Title Case.

## Métricas
254 testes: as mesmas 4 falhas antigas de `main`, 0 regressões. 48 capturas (16 páginas × 3 modos). As 404 e 403 são esperadas. Único erro de consola fora disso: `seed/documento.pdf`, ficheiro do seed. Dados sintéticos.
