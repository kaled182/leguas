# Manual de Manutenção - customauth

## Estrutura do App
- **Templates:**
  - `login.html`: Tela de login, clean, responsiva, minimalista.
  - `base_driver.html`: Base para páginas do motorista.
  - `driver_dashboard.html`: Dashboard do motorista, cards e tabela de entregas.
- **Estáticos:**
  - `css/auth.css`: Visual clean, responsivo, fácil de customizar.
  - `js/auth.js`: Validação de formulário, UX amigável.

## Boas Práticas
- Sempre use as classes `.btn` para botões e `.input` para campos.
- Mantenha o visual minimalista, evitando excesso de cores e bordas.
- Teste em desktop e mobile após qualquer alteração visual.

## Como adicionar funcionalidades
- Para novos campos, siga o padrão de classes e estrutura dos templates.
- Para novas validações, adicione funções no `auth.js`.
- Para novos estilos, adicione no `auth.css` e documente com comentários.

## Deploy e Estáticos
- Após alterações em arquivos estáticos, rode `python manage.py collectstatic`.
- Verifique se o caminho dos arquivos estáticos está correto nos templates.

## Acessibilidade
- Use sempre `label` para inputs.
- Garanta contraste suficiente para textos e botões.

## Suporte
- Dúvidas ou bugs: consulte a documentação nos comentários dos arquivos.
- Para manutenção avançada, siga o padrão de código limpo e comentado.
