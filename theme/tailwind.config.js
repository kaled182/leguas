// Build: docs/rebrand/04-design-system.md. Cores e medidas vêm de static/brand/tokens.css.
// Azuis, índigos e roxos passam a usar a escala da marca.
const brandScale = {
  50: '#F7F2FB', 100: '#EFE7F6', 200: '#DFCFEC', 300: '#C4A9D6', 400: '#9C78B0',
  500: '#7D5292', 600: '#6B3D7D', 700: '#4F2562', 800: '#3B1650', 900: '#2E0A3E', 950: '#1C0627',
};
// Cinzentos com a tonalidade da marca, até ao fundo do tema escuro.
const neutralScale = {
  50: '#FAF8FC', 100: '#F3EFF7', 200: '#E6DCF0', 300: '#D0C4DC', 400: '#A596B5',
  500: '#6E5A82', 600: '#584868', 700: '#4A2A5C', 800: '#2A1138', 900: '#1C0627', 950: '#140420',
};

module.exports = {
  darkMode: 'class',
  content: [
    '../templates/**/*.html',
    '../*/templates/**/*.html',
    '../static/js/**/*.js',
    '../static/brand/**/*.js',
    '../*/static/**/*.js',
    '../core/permissions.py',
    '../core/templatetags/**/*.py',
  ],
  // Classes montadas nos templates: lf-btn-{{ variant }}, lf-tone-{{ tone }}.
  safelist: [
    { pattern: /^lf-(btn|tone|skeleton)-/ },
    {
      pattern: /^(bg|text|border|from|to)-(gray|red|rose|amber|yellow|orange|green|emerald|teal|cyan|sky|blue|indigo|violet|purple)-(50|100|200|300|400|500|600|700|800|900)$/,
      variants: ['dark', 'hover'],
    },
    {
      pattern: /^(from|to|ring)-(red|amber|yellow|orange|emerald|cyan|blue|indigo|violet|purple)-(200|700|800|900)\/(20|50)$/,
      variants: ['dark'],
    },
    {
      pattern: /^(ring|text)-(rose|red|amber|emerald|teal|cyan|blue|indigo|violet|purple)-(500|600)$/,
      variants: ['focus', 'group-hover', 'dark:focus'],
    },
  ],
  theme: {
    extend: {
      fontFamily: { sans: ['Poppins', 'system-ui', 'sans-serif'] },
      colors: {
        brand: {
          purple: 'var(--brand-purple)',
          night: 'var(--brand-purple-night)',
          wing: 'var(--brand-purple-wing)',
          orange: 'var(--brand-orange)',
          'orange-dark': 'var(--brand-orange-dark)',
          lilac: 'var(--brand-lilac)',
          cream: 'var(--brand-cream)',
        },
        surface: { DEFAULT: 'var(--color-surface)', alt: 'var(--color-surface-alt)' },
        content: { DEFAULT: 'var(--color-text)', muted: 'var(--color-text-muted)' },
        edge: 'var(--color-border)',
        primary: brandScale, indigo: brandScale, violet: brandScale, purple: brandScale,
        fuchsia: brandScale, pink: brandScale, blue: brandScale, sky: brandScale,
        cyan: brandScale, teal: brandScale, gray: neutralScale, slate: neutralScale,
      },
      spacing: { sidebar: 'var(--sidebar-width)', 'sidebar-collapsed': 'var(--sidebar-width-collapsed)' },
    },
  },
  plugins: [],
}
