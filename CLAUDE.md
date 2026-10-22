# Diretrizes do projeto Léguas Franzinas

## 1. Forma de escrever (ASD-STE100, ~80%)

Escreva todas as explicações, relatórios, commits e documentação em **Português Técnico Simplificado**.
A base é a norma ASD-STE100 (Simplified Technical English). Siga cerca de 80% das regras.

### Regras obrigatórias (os 80%)

1. Escreva frases curtas.
   - Instrução: no máximo 20 palavras.
   - Descrição: no máximo 25 palavras.
2. Escreva uma só instrução em cada frase.
3. Use a voz ativa. Exemplo: "O script faz o backup." Não: "O backup é feito pelo script."
4. Use o imperativo nos procedimentos. Exemplo: "Execute `./update.sh`."
5. Use um termo para um só significado. Não alterne sinónimos (ex.: "motorista" ≠ "estafeta" ≠ "condutor").
6. Escreva parágrafos com no máximo 6 frases.
7. Use listas numeradas para passos em sequência. Use listas com marcas para itens sem ordem.
8. Escreva avisos e notas **antes** do passo a que se referem.
   - **AVISO:** risco de perda de dados ou de falha em produção.
   - **CUIDADO:** risco de erro ou de dano menor.
   - **NOTA:** informação útil.
9. Não use gíria, metáforas nem expressões vagas ("talvez", "mais ou menos", "algumas coisas").
10. Diga o resultado com números e factos. Exemplo: "73 testes, 0 regressões." Não: "Os testes correram bem."

### Flexibilidade permitida (os 20%)

- Use nomes técnicos sem tradução: nomes de código, comandos, CVE, bibliotecas, termos sem equivalente comum (ex.: deploy, commit, migration, endpoint).
- Use uma frase mais longa quando a divisão tira o sentido. Faça isto raramente.
- Em conversas curtas (uma pergunta, uma resposta), aplique só as regras 1, 3, 5 e 10.

## 2. Diagrama sempre

Para cada tarefa de análise, correção, arquitetura ou decisão, crie um diagrama.

1. No terminal, use um bloco `mermaid` (fluxo, sequência ou estados).
2. Na resposta final em HTML, desenhe o diagrama em SVG inline.
3. Mostre o mecanismo real: componentes, fluxo de dados e o ponto onde está o problema ou a alteração.

## 3. Resposta final em HTML

No fim de cada tarefa não trivial, crie uma página HTML de decisão.
Publique a página como Artifact (privado) e dê a ligação ao utilizador. Mostre também um resumo curto no terminal.

A página tem estas secções, nesta ordem:

1. **Resumo** — 3 a 5 frases. O que aconteceu e o que foi feito.
2. **Diagrama** — SVG do mecanismo ou do fluxo.
3. **Factos** — tabela com versões, números, testes, riscos.
4. **Decisão necessária** — opções com prós, contras e a recomendação. Se não há decisão, escreva "Nenhuma decisão necessária".
5. **Próximos passos** — lista numerada. Cada passo tem um responsável e um comando ou ação concreta.
6. **Fontes** — ligações para as referências usadas.

## 4. Deploy e testes

- Deploy de produção: push para `main`, depois `cd /root/leguas/production && ./update.sh`.
- Testes: container isolado da imagem `leguas-web:production`, `--network none`, repositório em read-only, SQLite em memória.
- **AVISO:** Não use a base de dados de produção para testes.
