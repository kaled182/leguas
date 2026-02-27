document.addEventListener('DOMContentLoaded', function() {
    // Seletores dos modais
    const addModal = document.getElementById("addManualCorrectionModal");
    const subtractModal = document.getElementById("subtractManualCorrectionModal");
    
    // Seletor do preview de remoção
    const ordersToRemovePreview = document.getElementById("ordersToRemovePreview");
    const ordersCountSpan = document.getElementById("ordersCount");

    // Seletores dos formulários
    const addForm = document.getElementById("addManualForm");
    const subtractForm = document.getElementById("subtractManualForm");

    // Seletores dos botões que abrem os modais
    const openAddBtn = document.getElementById("openAddManualCorrectionModal");
    const openSubtractBtn = document.getElementById("openSubtractManualCorrectionModal");

    // Seletores das mensagens de feedback
    const addFormMessage = document.getElementById("addFormMessage");
    const subtractFormMessage = document.getElementById("subtractFormMessage");

    // Seletores dos spinners
    const addSpinner = document.getElementById("addSubmitSpinner");
    const subtractSpinner = document.getElementById("subtractSubmitSpinner");
    
    // Seletor do motorista para subtração
    const subtractDriverSelect = document.getElementById("subtract_driver_select");

    // Funções auxiliares
    function showModal(modal) {
        modal.classList.remove("hidden");
    }

    function hideModal(modal) {
        modal.classList.add("hidden");
        // Limpar formulário e mensagens ao fechar
        const form = modal.querySelector('form');
        const message = modal.querySelector('[id$="FormMessage"]');
        if (form) form.reset();
        if (message) {
            message.classList.add('hidden');
            message.querySelector('p').textContent = '';
        }
    }

    function showMessage(messageElement, text, isError = false) {
        const p = messageElement.querySelector('p');
        messageElement.classList.remove('hidden');
        p.textContent = text;
        p.className = `text-sm font-medium ${isError ? 'text-red-600' : 'text-emerald-600'}`;

        // Auto-hide success messages after 3 seconds
        if (!isError) {
            setTimeout(() => {
                messageElement.classList.add('hidden');
            }, 3000);
        }
    }

    function toggleSpinner(spinner, show) {
        spinner.classList.toggle('hidden', !show);
    }
    
    function refreshPage() {
        window.location.reload();
    }

    // Event Listeners para abrir modais
    openAddBtn.addEventListener("click", () => showModal(addModal));
    openSubtractBtn.addEventListener("click", () => showModal(subtractModal));

    // Event Listeners para fechar modais
    document.querySelectorAll('[data-modal-hide]').forEach(button => {
        button.addEventListener('click', () => {
            const modalId = button.getAttribute('data-modal-hide');
            hideModal(document.getElementById(modalId));
        });
    });

    // Fechar ao clicar no fundo escuro
    [addModal, subtractModal].forEach(modal => {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) hideModal(modal);
        });
    });

    // Função para verificar e carregar pedidos a serem removidos
    async function checkOrdersToRemove() {
        const date = document.getElementById('subtract_date').value;
        const driverId = subtractDriverSelect.value;
        const ordersContainer = document.getElementById('ordersToRemoveContainer');
        const ordersList = document.getElementById('ordersList');
        
        if (!date) {
            ordersContainer.classList.add('hidden');
            return;
        }
        
        try {
            const response = await fetch(`/manualorders_paack/check-manual-orders/?date=${date}&driver_id=${driverId}`);
            const data = await response.json();
            
            ordersContainer.classList.remove('hidden');
            ordersList.innerHTML = ''; // Limpa a lista atual
            
            if (data.orders && data.orders.length > 0) {
                data.orders.forEach(order => {
                    const orderElement = document.createElement('div');
                    orderElement.className = 'flex items-center px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-700/50';
                    orderElement.innerHTML = `
                        <label class="inline-flex items-center flex-1">
                            <input type="checkbox" name="orders[]" value="${order.id}" 
                                   class="form-checkbox h-4 w-4 text-red-600 rounded border-gray-300">
                            <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">
                                ${order.order_id} - ${order.status}
                                <span class="text-xs text-gray-500 dark:text-gray-400">
                                    (${order.created_at})
                                </span>
                            </span>
                        </label>
                    `;
                    ordersList.appendChild(orderElement);
                });
                
                // Habilitar o botão e mostrar a contagem
                const submitButton = subtractForm.querySelector('button[type="submit"]');
                submitButton.disabled = false;
                updateSelectedCount();
            } else {
                ordersList.innerHTML = `
                    <div class="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                        Nenhum registro encontrado para esta data.
                    </div>
                `;
                const submitButton = subtractForm.querySelector('button[type="submit"]');
                submitButton.disabled = true;
            }
        } catch (error) {
            console.error('Erro ao verificar pedidos:', error);
            ordersContainer.classList.add('hidden');
        }
    }
    
    // Função para atualizar a contagem de selecionados
    function updateSelectedCount() {
        const selectedCount = document.querySelectorAll('#ordersList input[type="checkbox"]:checked').length;
        document.getElementById('selectedCount').textContent = `${selectedCount} selecionados`;
        
        // Atualizar o estado do checkbox "Selecionar Todos"
        const totalCount = document.querySelectorAll('#ordersList input[type="checkbox"]').length;
        const selectAllCheckbox = document.getElementById('selectAllOrders');
        selectAllCheckbox.checked = selectedCount === totalCount;
        selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < totalCount;
    }
    
    // Event listener para o checkbox "Selecionar Todos"
    document.getElementById('selectAllOrders').addEventListener('change', function(e) {
        const checkboxes = document.querySelectorAll('#ordersList input[type="checkbox"]');
        checkboxes.forEach(checkbox => checkbox.checked = e.target.checked);
        updateSelectedCount();
    });
    
    // Event delegation para checkboxes individuais
    document.getElementById('ordersList').addEventListener('change', function(e) {
        if (e.target.type === 'checkbox') {
            updateSelectedCount();
        }
    });

    // Event listeners para atualizar preview
    document.getElementById('subtract_date').addEventListener('change', checkOrdersToRemove);
    subtractDriverSelect.addEventListener('change', checkOrdersToRemove);

    // Iniciar verificação de pedidos quando uma data for selecionada
    document.getElementById('subtract_date').addEventListener('change', checkOrdersToRemove);

    // Função para enviar dados ao backend
    async function submitManualCorrection(formData, isAddition) {
        const url = '/manualorders_paack/manual-correction/';
        formData.append('is_addition', isAddition);
        
        const messageElement = isAddition ? addFormMessage : subtractFormMessage;
        const modal = isAddition ? addModal : subtractModal;
        const spinner = isAddition ? addSpinner : subtractSpinner;
        
        try {
            toggleSpinner(spinner, true);
            
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Erro ao processar a requisição');
            }
            
            showMessage(messageElement, data.message);
            setTimeout(() => {
                hideModal(modal);
                refreshPage(); // Atualiza a página para mostrar as mudanças
            }, 2000);
            
            return {
                success: true,
                message: data.message
            };
        } catch (error) {
            return {
                success: false,
                message: error.message
            };
        }
    }

    // Função para atualizar o dashboard após uma correção
    function refreshDashboard() {
        // Recarregar a página com os parâmetros atuais
        window.location.reload();
    }

    // Manipuladores dos formulários
    addForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        toggleSpinner(addSpinner, true);

        try {
            const formData = new FormData(e.target);
            const response = await fetch('/manualorders_paack/manual-correction/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showMessage(addFormMessage, data.message || 'Adição manual registrada com sucesso!');
                setTimeout(() => {
                    hideModal(addModal);
                    window.location.reload();
                }, 2000);
            } else {
                showMessage(addFormMessage, data.error || 'Erro ao processar a requisição', true);
            }
        } catch (error) {
            console.error('Erro na adição manual:', error);
            showMessage(addFormMessage, 'Erro ao processar a requisição. Tente novamente.', true);
        } finally {
            toggleSpinner(addSpinner, false);
        }
    });

    subtractForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        toggleSpinner(subtractSpinner, true);

        const formData = new FormData(e.target);
        const result = await submitManualCorrection(formData, false);

        if (result.success) {
            showMessage(subtractFormMessage, 'Subtração manual registrada com sucesso!');
            setTimeout(() => {
                hideModal(subtractModal);
                refreshDashboard();
            }, 2000);
        } else {
            showMessage(subtractFormMessage, result.message, true);
        }
        
        toggleSpinner(subtractSpinner, false);
    });
});