(function () {
  "use strict";

  // Elements may not exist on all pages — guard silently.
  var syncBtn = document.getElementById("syncButtonaApiPaack");
  var loader  = document.getElementById("loader");

  if (!syncBtn || !loader) return;

  var logBox = document.getElementById("logBox");

  syncBtn.addEventListener("click", function () {
    var csrfToken = syncBtn.dataset.csrf || "";
    var syncUrl   = syncBtn.dataset.syncUrl || "/paackos/sync/";

    syncBtn.disabled = true;
    loader.classList.remove("hidden");
    if (logBox) logBox.innerText = "";

    // POST to kick off the sync, then stream real-time status.
    fetch(syncUrl, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then(function () {
        return fetch("/paackos/real-time-sync-status/");
      })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }

        var reader  = response.body.getReader();
        var decoder = new TextDecoder();

        function read() {
          reader
            .read()
            .then(function (chunk) {
              if (chunk.done) {
                setTimeout(function () {
                  if (logBox) {
                    logBox.innerText += "\n🔄 Recarregando em 3 segundos...\n";
                  }
                  setTimeout(function () {
                    window.location.reload();
                  }, 3000);
                }, 1000);
                return;
              }
              if (logBox) {
                logBox.innerText += decoder.decode(chunk.value);
                logBox.scrollTop = logBox.scrollHeight;
              }
              read();
            })
            .catch(function (err) {
              console.error("Erro no streaming:", err);
              if (logBox) {
                logBox.innerText += "\n❌ Erro no streaming: " + err.message + "\n";
              }
              loader.classList.add("hidden");
              syncBtn.disabled = false;
            });
        }

        read();
      })
      .catch(function (err) {
        console.error("Erro na sincronização:", err);
        if (logBox) {
          logBox.innerText += "\n❌ Erro: " + err.message + "\n";
        }
        setTimeout(function () {
          loader.classList.add("hidden");
          syncBtn.disabled = false;
        }, 3000);
      });
  });
})();
