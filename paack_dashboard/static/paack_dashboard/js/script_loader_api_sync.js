const form = document.getElementById("formSyncApiPaack");
const loader = document.getElementById("loader");

form.addEventListener("submit", function (e) {
  e.preventDefault(); // Prevenir o submit normal do formulário
  
  loader.classList.remove("hidden");
  
  // Limpar o log box antes de iniciar
  const logBox = document.getElementById("logBox");
  logBox.innerText = "";
  
  // Iniciar o streaming de status
  fetch("/paackos/real-time-sync-status/")
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) {
            // Sincronização finalizada
            setTimeout(() => {
              logBox.innerText += "\n🔄 Recarregando página em 3 segundos...\n";
              setTimeout(() => {
                window.location.reload();
              }, 3000);
            }, 1000);
            return;
          }
          
          // Adicionar novo conteúdo ao log
          logBox.innerText += decoder.decode(value);
          logBox.scrollTop = logBox.scrollHeight; // auto scroll
          read();
        }).catch(error => {
          console.error('Erro no streaming:', error);
          logBox.innerText += `\n❌ Erro no streaming: ${error.message}\n`;
        });
      }
      read();
    })
    .catch(error => {
      console.error('Erro na requisição:', error);
      logBox.innerText += `\n❌ Erro na requisição: ${error.message}\n`;
      // Esconder loader em caso de erro
      setTimeout(() => {
        loader.classList.add("hidden");
      }, 3000);
    });
});