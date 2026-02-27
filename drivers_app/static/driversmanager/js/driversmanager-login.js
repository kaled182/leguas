// AJAX para login sem recarregar a página
        document.getElementById('driver-login-form').onsubmit = async function(e) {
            e.preventDefault();
            const form = e.target;
            const data = new FormData(form);
            const errorDiv = document.getElementById('login-error');
            errorDiv.classList.add('hidden');
            errorDiv.textContent = '';
            const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            try {
                const response = await fetch("", {
                    method: "POST",
                    headers: {
                        'X-CSRFToken': csrftoken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: data
                });
                const result = await response.json();
                if (result.status === 'success') {
                    window.location.href = "/drivers/manager/";
                } else {
                    errorDiv.textContent = result.message || "Erro ao autenticar";
                    errorDiv.classList.remove('hidden');
                }
            } catch {
                errorDiv.textContent = "Erro de conexão com o servidor.";
                errorDiv.classList.remove('hidden');
            }
        }