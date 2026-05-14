// Patch pós-build do WPPConnect Server (dist/config.js).
//
// 1) autoClose:0 / deviceSyncTimeout:0 — evita que o browser feche
//    antes de o QR ser gerado.
// 2) webhook.url global — o WPPConnect chama este URL em cada evento
//    (incluindo 'qrcode'). É a forma fiável de entregar o QR ao
//    Django: o callWebHook é invocado directamente com o valor fresco,
//    contornando o bug de referência do clientsArray que faz os
//    endpoints /qrcode-session e /status-session ficarem presos em
//    INITIALIZING.
const fs = require('fs');
const path = 'dist/config.js';
let content = fs.readFileSync(path, 'utf8');

// 1) autoClose
content = content.replace(
  /createOptions\s*:\s*\{/,
  'createOptions: { autoClose: 0, deviceSyncTimeout: 0,'
);

// 2) webhook.url global
const webhookUrl =
  process.env.WPP_WEBHOOK_URL ||
  'http://web:8000/system/whatsapp/webhook/';
content = content.replace(
  /webhook\s*:\s*\{\s*url\s*:\s*null/,
  "webhook: { url: '" + webhookUrl + "'"
);

fs.writeFileSync(path, content);
console.log('Patch aplicado: autoClose:0 + webhook.url=' + webhookUrl);
