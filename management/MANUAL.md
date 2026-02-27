# Manual de Manutenção da Interface - App Management

## Visão Geral

Este documento fornece orientações detalhadas sobre como manter, atualizar e estender a interface do aplicativo Management do sistema Léguas Monitoring. A interface foi completamente refatorada para utilizar Tailwind CSS, resultando em uma experiência de usuário moderna, responsiva e bem estruturada.

## Estrutura de Arquivos

```
management/
│
├── templates/
│   ├── management/
│   │   ├── base-dashboard.html      # Template base com sidebar e estrutura principal
│   │   ├── dashboard.html           # Dashboard principal
│   │   └── driversmanagement.html   # Interface de gerenciamento de motoristas
│   │
│   └── partials/                    # Componentes parciais reutilizáveis
│
├── static/
│   └── management/
│       ├── css/
│       │   ├── main.css             # Estilos customizados que complementam o Tailwind
│       │   └── ...
│       └── js/
│           ├── main.js              # JavaScript principal com funcionalidades compartilhadas
│           └── ...
│
└── MANUAL.md                        # Este manual
```

## Tecnologias Utilizadas

- **Tailwind CSS**: Framework CSS utilitário para design responsivo
- **Chart.js**: Para visualizações de dados 
- **Lucide Icons**: Biblioteca de ícones modernos
- **Django Templates**: Sistema de templates do Django

## Componentes Principais

### Base Dashboard (base-dashboard.html)

O template base proporciona a estrutura para todas as páginas do dashboard, incluindo:

- Sidebar navegável (desktop e mobile)
- Sistema de tema claro/escuro
- Cabeçalho com navegação e ações
- Área de conteúdo principal
- Sistema de notificações

#### Como usar:

```html
{% extends 'management/base-dashboard.html' %}

{% block title %}Título da Página{% endblock %}
{% block page_title %}Título Exibido no Cabeçalho{% endblock %}

{% block dashboard_content %}
  <!-- Seu conteúdo aqui -->
{% endblock %}

{% block page_js %}
  <!-- JavaScript específico da página -->
  <script>
    // Seu código aqui
  </script>
{% endblock %}
```

### Sistema de Notificações

O sistema de notificações pode ser usado em qualquer página através da função JavaScript `showNotification()`:

```javascript
showNotification('Mensagem de sucesso', 'success');
showNotification('Mensagem de erro', 'error');
showNotification('Aviso importante', 'warning');
showNotification('Informação', 'info');
```

## Personalização do Tema

### Cores

O tema foi projetado usando as cores padrão do Tailwind com foco em:

- **Primário**: Indigo (`indigo-600`, `#6366f1`)
- **Secundário**: Roxo (`purple-600`, `#9333ea`)
- **Sucesso**: Verde (`green-600`, `#16a34a`)
- **Erro**: Vermelho (`red-600`, `#dc2626`)
- **Alerta**: Amarelo (`yellow-600`, `#ca8a04`)
- **Info**: Azul (`blue-600`, `#2563eb`)

Para alterar as cores principais do tema, edite a configuração do Tailwind no `base.html`.

### Modo Escuro

O modo escuro é totalmente suportado e pode ser alternado pelo botão flutuante. A preferência do usuário é salva em `localStorage`. 

Classes Tailwind para suportar o modo escuro seguem o padrão `dark:{classe}`, por exemplo:

```html
<div class="bg-white dark:bg-gray-800 text-gray-900 dark:text-white">
  Conteúdo
</div>
```

## Padrões e Boas Práticas

### Nomenclatura de Classes

- Use classes Tailwind para estilização sempre que possível
- Para estilos personalizados complexos, crie classes em `main.css`
- Use o prefixo `custom-` para suas classes personalizadas

### Estrutura de Componentes

Divida interfaces complexas em componentes menores. Os componentes devem:

1. Ser semanticamente corretos (usar tags HTML apropriadas)
2. Ser responsivos (adaptar a diferentes tamanhos de tela)
3. Seguir uma hierarquia lógica

### JavaScript

- Código JavaScript está estruturado em módulos em `main.js`
- Funcionalidades específicas de página devem ser incluídas em `{% block page_js %}`
- Use funções autocontidas para recursos adicionais

### Responsividade

A interface é totalmente responsiva seguindo o padrão mobile-first do Tailwind:

- Design base: Mobile (< 640px)
- Classes `sm:`: Tablets pequenos (≥ 640px)
- Classes `md:`: Tablets (≥ 768px)
- Classes `lg:`: Desktops (≥ 1024px)
- Classes `xl:`: Telas grandes (≥ 1280px)
- Classes `2xl:`: Telas extra-grandes (≥ 1536px)

## Sidebar

### Estrutura 

A sidebar tem duas versões:

1. **Desktop**: Visível em telas MD ou maiores, pode colapsar para mostrar apenas ícones
2. **Mobile**: Painel deslizante que aparece quando o botão de menu é clicado

### Adicionando Links na Sidebar

Para adicionar novos links à sidebar, edite o arquivo `templates/partials/sidebar_links.html`:

```html
<a href="{% url 'management:nova_pagina' %}" 
  class="nav-link flex items-center gap-3 p-3 rounded-lg hover:bg-primary/10 transition-colors group">
  <i data-lucide="icon-name" class="w-5 h-5 text-gray-500 group-hover:text-primary flex-shrink-0"></i>
  <span class="sidebar-text font-medium">Nome do Link</span>
</a>
```

