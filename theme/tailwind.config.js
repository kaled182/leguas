// Build: docs/rebrand/04-design-system.md. Cores e medidas vêm de static/brand/tokens.css.
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
  safelist: [{ pattern: /^lf-(btn|tone|skeleton)-/ }],
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
      },
      spacing: { sidebar: 'var(--sidebar-width)', 'sidebar-collapsed': 'var(--sidebar-width-collapsed)' },
    },
  },
  plugins: [],
}
