document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM Carregado, inicializando gráfico");
    // Verificar se o elemento do gráfico existe
    const chartElement = document.getElementById('driversSuccessChart');
    console.log("Elemento do gráfico encontrado:", !!chartElement);
    if (!chartElement) return;

    // Obter dados do elemento JSON
    let chartData = [];
    try {
        const chartDataElement = document.getElementById('chart-data');
        if (chartDataElement) {
            // Remover possíveis espaços em branco e caracteres não imprimíveis
            const jsonText = chartDataElement.textContent.trim();
            console.log("Carregando dados JSON:", jsonText);
            
            // Sanitizar o texto antes de fazer o parse
            const jsonData = JSON.parse(jsonText);
            chartData = jsonData.driver_success_chart || [];
        }
    } catch (error) {
        console.error("Erro ao carregar dados do gráfico:", error);
        console.error("Texto JSON problemático:", chartDataElement ? chartDataElement.textContent : "elemento não encontrado");
        return;
    }

    console.log("Dados do gráfico carregados:", chartData);
    
    // Verificar se temos dados para exibir
    if (!chartData || chartData.length === 0) {
        console.warn("Sem dados para exibir no gráfico");
        return;
    }

    // Preparar dados para o gráfico
    const driverNames = chartData.map(driver => driver.name);
    const successRates = chartData.map(driver => parseFloat(driver.success_rate));
    const deliveryCounts = chartData.map(driver => driver.deliveries);
    const failCounts = chartData.map(driver => driver.fails);

// Limitar a 10 motoristas para melhor visualização
const top10Names = driverNames.slice(0, 10);
const top10Rates = successRates.slice(0, 10);
const top10Deliveries = deliveryCounts.slice(0, 10);
const top10Fails = failCounts.slice(0, 10);

// Criar o gráfico usando Chart.js
console.log("Criando o gráfico com os dados:", {
    names: top10Names,
    rates: top10Rates,
    deliveries: top10Deliveries,
    fails: top10Fails
});

const ctx = chartElement.getContext('2d');
try {
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: top10Names,
            datasets: [
                {
                    label: 'Taxa de Sucesso (%)',
                    data: top10Rates,
                    backgroundColor: 'rgba(52, 211, 153, 0.7)',
                    borderColor: 'rgb(16, 185, 129)',
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: 'y'
                },
                {
                    label: 'Entregas',
                    data: top10Deliveries,
                    backgroundColor: 'rgba(59, 130, 246, 0.5)',
                    borderColor: 'rgb(37, 99, 235)',
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: 'y1'
                },
                {
                    label: 'Falhas',
                    data: top10Fails,
                    backgroundColor: 'rgba(239, 68, 68, 0.5)',
                    borderColor: 'rgb(220, 38, 38)',
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8,
                        font: {
                            family: "'Inter', sans-serif"
                        }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Taxa de Sucesso (%)'
                    },
                    max: 100,
                    ticks: {
                        callback: function (value) {
                            return value + '%';
                        }
                    }
                },
                y1: {
                    beginAtZero: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Número de entregas'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
    console.log("Gráfico criado com sucesso");
} catch (error) {
    console.error("Erro ao criar o gráfico:", error);
}
});