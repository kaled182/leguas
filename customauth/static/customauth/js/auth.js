/**
 * auth.js - Funcionalidades de autenticação
 * Modernizado para trabalhar com Tailwind CSS
 * - Validação de formulário
 * - Feedback visual em tempo real
 * - UX aprimorada para desktop e mobile
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elementos do formulário
    const form = document.querySelector('form');
    const emailInput = document.getElementById('email_or_nif');
    const passwordInput = document.getElementById('password');
    const submitButton = document.querySelector('button[type="submit"]');
    
    // Classes Tailwind para estados dos campos
    const validClass = 'border-green-500 dark:border-green-500';
    const invalidClass = 'border-red-500 dark:border-red-500';
    const focusClass = 'ring-indigo-500 border-indigo-500';
    
    // Validação em tempo real
    if (emailInput) {
        emailInput.addEventListener('input', function() {
            validateField(this);
        });
        
        emailInput.addEventListener('blur', function() {
            validateField(this, true);
        });
    }
    
    if (passwordInput) {
        passwordInput.addEventListener('input', function() {
            validateField(this);
        });
        
        passwordInput.addEventListener('blur', function() {
            validateField(this, true);
        });
    }
    
    // Submissão do formulário
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!validateForm()) {
                e.preventDefault();
                showErrorMessage('Por favor, preencha todos os campos corretamente.');
                shakeButton();
                return false;
            }
            
            // Mostrar loading no botão
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.innerHTML = '<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Entrando...';
            }
        });
    }
    
     function closeModal() {
    document.getElementById('modal-messages').style.display = 'none';
    }

    // Fechar automaticamente após alguns segundos (opcional)
    setTimeout(() => {
        closeModal();
    }, 4000);

    /**
     * Valida um campo individual
     * @param {HTMLElement} field - Campo a ser validado
     * @param {boolean} showError - Se deve mostrar mensagem de erro
     */
    function validateField(field, showError = false) {
        // Remover classes anteriores de validação
        field.classList.remove(validClass, invalidClass);
        
        // Container da mensagem de erro
        let errorContainer = field.nextElementSibling;
        if (errorContainer && !errorContainer.classList.contains('error-message')) {
            errorContainer = null;
        }
        
        // Se não existir container de erro, criar um
        if (!errorContainer && showError) {
            errorContainer = document.createElement('p');
            errorContainer.classList.add('error-message', 'mt-1', 'text-sm', 'text-red-600', 'dark:text-red-400');
            field.parentNode.appendChild(errorContainer);
        }
        
        // Validar campo
        let isValid = true;
        let errorMessage = '';
        
        if (!field.value.trim()) {
            isValid = false;
            errorMessage = 'Este campo é obrigatório';
        } else if (field.id === 'email_or_nif') {
            // Validação para email ou NIF
            const isEmail = field.value.includes('@');
            
            if (isEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(field.value)) {
                isValid = false;
                errorMessage = 'Email inválido';
            } else if (!isEmail && !/^\d+$/.test(field.value)) {
                isValid = false;
                errorMessage = 'NIF inválido';
            }
        } else if (field.id === 'password' && field.value.length < 6) {
            isValid = false;
            errorMessage = 'A senha deve ter pelo menos 6 caracteres';
        }
        
        // Aplicar classe conforme validação
        if (field.value.trim()) {
            field.classList.add(isValid ? validClass : invalidClass);
        }
        
        // Mostrar ou ocultar mensagem de erro
        if (errorContainer) {
            if (!isValid && showError) {
                errorContainer.textContent = errorMessage;
                errorContainer.style.display = 'block';
            } else {
                errorContainer.style.display = 'none';
            }
        }
        
        return isValid;
    }
    
    /**
     * Valida todo o formulário
     * @returns {boolean} - Indica se o formulário é válido
     */
    function validateForm() {
        let isValid = true;
        
        // Validar email/NIF
        if (emailInput) {
            isValid = validateField(emailInput, true) && isValid;
        }
        
        // Validar senha
        if (passwordInput) {
            isValid = validateField(passwordInput, true) && isValid;
        }
        
        return isValid;
    }
    
    /**
     * Mostra uma mensagem de erro geral
     * @param {string} message - Mensagem de erro
     */
    function showErrorMessage(message) {
        // Procurar container de erro existente
        let errorContainer = document.querySelector('.form-error');
        
        // Se não existir, criar um
        if (!errorContainer) {
            errorContainer = document.createElement('div');
            errorContainer.classList.add('form-error', 'bg-red-100', 'dark:bg-red-900', 'border', 'border-red-400', 'dark:border-red-800', 'text-red-700', 'dark:text-red-200', 'px-4', 'py-3', 'rounded', 'mb-4');
            form.prepend(errorContainer);
        }
        
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
        
        // Esconder após 5 segundos
        setTimeout(() => {
            errorContainer.style.display = 'none';
        }, 5000);
    }
    
    /**
     * Efeito de shake no botão para feedback visual
     */
    function shakeButton() {
        if (submitButton) {
            submitButton.classList.add('animate-shake');
            setTimeout(() => {
                submitButton.classList.remove('animate-shake');
            }, 500);
        }
    }
    
    // Adicionar animação de shake ao Tailwind (inline)
    const style = document.createElement('style');
    style.innerHTML = `
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
            20%, 40%, 60%, 80% { transform: translateX(5px); }
        }
        .animate-shake {
            animation: shake 0.5s cubic-bezier(.36,.07,.19,.97) both;
        }
    `;
    document.head.appendChild(style);
});
