document.addEventListener('DOMContentLoaded', function () {
    // Ocultar loading após página carregar
    const loadingOverlay = document.getElementById('dashboard-loading');
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
    }

    // Inicializar dashboard
    if (typeof initDashboard === 'function') {
        initDashboard();
    }

    // Garantir que os ícones estão atualizados
    if (window.lucide) {
        lucide.createIcons();
    }

    // Criar gráfico de sucesso dos motoristas
    setTimeout(() => {
        createDriversSuccessChart();
    }, 100);

    // Adicionar loading ao mudar data
    const dateFilter = document.getElementById('date-filter');
    if (dateFilter) {
        dateFilter.addEventListener('change', function () {
            if (loadingOverlay) {
                loadingOverlay.classList.remove('hidden');
            }
        });
    }

    // Mostrar notificação de boas-vindas apenas uma vez por sessão
    if (!sessionStorage.getItem('dashboard-welcomed')) {
        setTimeout(() => {
            if (typeof showNotification === 'function') {
                showNotification('Dashboard carregado com sucesso!', 'success');
                sessionStorage.setItem('dashboard-welcomed', 'true');
            }
        }, 500);
    }
});

function createDriversSuccessChart() {
    const chartCanvas = document.getElementById('driversSuccessChart');
    if (!chartCanvas) {
        console.log('Canvas do gráfico não encontrado');
        return;
    }

    if (typeof Chart === 'undefined') {
        console.log('Chart.js não disponível');
        return;
    }

    // Obter dados do JSON
    const chartDataScript = document.getElementById('chart-data');
    let chartData;
    try {
        if (!chartDataScript) {
            console.log('Elemento chart-data não encontrado');
            return;
        }
        
        // Remover espaços e caracteres especiais antes de fazer o parse
        const jsonText = chartDataScript.textContent.trim();
        chartData = JSON.parse(jsonText);
    } catch (e) {
        console.error('Erro ao parsear dados do gráfico:', e);
        console.error('Texto problemático:', chartDataScript ? chartDataScript.textContent : "não disponível");
        return;
    }

    const driversData = chartData.driver_success_chart || [];
    console.log('Dados do gráfico:', driversData);

    if (driversData.length === 0) {
        console.log('Nenhum dado para o gráfico');
        chartCanvas.style.display = 'none';
        return;
    }

    // Preparar dados para o gráfico
    const labels = driversData.map(d => d.name);
    const successRates = driversData.map(d => d.success_rate.toFixed(2));

    console.log('Labels:', labels);
    console.log('Taxa de Sucesso:', successRates);

    // Detectar tema atual
    const isDark = document.documentElement.classList.contains('dark');
    const textColor = isDark ? '#e5e7eb' : '#4b5563';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

    // Configurar gráfico
    try {
        new Chart(chartCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Taxa de Sucesso (%)',
                        data: successRates,
                        backgroundColor: 'rgba(34, 197, 94, 0.8)',
                        borderColor: 'rgba(34, 197, 94, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: {
                            color: textColor,
                            maxRotation: 45
                        },
                        grid: {
                            color: gridColor
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            color: textColor,
                            callback: function (value) {
                                return value + '%';
                            }
                        },
                        grid: {
                            color: gridColor
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return context.parsed.y + '%';
                            }
                        }
                    }
                }
            }
        });
        console.log('Gráfico criado com sucesso!');
    } catch (error) {
        console.error('Erro ao criar gráfico:', error);
    }
}