## Formulários

Os formulários seguem um padrão consistente:

```html
<div>
  <label for="campo_id" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
    Nome do Campo
  </label>
  <div class="mt-1">
    <input 
      id="campo_id" 
      name="campo_nome" 
      type="text" 
      class="appearance-none block w-full px-3 py-2 border border-gray-300 dark:border-gray-700 
             rounded-md shadow-sm placeholder-gray-400 dark:placeholder-gray-500 
             focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 
             dark:bg-gray-800 dark:text-white text-sm"
      placeholder="Placeholder"
    >
  </div>
</div>
```

## Cards

Os cards de métricas seguem o padrão:

```html
<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6 transition-all hover:shadow-md">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">Título do Card</h3>
    <div class="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
      <i data-lucide="icon-name" class="w-5 h-5 text-indigo-600 dark:text-indigo-400"></i>
    </div>
  </div>
  <div>
    <p class="text-2xl font-bold text-gray-900 dark:text-white">Valor</p>
    <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
      Descrição
    </p>
  </div>
</div>
```

## Tabelas

As tabelas seguem o padrão:

```html
<div class="overflow-x-auto">
  <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
    <thead class="bg-gray-50 dark:bg-gray-900/50">
      <tr>
        <!-- Cabeçalhos -->
        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          Cabeçalho
        </th>
      </tr>
    </thead>
    <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
      <!-- Linhas -->
      <tr class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">
          Conteúdo
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

## Modais

Os modais seguem o padrão:

```html
<div id="meuModal" class="fixed inset-0 z-50 hidden overflow-y-auto">
  <div class="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
    <!-- Backdrop -->
    <div class="fixed inset-0 transition-opacity" aria-hidden="true">
      <div class="absolute inset-0 bg-gray-500 dark:bg-gray-900 opacity-75"></div>
    </div>
    
    <!-- Modal -->
    <div class="inline-block align-bottom bg-white dark:bg-gray-800 rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
      <!-- Cabeçalho -->
      <div class="px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
        <h3 class="text-lg leading-6 font-medium text-gray-900 dark:text-white">Título do Modal</h3>
        <!-- Conteúdo -->
        <!-- ... -->
      </div>
      
      <!-- Rodapé com ações -->
      <div class="bg-gray-50 dark:bg-gray-700 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
        <button type="button" class="btn-primary">Confirmar</button>
        <button type="button" class="btn-secondary">Cancelar</button>
      </div>
    </div>
  </div>
</div>

<!-- JavaScript para controlar o modal -->
<script>
  document.getElementById('botaoAbrir').addEventListener('click', function() {
    document.getElementById('meuModal').classList.remove('hidden');
  });
  
  document.getElementById('botaoFechar').addEventListener('click', function() {
    document.getElementById('meuModal').classList.add('hidden');
  });
</script>
```

## Gráficos

Os gráficos são implementados usando Chart.js:

```html
<div class="h-80">
  <canvas id="meuGrafico"></canvas>
</div>

<script>
  const ctx = document.getElementById('meuGrafico');
  const isDarkMode = document.documentElement.classList.contains('dark');
  const textColor = isDarkMode ? '#e5e7eb' : '#4b5563';
  
  new Chart(ctx, {
    type: 'line',  // ou 'bar', 'pie', etc
    data: {
      labels: ['Label 1', 'Label 2'],
      datasets: [{
        label: 'Dados',
        data: [10, 20],
        backgroundColor: 'rgba(99, 102, 241, 0.2)',
        borderColor: 'rgba(99, 102, 241, 1)',
      }]
    },
    options: {
      // Opções do gráfico
      plugins: {
        legend: {
          labels: {
            color: textColor
          }
        }
      }
    }
  });
</script>
```

## Solução de Problemas

### Sidebar não está colapsando corretamente

Verifique:
1. Se o JavaScript está sendo carregado corretamente
2. Se todos os elementos HTML têm os IDs corretos
3. Se todas as classes Tailwind estão aplicadas corretamente

### Temas escuros não estão funcionando

Verifique:
1. Se o `darkMode: 'class'` está configurado no Tailwind
2. Se o JavaScript para alternar o tema está funcionando
3. Se todos os elementos têm classes `dark:` apropriadas

### Modais não funcionam corretamente

Verifique:
1. Se o JavaScript de controle está sendo executado
2. Se os IDs dos elementos correspondem aos usados no JavaScript
3. Se o z-index está configurado corretamente (modais devem ter z-index alto)

### Layout quebrando em dispositivos específicos

Verifique:
1. Se as classes responsivas estão aplicadas corretamente
2. Se flexbox ou grid estão configurados para adaptação
3. Se há overflow em algum elemento que pode causar quebra

## Atualizações Futuras

Ao fazer atualizações no futuro, mantenha estes princípios:

1. **Consistência**: Mantenha o mesmo estilo e padrão em toda a interface
2. **Responsividade**: Teste em diferentes tamanhos de tela
3. **Acessibilidade**: Use atributos ARIA e semântica HTML correta
4. **Performance**: Otimize imagens e minimize JavaScript
5. **Compatibilidade com tema escuro**: Sempre forneça alternativas para o tema escuro

## Conclusão

Esta interface foi projetada para ser elegante, funcional e fácil de manter. Ao seguir os padrões e diretrizes descritos neste documento, você ajudará a garantir que a interface permaneça consistente e de alta qualidade à medida que o aplicativo evolui.
