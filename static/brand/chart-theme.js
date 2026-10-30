// Tema dos gráficos: lê as cores de tokens.css.
(function () {
  if (!window.Chart) return;
  const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const fontFamily = 'Poppins, system-ui, sans-serif';
  Chart.defaults.font.family = fontFamily;
  Chart.defaults.color = token('--color-text-muted');
  Chart.defaults.borderColor = token('--color-border');
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.scales.category.ticks.maxRotation = 0;
  Chart.defaults.scales.category.ticks.autoSkip = true;
  window.lfChartColors = () => ({
    primary: token('--brand-orange'),
    secondary: token('--brand-purple-wing'),
    success: token('--success'),
    danger: token('--danger'),
    warning: token('--warning'),
    neutral: token('--neutral'),
  });
})();
