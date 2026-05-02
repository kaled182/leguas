const fs = require('fs');
const path = 'dist/config.js';
let content = fs.readFileSync(path, 'utf8');
content = content.replace(
  /createOptions\s*:\s*\{/,
  'createOptions: { autoClose: 0, deviceSyncTimeout: 0,'
);
fs.writeFileSync(path, content);
console.log('Patch autoClose:0 aplicado com sucesso');
