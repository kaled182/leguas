/* Gerador de contrato único (por hub/CP) e de aditivo — Léguas Franzinas.
 *
 * Texto: geradores em uso (gerador_contrato_Viana_1, gerador_contrato_Aveiro,
 * gerador_aditivo_entregas). O contrato único junta os dois:
 *   - corpo comum (16 cláusulas);
 *   - hub(s) e CP no Anexo I (uma secção por hub);
 *   - pagamento pelas regras do hub principal;
 *   - caução por regime: semanal = retenção rotativa (Viana),
 *     mensal = caução fixa (Aveiro).
 * Os dados vêm de window.GEN (json_script no template).
 */
(function () {
const GEN = JSON.parse(document.getElementById("gen-data").textContent);
const $ = id => document.getElementById(id);
const LOGO = GEN.logo;
const WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"];

function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function eur(n) { return Number(n).toFixed(2).replace(".", ",") + " €"; }
function fdate(v) {
  if (!v) return "";
  const m = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const d = new Date(v + "T12:00:00");
  return d.getDate() + " de " + m[d.getMonth()] + " de " + d.getFullYear();
}
function bl(v, w) {
  const t = (v || "").trim();
  return '<span class="bl" style="min-width:' + w + 'mm">' + (t ? esc(t) : "&nbsp;") + '</span>';
}
function val(id) { const el = $(id); return el ? el.value : ""; }
function num(id, dflt) { const v = +val(id); return isNaN(v) || val(id) === "" ? dflt : v; }

function mhead(sec) {
  return '<div class="mhead"><div class="l"><img src="' + LOGO + '">' +
    '<div class="brand">LÉGUAS<span class="b2"><br>FRANZINAS</span></div></div>' +
    '<div class="r">' + sec + '</div></div>';
}
function dfoot(label, n, total) {
  const minuta = $("c_minuta").checked ? ' · <span style="color:#b23a30">Minuta — sujeita a validação jurídica</span>' : '';
  return '<div class="dfoot"><div><span class="strong">Léguas Franzinas — Unipessoal, Lda.</span> · NIPC 517307243 · ' + label + minuta + '</div><div>' + n + ' / ' + total + '</div></div>' +
    '<div class="rubr">Rubricas<span class="rl"></span><span class="rl"></span></div>';
}

function idPrestador(full) {
  const tipo = val("g_tipo");
  if (tipo === "singular") {
    if (!full) {
      return bl(val("g_nome"), 70) + ' (adiante, «2.º Outorgante» ou «Prestador»), pessoa singular, titular do documento de identificação n.º ' + bl(val("g_docnum"), 32) +
        ', NIF ' + bl(val("g_nif"), 26) + ', com morada em ' + bl(val("g_morada"), 86) + ';';
    }
    return bl(val("g_nome"), 70) + ' (adiante, «2.º Outorgante» ou «Prestador»), pessoa singular, titular de ' +
      esc(val("g_doctipo")) + ' n.º ' + bl(val("g_docnum"), 32) + ', válido até ' + bl(fdate(val("g_docval")), 34) +
      ', NIF ' + bl(val("g_nif"), 26) + ', com morada em ' + bl(val("g_morada"), 86) +
      ', titular da carta de condução n.º ' + bl(val("g_carta"), 30) + ', emitida por ' + bl(val("g_cartapais"), 26) +
      ', válida até ' + bl(fdate(val("g_cartaval")), 34) + ', contacto ' + bl(val("g_tel"), 26) + '.';
  }
  let t = bl(val("g_nome"), 70) + ' (adiante, «2.º Outorgante» ou «Prestador»), pessoa coletiva, NIPC ' + bl(val("g_nif"), 26) +
    ', com sede em ' + bl(val("g_morada"), 86) + ', neste ato representada por ' + bl(val("g_repsoc"), 52) +
    ', NIF ' + bl(val("g_repsocnif"), 26) + ', na qualidade de gerente, com poderes para o ato';
  if (!full) return t + ';';
  return t + ', contacto ' + bl(val("g_tel"), 26) +
    '. Motorista habitual titular da carta de condução n.º ' + bl(val("g_carta"), 30) + ', emitida por ' + bl(val("g_cartapais"), 24) + ', válida até ' + bl(fdate(val("g_cartaval")), 32) + '.';
}

function toggleTipo() {
  const tipo = val("g_tipo");
  if ($("box_singular")) $("box_singular").style.display = tipo === "singular" ? "" : "none";
  $("box_sociedade").style.display = tipo === "sociedade" ? "" : "none";
  $("lb_nome").textContent = tipo === "sociedade" ? "Denominação social" : "Nome completo";
  $("lb_nif").textContent = tipo === "sociedade" ? "NIPC" : "NIF";
}

/* ═══════════════════════ CONTRATO ÚNICO ═══════════════════════ */

function buildZoneList() {
  let h = "";
  GEN.hubs.forEach(hub => {
    const regs = [hub.allows_monthly ? "mensal" : null, hub.allows_weekly ? "semanal" : null].filter(Boolean).join(" e ");
    h += '<div class="hubbox" data-hub="' + hub.id + '">' +
      '<label class="hn"><input type="radio" name="primary" value="' + hub.id + '"' + (hub.id === GEN.primary_hub_id ? " checked" : "") + '> ' + esc(hub.name) +
      ' <span style="font-weight:400;font-size:10px;color:#c9b8d9">(principal)</span></label>' +
      '<div class="ht">' + (hub.has_terms ? 'Aceita ' + regs + ' · mensal pago ' + esc(hub.monthly_text) : '<span style="color:#ffb27a">Sem condições configuradas</span>') + '</div>';
    hub.cps.forEach(cp => {
      const priced = cp.p !== null;
      h += '<label class="zonerow"><input type="checkbox" class="zck" data-hub="' + hub.id + '" data-cp="' + cp.cp + '"' +
        (cp.checked ? " checked" : "") + (priced ? "" : " disabled") + '>' +
        '<span class="cpn">' + cp.cp + '</span><span class="zn">' + esc(cp.z || "") + '</span>' +
        '<span class="esc">' + (priced ? (cp.esc ? cp.esc + ' · ' : '') + eur(cp.p) + (hub.allows_weekly ? '/' + eur(cp.s) : '') : 'sem tarifa') + '</span></label>';
    });
    h += '</div>';
  });
  $("zonelist").innerHTML = h;
}

function selection() {
  const byHub = {};
  document.querySelectorAll(".zck").forEach(c => {
    if (!c.checked) return;
    (byHub[c.dataset.hub] = byHub[c.dataset.hub] || []).push(c.dataset.cp);
  });
  const hubs = GEN.hubs.filter(h => byHub[h.id]).map(h => ({
    hub: h, cps: h.cps.filter(cp => byHub[h.id].includes(cp.cp)),
  }));
  const pr = document.querySelector('input[name="primary"]:checked');
  let primary = hubs.find(x => pr && String(x.hub.id) === pr.value);
  if (!primary && hubs.length) primary = hubs[0];
  return { hubs, primary: primary ? primary.hub : null };
}

function allowedRegimes(sel) {
  if (!sel.hubs.length) return ["MENSAL", "SEMANAL"];
  return ["MENSAL", "SEMANAL"].filter(r => sel.hubs.every(x => r === "MENSAL" ? x.hub.allows_monthly : x.hub.allows_weekly));
}

function renderContrato() {
  toggleTipo();
  $("s_minimo").style.display = $("c_minimo").checked ? "" : "none";
  const sel = selection();
  const allowed = allowedRegimes(sel);
  ["MENSAL", "SEMANAL"].forEach(r => {
    const el = $(r === "MENSAL" ? "r_padrao" : "r_semanal");
    el.disabled = !allowed.includes(r);
    if (el.disabled && el.checked) { const other = $(r === "MENSAL" ? "r_semanal" : "r_padrao"); if (!other.disabled) other.checked = true; }
  });
  const regime = $("r_semanal").checked ? "SEMANAL" : "MENSAL";
  const P = sel.primary || GEN.hubs[0] || {};
  const warns = [];
  if (!sel.hubs.length) warns.push("Selecione pelo menos um CP.");
  if (!allowed.length) warns.push("Os hubs selecionados não têm um regime em comum.");
  if (GEN.driver.regime && GEN.driver.regime !== regime) warns.push("A ficha tem o regime " + GEN.driver.regime.toLowerCase() + "; o contrato está em " + regime.toLowerCase() + ".");
  sel.hubs.forEach(x => { if (!x.hub.has_terms) warns.push("O hub " + x.hub.name + " não tem condições de contrato configuradas."); });
  $("warns").innerHTML = warns.map(w => '<div class="warn">' + esc(w) + '</div>').join("");

  const V = {
    conf: val("v_conf") || "22:00", saida: val("v_saida") || "10:00", resp: val("v_resp") || "24",
    perda: num("v_perda", 50), teto: num("v_teto", 0), dano: num("v_dano", 15), local: num("v_local", 5),
    noshow: num("v_noshow", 50), dev: num("v_dev", 30), aviso: num("v_aviso", 15), liq1: num("v_liq1", 45), liq2: num("v_liq2", 60),
    cauc: num("v_cauc", 3), matur: num("v_matur", 28), caucfix: num("v_caucfix", 300),
    diapag: WEEKDAYS[P.weekly_payday || 1], lag: P.weekly_lag_weeks || 4,
    mmode: P.monthly_mode || "DAYS_AFTER_CLOSE", mval: P.monthly_value || 30,
    min: num("v_min", 60), minlim: num("v_minlim", 50), minpct: val("v_minpct") || "100%",
  };
  const dass = fdate(val("g_dass")), dini = fdate(val("g_dini"));
  const dur = val("g_dur") || "12";
  const local = val("g_local") || P.signing_place || "Esposende";
  const rep = val("g_rep");
  const temC = sel.hubs.some(x => x.cps.some(c => c.esc === "C"));
  const nRows = sel.hubs.reduce((a, x) => a + x.cps.length + 1, 0);
  const SPLIT = nRows >= 5 || $("c_minimo").checked;
  const TOTAL = SPLIT ? 7 : 6;
  const LABEL = "Contrato de Prestação de Serviços";

  const hubTxt = sel.hubs.length === 1
    ? 'no hub ' + esc(sel.hubs[0].hub.name) + (sel.hubs[0].hub.address ? ' (' + esc(sel.hubs[0].hub.address) + ')' : '')
    : 'no hub indicado no Anexo I para cada zona';

  const monthlyDesc = V.mmode === "DAY_OF_NEXT_MONTH"
    ? 'o apuramento é mensal e fecha no último dia de cada mês; o Prestador verifica o extrato e emite a fatura, sendo o pagamento de todos os volumes entregues entre o dia 1 e o último dia do mês efetuado de uma vez no <b>dia ' + V.mval + ' do mês seguinte</b> (a título de exemplo: o que entregas de 1 a 31 de agosto, recebes de uma vez no dia ' + V.mval + ' de setembro)'
    : 'o apuramento junta todas as entregas do mês e fecha no último dia; o pagamento é único e a fatura correspondente é paga no prazo de <b>' + V.mval + ' dias</b> após a sua emissão (a título de exemplo: apuramento de setembro, faturado no início de outubro, pago a 1 de novembro)';
  const regDesc = regime === "SEMANAL"
    ? 'Regime <b>Semanal</b> — pagamento semanal, toda a ' + esc(V.diapag) + ', nos termos da Cláusula 7.ª, com o valor da coluna «Semanal» do Anexo I.'
    : 'Regime <b>Mensal</b> — ' + monthlyDesc + ', com o valor da coluna «Mensal» do Anexo I.';

  // ================= PÁGINA 1 =================
  const p1 = '<div class="a4"><div class="pagepad">' + mhead("Contrato · Condições Gerais") +
    '<div class="doctitle"><div class="kk">Prestação de serviços de transporte e distribuição</div><h1>Contrato de Prestação de Serviços</h1></div>' +
    '<div class="ct">' +
    '<p><b>Entre:</b></p>' +
    '<div class="idgrid"><b>LÉGUAS FRANZINAS — UNIPESSOAL, LDA.</b> (adiante, «1.º Outorgante»), pessoa coletiva n.º 517307243, com sede na Rua Padre Giesteira, n.º 225, Apart. 55, 4740-283 Esposende, com o capital social de 10.500,00 €, neste ato representada por ' + bl(rep, 50) + ', na qualidade de gerente, com poderes para o ato;</div>' +
    '<p><b>E:</b></p>' +
    '<div class="idgrid">' + idPrestador(true) + '</div>' +
    '<p>é livremente e de boa-fé celebrado o presente <b>Contrato de Prestação de Serviços</b>, ao abrigo do disposto nos artigos 1154.º e seguintes do Código Civil, que se rege pelas cláusulas seguintes e pelos <b>Anexo I (Condições Particulares)</b> e <b>Anexo II (Protocolo de Entrega)</b>, que dele fazem parte integrante:</p>' +
    '<div class="cl">Cláusula 1.ª — Objeto</div>' +
    '<p class="par">O 2.º Outorgante prestará ao 1.º Outorgante, como profissional por conta própria, serviços de transporte e distribuição de mercadorias de pequeno volume (entregas ao domicílio, recolhas e devoluções), na(s) zona(s) de código postal identificada(s) no Anexo I.</p>' +
    '<div class="cl">Cláusula 2.ª — Autonomia e independência</div>' +
    '<p class="par"><b>1.</b> Os serviços são prestados com plena autonomia técnica e organizativa, mediante a utilização de viatura ligeira de mercadorias própria do Prestador' + (val("g_matr").trim() ? ' (matrícula(s) ' + bl(val("g_matr"), 34) + ')' : '') + ', telemóvel e demais meios próprios.</p>' +
    '<p class="par"><b>2.</b> O Prestador não fica sujeito a exclusividade, podendo prestar serviços a quaisquer terceiros, desde que tal não comprometa serviços já confirmados nos termos da Cláusula 3.ª.</p>' +
    '<p class="par"><b>3.</b> As partes reconhecem expressamente que o presente contrato não configura contrato de trabalho nem cria qualquer relação de subordinação jurídica, não conferindo direito a retribuição fixa, férias, subsídios ou quaisquer prestações de natureza laboral.</p>' +
    '<div class="cl">Cláusula 3.ª — Oferta e aceitação de serviços</div>' +
    '<p class="par"><b>1.</b> O 1.º Outorgante comunica ao Prestador, no dia anterior, pelos canais acordados (aplicação ou mensagem escrita), a disponibilidade de rota(s) para o dia seguinte.</p>' +
    '<p class="par"><b>2.</b> O Prestador é livre de aceitar ou recusar cada oferta. A aceitação deve ser comunicada por escrito até às <b>' + esc(V.conf) + '</b> do dia da oferta; a ausência de resposta equivale a recusa.</p>' +
    '<p class="par"><b>3.</b> A recusa ou não resposta não gera qualquer penalidade nem produz efeito nas ofertas futuras, que continuam a ser feitas segundo critérios objetivos de zona e capacidade.</p>' +
    '<p class="par"><b>4.</b> A rota confirmada constitui serviço contratado para o dia respetivo, aplicando-se-lhe as Cláusulas 4.ª e 9.ª.</p>' +
    '</div>' + dfoot(LABEL, 1, TOTAL) + '</div></div>';

  // ================= PÁGINA 2 =================
  const cl7 = regime === "SEMANAL"
    ? '<div class="cl">Cláusula 7.ª — Regime semanal, maturação e retenção de garantia</div>' +
      '<p class="par"><b>1.</b> Optando o Prestador pelo regime Semanal (Anexo I), o pagamento é efetuado toda a <b>' + esc(V.diapag) + '</b>: a semana de trabalho decorre de segunda-feira a domingo, o apuramento fecha na segunda-feira seguinte e cada ' + esc(V.diapag) + ' paga a semana trabalhada ' + (V.lag === 4 ? 'quatro' : V.lag) + ' semanas antes. O primeiro pagamento ocorre na primeira ' + esc(V.diapag) + ' após decorridos <b>' + V.matur + ' dias</b> sobre o início ("maturação").</p>' +
      '<p class="par"><b>2.</b> As <b>' + V.cauc + ' últimas semanas</b> trabalhadas permanecem retidas, em regime rotativo, como garantia do cumprimento das obrigações do Prestador (Cláusulas 8.ª e 9.ª), sendo libertadas à medida que novas semanas entram na retenção.</p>' +
      '<p class="par"><b>3.</b> O Prestador tem acesso a extrato discriminado: volumes, valores, saldo retido, deduções e datas de libertação. A mudança de regime é possível e produz efeitos no ciclo seguinte.</p>'
    : '<div class="cl">Cláusula 7.ª — Caução</div>' +
      '<p class="par"><b>1.</b> Para garantia do cumprimento das obrigações do Prestador (Cláusulas 8.ª e 9.ª), é constituída uma caução no valor de <b>' + V.caucfix + ',00 €</b>, por retenção sobre o(s) primeiro(s) pagamento(s) devido(s) ao Prestador.</p>' +
      '<p class="par"><b>2.</b> A caução só é utilizada quando o valor a pagar num fecho não comporte as deduções devidas, sendo reconstituída por retenção nos pagamentos seguintes.</p>' +
      '<p class="par"><b>3.</b> O Prestador tem acesso a extrato discriminado: volumes, valores, caução retida e deduções. A caução é restituída na liquidação final, nos termos da Cláusula 14.ª. A mudança de regime é possível e produz efeitos no ciclo seguinte.</p>';
  const p2 = '<div class="a4"><div class="pagepad">' + mhead("Contrato · Condições Gerais") +
    '<div class="ct">' +
    '<div class="cl">Cláusula 4.ª — Execução do serviço</div>' +
    '<p class="par"><b>1.</b> A recolha dos volumes ' + hubTxt + ' deve ocorrer até às <b>' + esc(V.saida) + '</b>, por exigência dos prazos de entrega assumidos perante o cliente final (SLA). A organização da rota, a sequência de paragens, as pausas e o termo do dia são da livre decisão do Prestador.</p>' +
    '<p class="par"><b>2.</b> O registo das operações (entrega, tentativa, recolha, incidência) é efetuado na aplicação indicada pelo 1.º Outorgante, enquanto requisito técnico do serviço e da rastreabilidade exigida pelo cliente final.</p>' +
    '<p class="par"><b>3.</b> Os volumes não entregues ou com incidência são devolvidos ao hub no próprio dia.</p>' +
    '<p class="par"><b>4.</b> Em caso de avaria da viatura, o Prestador assegura, por meios próprios, viatura de substituição que permita concluir o serviço confirmado; não o assegurando, aplica-se o disposto na Cláusula 9.ª, n.º 1, alínea d).</p>' +
    '<p class="par"><b>5.</b> As entregas cumprem o Protocolo de Entrega constante do Anexo II, enquanto requisito técnico do cliente final, designadamente: registo do nome completo e do número do documento de identificação de quem recebe; fotografias obrigatórias nas entregas em caixa de correio, ponto de recolha, cacifo e porteiro; registo geolocalizado a menos de 200 metros do local de entrega; contacto prévio com o destinatário antes de registar ausência; proibição de entrega a menores e de deixar volumes em zonas comuns ou com terceiros sem autorização do destinatário.</p>' +
    '<div class="cl">Cláusula 5.ª — Substituição</div>' +
    '<p class="par">O Prestador pode fazer-se substituir, ou recorrer a colaboradores próprios, na execução dos serviços, desde que os substitutos sejam titulares de carta de condução válida e cumpram os requisitos técnicos, de segurança e de registo aplicáveis, mantendo o Prestador responsabilidade integral pelos atos e omissões destes.</p>' +
    '<div class="cl">Cláusula 6.ª — Retribuição e faturação</div>' +
    '<p class="par"><b>1.</b> Como contrapartida, o Prestador recebe um valor por volume entregue/recolhido, conforme a tabela de zona(s) constante do Anexo I. Regime aplicável: ' + regDesc + '</p>' +
    '<p class="par"><b>2.</b> Os pagamentos são efetuados contra a emissão de fatura ou fatura-recibo pelo Prestador. Os valores indicados não incluem IVA, que acresce à taxa legal, ou beneficia de isenção, conforme o enquadramento fiscal do Prestador.</p>' +
    '<p class="par"><b>3.</b> Todos os impostos, contribuições e despesas necessárias à execução (combustível, portagens, manutenção, alimentação, comunicações) são da responsabilidade do Prestador.</p>' +
    cl7 +
    '</div>' + dfoot(LABEL, 2, TOTAL) + '</div></div>';

  // ================= PÁGINA 3 =================
  const tetoTxt = V.teto > 0 ? ', até ao limite de <b>' + V.teto + ',00 €</b>' : '';
  const dedTxt = regime === "SEMANAL"
    ? 'semanal (pré-fatura) no regime Semanal — e refletidas no extrato desse ciclo; sendo o valor a pagar insuficiente, o remanescente é deduzido à garantia retida.'
    : 'fecho mensal — e refletidas no extrato desse mês; sendo o valor a pagar insuficiente, o remanescente é deduzido à caução.';
  const p3 = '<div class="a4"><div class="pagepad">' + mhead("Contrato · Condições Gerais") +
    '<div class="ct">' +
    '<div class="cl">Cláusula 8.ª — Guarda e responsabilidade pelos volumes</div>' +
    '<p class="par"><b>1.</b> A responsabilidade do Prestador pelos volumes inicia-se com a conferência física da carga ' + hubTxt + '. Antes da saída, o Prestador confirma que os volumes atribuídos à rota na aplicação estão fisicamente presentes e em bom estado. Faltas ou danos comunicados antes da saída não lhe são imputados.</p>' +
    '<p class="par"><b>2.</b> Após a saída para distribuição, são da responsabilidade do Prestador, quando lhe sejam imputáveis: <b>a)</b> a perda, extravio ou furto de volumes; <b>b)</b> o dano de volumes; <b>c)</b> o registo de entrega sem entrega efetiva ou sem prova de entrega válida («entrega falsa»); <b>d)</b> a entrega em local diferente do indicado, incluindo fora do ponto de recolha ou cacifo designado; <b>e)</b> o registo de ausência sem tentativa real («falso ausente»).</p>' +
    '<p class="par"><b>3.</b> Considera-se perdido o volume que, tendo saído para distribuição, não seja entregue nem devolvido ao hub no prazo de 3 dias úteis, bem como o volume registado como entregue cuja prova de entrega válida não seja apresentada no prazo da Cláusula 9.ª, n.º 4.</p>' +
    '<p class="par"><b>4.</b> Os danos detetados durante a rota são comunicados de imediato ao 1.º Outorgante e sempre no próprio dia; não o sendo, presumem-se ocorridos sob a guarda do Prestador.</p>' +
    '<p class="par"><b>5.</b> Não há lugar a responsabilidade em caso de força maior, designadamente furto com violência, desde que o Prestador tenha cumprido os procedimentos de segurança aplicáveis. Em caso de furto ou tentativa de furto, o Prestador apresenta queixa às autoridades policiais e comunica de imediato ao 1.º Outorgante as referências dos volumes, o local, o dia e a hora da ocorrência.</p>' +
    '<p class="par"><b>6.</b> Não são remunerados: <b>a)</b> os serviços registados na aplicação por pessoa diferente do Prestador ou de substituto por ele previamente identificado ao 1.º Outorgante; <b>b)</b> os volumes destinados a ponto de recolha registados como entregues mas deixados a rececionista ou a pessoa não autorizada.</p>' +
    '<div class="cl">Cláusula 9.ª — Cláusulas penais e ressarcimento</div>' +
    '<p class="par"><b>1.</b> A título de indemnização pré-fixada, nos termos dos artigos 810.º e seguintes do Código Civil, são devidos os seguintes valores: <b>a)</b> perda, extravio ou furto de volume, e entrega falsa sem prova de entrega válida (incluindo entrega fora do ponto de recolha ou cacifo designado sem receção pelo destinatário) — <b>' + V.perda + ',00 € por volume</b> ou, sendo superior, o valor declarado da mercadoria' + tetoTxt + '; <b>b)</b> dano de volume — <b>' + V.dano + ',00 € por volume</b>; <b>c)</b> entrega em local diferente do indicado, incluindo fora do ponto de recolha ou cacifo designado, com receção final pelo destinatário — <b>' + V.local + ',00 € por volume</b>; <b>d)</b> não execução de rota previamente confirmada, sem comunicação até às ' + esc(V.conf) + ' do dia anterior — <b>' + V.noshow + ',00 € por ocorrência</b>; <b>e)</b> não devolução ao hub, no próprio dia, de volumes não entregues ou com incidência — <b>' + V.dev + ',00 € por ocorrência</b>.</p>' +
    '<p class="par"><b>2.</b> O valor declarado é o comunicado pelo cliente final e consta da evidência entregue ao Prestador nos termos do n.º 4.</p>' +
    '<p class="par"><b>3.</b> As deduções são aplicadas <b>no fecho de apuramento imediatamente seguinte à confirmação</b> — ' + dedTxt + '</p>' +
    '<p class="par"><b>4.</b> Nenhuma dedução é efetuada sem notificação prévia ao Prestador, acompanhada da evidência disponível (reclamação, prova de entrega, registo GPS, valor declarado), dispondo o Prestador de <b>' + esc(V.resp) + ' horas</b> para responder com os seus elementos de prova. Nas reclamações de não receção, é prova de entrega válida o registo de nome e documento de identificação, fotografia conforme o Anexo II, ou registo de chamada, e-mail ou SMS do destinatário a confirmar a entrega.</p>' +
    '<p class="par"><b>5.</b> As quantias previstas nesta cláusula têm natureza indemnizatória e não constituem contrapartida de qualquer prestação de serviços. As alíneas d) e e) do n.º 1 não prejudicam o ressarcimento de danos que as excedam, nos termos gerais.</p>' +
    '</div>' + dfoot(LABEL, 3, TOTAL) + '</div></div>';

  // ================= PÁGINA 4 =================
  const p4 = '<div class="a4"><div class="pagepad">' + mhead("Contrato · Condições Gerais") +
    '<div class="ct">' +
    '<div class="cl">Cláusula 10.ª — Seguros obrigatórios</div>' +
    '<p class="par"><b>1.</b> Constitui condição de execução do presente contrato a titularidade, pelo Prestador, dos seguros legalmente obrigatórios: <b>a)</b> seguro de acidentes de trabalho para trabalhadores independentes (Lei n.º 98/2009, de 4 de setembro, e Decreto-Lei n.º 159/99, de 11 de maio) ou, tratando-se de sociedade, seguro de acidentes de trabalho que cubra todas as pessoas afetas à execução dos serviços; <b>b)</b> seguro de responsabilidade civil automóvel (Decreto-Lei n.º 291/2007, de 21 de agosto) de todas as viaturas utilizadas, com apólice adequada ao uso profissional de transporte de mercadorias.</p>' +
    '<p class="par"><b>2.</b> O Prestador entrega ao 1.º Outorgante, antes do início dos serviços e sempre que solicitado, cópia das apólices e comprovativo do pagamento dos prémios, comunicando de imediato qualquer alteração, suspensão ou cessação de cobertura.</p>' +
    '<p class="par"><b>3.</b> A falta ou caducidade de qualquer seguro obrigatório impede a atribuição de rotas até à regularização e constitui fundamento de resolução nos termos da Cláusula 15.ª, correndo por conta exclusiva do Prestador os danos emergentes da falta de cobertura.</p>' +
    '<div class="cl">Cláusula 11.ª — Proteção de dados e confidencialidade</div>' +
    '<p class="par"><b>1.</b> Os dados pessoais dos destinatários a que o Prestador aceda são tratados exclusivamente para a execução das entregas, nos termos do RGPD, sendo proibida qualquer utilização, cópia ou comunicação para outros fins.</p>' +
    '<p class="par"><b>2.</b> O Prestador guarda sigilo sobre as condições comerciais e operacionais do 1.º Outorgante e dos seus clientes, obrigação que subsiste após a cessação do contrato.</p>' +
    '<div class="cl">Cláusula 12.ª — Equipamentos e materiais</div>' +
    '<p class="par">Os equipamentos e materiais eventualmente disponibilizados pelo 1.º Outorgante são devolvidos na cessação do contrato; a não devolução é deduzida pelo valor de reposição, documentado no extrato final.</p>' +
    '<div class="cl">Cláusula 13.ª — Vigência e denúncia</div>' +
    '<p class="par">O contrato entra em vigor em ' + bl(dini, 40) + ' e vigora por <b>' + esc(dur) + ' meses</b>, renovável por iguais períodos, podendo qualquer das partes denunciá-lo, por escrito, com pré-aviso de <b>' + V.aviso + ' dias</b>.</p>' +
    '<div class="cl">Cláusula 14.ª — Cessação e liquidação de saldos</div>' +
    '<p class="par"><b>1.</b> Cessando o contrato com pré-aviso, o saldo retido é liquidado <b>' + V.liq1 + ' dias</b> após o último dia de serviço. <b>2.</b> Cessando sem pré-aviso, a liquidação ocorre logo que o apuramento feche, no máximo <b>' + V.liq2 + ' dias</b> após o último dia de serviço e nunca antes de decorridos 30 dias sobre a última entrega, prazo correspondente à janela de reclamações do cliente final e ao apuramento de incidências, volumes e equipamentos por devolver.</p>' +
    '<p class="par"><b>3.</b> Em ambos os casos, a liquidação é efetuada líquida das deduções previstas nas Cláusulas 8.ª, 9.ª e 12.ª, integralmente documentadas no extrato final.</p>' +
    '<div class="cl">Cláusula 15.ª — Resolução por incumprimento</div>' +
    '<p class="par">O incumprimento grave ou reiterado das obrigações contratuais — designadamente fraude, entregas falsas reiteradas ou retenção indevida de volumes — confere à parte lesada o direito de resolver imediatamente o contrato, sem prejuízo da responsabilidade civil aplicável.</p>' +
    '<div class="cl">Cláusula 16.ª — Disposições finais</div>' +
    '<p class="par">Os Anexos I e II fazem parte integrante do contrato; as alterações constam de documento escrito assinado por ambas as partes. Em tudo o omisso aplicam-se os artigos 1154.º e seguintes do Código Civil. Para os litígios emergentes é competente o tribunal da comarca da sede do 1.º Outorgante.</p>' +
    '<p style="margin-top:4mm">' + esc(local) + ', ' + bl(dass, 44) + '</p>' +
    '<div class="sign">' +
    '<div class="box"><div class="line"></div><b>1.º Outorgante</b><br>Léguas Franzinas — Unipessoal, Lda.<br>' + esc(rep || "") + '</div>' +
    '<div class="box"><div class="line"></div><b>2.º Outorgante</b><br>' + (val("g_nome").trim() ? esc(val("g_nome")) : "&nbsp;") + '</div>' +
    '</div>' +
    '</div>' + dfoot(LABEL, 4, TOTAL) + '</div></div>';

  // ================= ANEXO I =================
  const anyWeekly = sel.hubs.some(x => x.hub.allows_weekly);
  let ztab = "";
  if (sel.hubs.length) {
    ztab = '<table><thead><tr><th>Escalão</th><th>CP</th><th>Zona</th><th class="num' + (regime === "MENSAL" ? ' sel' : '') + '">Regime Mensal</th>' +
      (anyWeekly ? '<th class="num' + (regime === "SEMANAL" ? ' sel' : '') + '">Regime Semanal</th>' : '') + '</tr></thead><tbody>';
    sel.hubs.forEach(x => {
      ztab += '<tr class="hubrow"><td colspan="' + (anyWeekly ? 5 : 4) + '">Hub ' + esc(x.hub.name) + (x.hub.address ? ' · ' + esc(x.hub.address) : '') + '</td></tr>';
      x.cps.forEach(z => {
        ztab += '<tr' + (z.esc === "C" ? ' class="hl"' : '') + '><td class="strong">' + (z.esc || '—') + '</td><td class="strong">' + z.cp + '</td><td>' + esc(z.z || '') +
          '</td><td class="num">' + eur(z.p) + '</td>' + (anyWeekly ? (x.hub.allows_weekly ? '<td class="num">' + eur(z.s) + '</td>' : '<td class="na">—</td>') : '') + '</tr>';
      });
    });
    ztab += '</tbody></table>';
  } else {
    ztab = '<p class="note">— Selecionar no gerador a(s) zona(s) contratada(s). —</p>';
  }
  const monthlyShort = V.mmode === "DAY_OF_NEXT_MONTH"
    ? 'o que entregas de 1 ao último dia do mês, recebes de uma vez no dia ' + V.mval + ' do mês seguinte (ex.: de 1 a 31 de agosto → dia ' + V.mval + ' de setembro)'
    : 'apuramento único de todo o mês, fechado no último dia; fatura paga a ' + V.mval + ' dias (ex.: setembro &#8594; fatura início de outubro &#8594; pago a 1 de novembro)';
  const regTxt = regime === "SEMANAL"
    ? '<b>Semanal</b> — pagamento toda a ' + esc(V.diapag) + ' (coluna «Semanal»), com apuramento fechado à segunda-feira, maturação de ' + V.matur + ' dias e retenção rotativa de ' + V.cauc + ' semanas (Cláusula 7.ª).'
    : '<b>Mensal</b> — ' + monthlyShort + ' (coluna «Mensal»). Caução de ' + V.caucfix + ',00 € (Cláusula 7.ª).';

  let minBlock = "";
  if ($("c_minimo").checked) {
    minBlock = '<div class="dsec"><div class="dk">3 · Tarifa mínima por rota completa' + (temC ? '' : ' <span style="color:#b23a30">(atenção: nenhuma zona C selecionada)</span>') + '</div>' +
      '<p class="ct par">Nas rotas da(s) zona(s) do escalão C com volume diário inferior a <b>' + V.minlim + ' volumes</b>, é devida uma tarifa mínima de <b>' + V.min + ',00 € por rota integralmente executada</b>. A tarifa mínima só é devida quando a rota for integralmente concluída: <b>' + esc(V.minpct) + ' dos volumes que saíram para distribuição entregues no próprio dia</b>; prevalece o maior dos valores entre a tarifa mínima e o apuramento por volume.</p></div>';
  }
  const tipo = val("g_tipo");
  const fv = (id, w) => val(id).trim() ? esc(val(id)) : '<span class="bl" style="min-width:' + w + 'mm">&nbsp;</span>';
  const idgridAnexo = '<div class="idgrid"><div class="rowl">' +
    '<div class="f" style="flex:2"><div class="k">Prestador</div><div class="v">' + fv("g_nome", 60) + '</div></div>' +
    '<div class="f"><div class="k">' + (tipo === "sociedade" ? "NIPC" : "NIF") + '</div><div class="v">' + fv("g_nif", 26) + '</div></div>' +
    '<div class="f"><div class="k">IBAN</div><div class="v">' + fv("g_iban", 40) + '</div></div>' +
    '</div><div class="rowl" style="margin-top:1mm">' +
    '<div class="f" style="flex:1"><div class="k">Seguro acidentes de trabalho — apólice</div><div class="v">' + fv("g_segat", 44) + '</div></div>' +
    '<div class="f" style="flex:1"><div class="k">Seguro automóvel — apólice</div><div class="v">' + fv("g_segauto", 44) + '</div></div>' +
    '</div></div>';
  const secZonas = '<div class="dsec"><div class="dk">1 · Zona(s) contratada(s) e valores por volume (s/ IVA)</div>' + ztab +
    '<p class="note">Valores por volume entregue/recolhido. A tabela pode ser revista com pré-aviso escrito de ' + V.aviso + ' dias, aplicando-se a nova tabela ao ciclo seguinte.</p></div>';
  const garantia = regime === "SEMANAL"
    ? '<tr><td>Retenção de garantia (reg. semanal)</td><td class="num strong">' + V.cauc + ' semanas rotativas</td><td>Maturação do 1.º pagamento</td><td class="num strong">' + V.matur + ' dias</td></tr>'
    : '<tr><td>Caução</td><td class="num strong">' + V.caucfix + ',00 €</td><td>Pagamento</td><td class="num strong">' + (V.mmode === "DAY_OF_NEXT_MONTH" ? 'dia ' + V.mval + ' do mês seguinte' : V.mval + ' dias após a fatura') + '</td></tr>';
  const secResto = '<div class="dsec"><div class="dk">2 · Regime de pagamento escolhido</div><p class="ct par">' + regTxt + '</p></div>' +
    minBlock +
    '<div class="dsec"><div class="dk">' + ($("c_minimo").checked ? '4' : '3') + ' · Parâmetros operacionais e valores de responsabilidade</div>' +
    '<table><tbody>' +
    '<tr><td>Confirmação de rota (véspera)</td><td class="num strong">até às ' + esc(V.conf) + '</td><td>Recolha no hub</td><td class="num strong">até às ' + esc(V.saida) + '</td></tr>' +
    '<tr><td>Perda / entrega falsa (mínimo)</td><td class="num strong">' + V.perda + ',00 € / volume</td><td>Valor declarado superior</td><td class="num strong">' + (V.teto > 0 ? 'até ' + V.teto + ',00 €' : 'valor integral') + '</td></tr>' +
    '<tr><td>Dano</td><td class="num strong">' + V.dano + ',00 € / volume</td><td>Entrega em local diferente (recebida)</td><td class="num strong">' + V.local + ',00 € / volume</td></tr>' +
    '<tr><td>Rota confirmada não executada</td><td class="num strong">' + V.noshow + ',00 € / ocorrência</td><td>Não devolução de volumes no dia</td><td class="num strong">' + V.dev + ',00 € / ocorrência</td></tr>' +
    garantia +
    '<tr><td>Liquidação na cessação c/ pré-aviso</td><td class="num strong">' + V.liq1 + ' dias</td><td>Sem pré-aviso (máximo)</td><td class="num strong">' + V.liq2 + ' dias</td></tr>' +
    '<tr><td colspan="2">Prazo de resposta do Prestador a reclamações</td><td colspan="2" class="num strong">' + esc(V.resp) + ' horas</td></tr>' +
    '<tr><td colspan="2">Dedução de indemnizações e cláusulas penais</td><td colspan="2" class="num strong">no fecho de apuramento seguinte à confirmação</td></tr>' +
    '</tbody></table></div>' +
    '<div class="callout"><div class="ck">Declaração</div><p>O Prestador declara ter lido e compreendido o contrato e os Anexos I e II, ter recebido cópia de todos e aceitar as condições neles fixadas, incluindo os valores de responsabilidade e os prazos de liquidação.</p></div>' +
    '<div class="sign">' +
    '<div class="box"><div class="line"></div><b>1.º Outorgante</b><br>Léguas Franzinas — Unipessoal, Lda.</div>' +
    '<div class="box"><div class="line"></div><b>2.º Outorgante</b><br>' + esc(local) + ', ' + (val("g_dass") ? esc(fdate(val("g_dass"))) : '____ / ____ / ________') + '</div>' +
    '</div>';
  const anexoTitle = '<div class="doctitle"><div class="kk">Parte integrante do contrato de prestação de serviços</div><h1>Anexo I — Condições Particulares</h1></div>';
  let a1, a1b = "";
  if (SPLIT) {
    a1 = '<div class="a4"><div class="pagepad">' + mhead("Anexo I · Condições Particulares") + anexoTitle + idgridAnexo + secZonas + dfoot(LABEL, 5, TOTAL) + '</div></div>';
    a1b = '<div class="a4"><div class="pagepad">' + mhead("Anexo I · Condições Particulares") +
      '<div class="doctitle"><div class="kk">Anexo I — continuação</div><h1>Condições Particulares (cont.)</h1></div>' +
      secResto + dfoot(LABEL, 6, TOTAL) + '</div></div>';
  } else {
    a1 = '<div class="a4"><div class="pagepad">' + mhead("Anexo I · Condições Particulares") + anexoTitle + idgridAnexo + secZonas + secResto + dfoot(LABEL, 5, TOTAL) + '</div></div>';
  }
  const a2 = '<div class="a4"><div class="pagepad">' + mhead("Anexo II · Protocolo de Entrega") +
    '<div class="doctitle"><div class="kk">Parte integrante do contrato de prestação de serviços</div><h1>Anexo II — Protocolo de Entrega</h1></div>' +
    '<p class="ct par">Requisitos técnicos exigidos pelo cliente final para a rastreabilidade e prova de entrega (Cláusula 4.ª, n.º 5). Em todos os tipos de entrega, o registo na aplicação é feito a <b>menos de 200 metros</b> do local de entrega.</p>' +
    protocolo() + dfoot(LABEL, TOTAL, TOTAL) + '</div></div>';

  $("preview").innerHTML = p1 + p2 + p3 + p4 + a1 + a1b + a2;

  return {
    regime,
    hubs: sel.hubs.map(x => ({ hub_id: x.hub.id, name: x.hub.name, cp4s: x.cps.map(c => c.cp), primary: sel.primary && x.hub.id === sel.primary.id })),
    params: Object.assign({}, V, { local, dass: val("g_dass"), dini: val("g_dini"), dur, rep, minimo: $("c_minimo").checked }),
    ok: sel.hubs.length > 0 && allowed.length > 0,
  };
}

function protocolo() {
  return '<div class="dsec"><div class="dk">1 · Registo obrigatório por tipo de entrega</div>' +
    '<table class="a2t"><thead><tr><th>Tipo</th><th>Registo na aplicação</th><th>Fotografias</th></tr></thead><tbody>' +
    '<tr><td class="strong">Destinatário / coabitante</td><td>Nome completo e n.º do documento de identificação de quem recebe. Não são aceites diminutivos ou alcunhas.</td><td>—</td></tr>' +
    '<tr><td class="strong">Caixa de correio</td><td>—</td><td>2: volume em frente à caixa, com etiqueta legível; caixa de correio.</td></tr>' +
    '<tr><td class="strong">Ponto de recolha</td><td>Só no ponto designado. O volume tem de caber no ponto.</td><td>2: entrada principal do ponto; cada volume entregue, com etiqueta legível (sequência permitida).</td></tr>' +
    '<tr><td class="strong">Cacifo (locker)</td><td>Só no cacifo designado.</td><td>2: cacifo completo; volume em frente ao cacifo, com etiqueta legível.</td></tr>' +
    '<tr><td class="strong">Porteiro</td><td>Nome completo do porteiro. Não são aceites «Porteiro» ou «Receção».</td><td>2: porta de entrada do edifício; volume em frente à porta, com etiqueta legível.</td></tr>' +
    '<tr><td class="strong">Vizinho</td><td>Nome de quem recebe, com andar e porta.</td><td>—</td></tr>' +
    '<tr><td class="strong">Outro (loja, comércio)</td><td>Nome de quem recebe e descrição do local (ex.: «Mercearia Marta, em frente ao prédio»).</td><td>—</td></tr>' +
    '</tbody></table></div>' +
    '<div class="dsec"><div class="dk">2 · Regras de entrega</div><div class="ct">' +
    '<p class="par"><b>1.</b> Antes da entrega, verificar na aplicação se o destinatário pré-autorizou a entrega a terceiro.</p>' +
    '<p class="par"><b>2.</b> Entregar na morada exata. A alteração de morada só é feita a pedido do destinatário, no momento da entrega.</p>' +
    '<p class="par"><b>3.</b> Não deixar volumes no elevador, capacho ou outra zona comum sem autorização do destinatário.</p>' +
    '<p class="par"><b>4.</b> Destinatário ausente: contactá-lo. A entrega a terceiro só é feita com a sua autorização e com indicação do seu n.º de identificação. Sem contacto, agenda-se nova tentativa. Nunca entregar a terceiro sem autorização.</p>' +
    '<p class="par"><b>5.</b> Nunca entregar a menores, qualquer que seja a relação com o destinatário.</p>' +
    '<p class="par"><b>6.</b> Registar tentativa só após tentativa real, a menos de 100 metros do ponto de entrega. Não registar «cliente ausente» sem contacto prévio.</p>' +
    '<p class="par"><b>7.</b> Respeitar a preferência de entrega indicada pelo destinatário.</p>' +
    '<p class="par"><b>8.</b> Registar na aplicação o estado real de cada volume (recebido, em rota, entregue, incidência).</p>' +
    '<p class="par"><b>9.</b> Nunca abrir volumes. Não riscar a embalagem; notas apenas em letra pequena.</p>' +
    '<p class="par"><b>10.</b> Não pedir gorjetas, não entrar na habitação do destinatário, não abrir portas sem autorização. Linguagem respeitosa; proibido o exercício da atividade sob efeito de álcool ou drogas.</p>' +
    '</div></div>' +
    '<div class="dsec"><div class="dk">3 · Sequência de tentativa</div><div class="ct">' +
    '<p class="par"><b>Morada particular:</b> tocar à campainha; na ausência, ligar ao destinatário; alternativa autorizada → entregar e registar; sem resposta → registar tentativa e devolver o volume ao hub no próprio dia. <b>Comércio:</b> aberto → entregar e registar; fechado → devolver ao hub. A 2.ª tentativa repete o processo.</p>' +
    '</div></div>';
}

/* ═══════════════════════ ADITIVO ═══════════════════════ */

function renderAditivo() {
  toggleTipo();
  const hub = GEN.hubs.find(h => String(h.id) === val("g_hub")) || GEN.hubs[0] || { name: "", address: "", signing_place: "" };
  const H = {
    nome: "Hub " + hub.name + (hub.address ? " (" + hub.address + ")" : ""),
    curto: "Hub " + hub.name,
  };
  const V = {
    perda: num("v_perda", 50), teto: num("v_teto", 0), dano: num("v_dano", 15), local: num("v_local", 5),
    resp: val("v_resp") || "24", noshow: num("v_noshow", 50), conf: val("v_conf") || "22:00", dev: num("v_dev", 30),
    cNoshow: $("c_noshow").checked, cDev: $("c_dev").checked,
  };
  const dass = fdate(val("g_dass")), dorig = fdate(val("g_dorig"));
  const local = val("g_local") || hub.signing_place || "Esposende";
  const rep = val("g_rep");
  const TOTAL = 3;
  const LABEL = "Aditivo ao Contrato";
  $("warns").innerHTML = val("g_dorig") ? "" : '<div class="warn">Indique a data de assinatura do contrato original.</div>';

  const al = ['a', 'b', 'c', 'd', 'e']; const items = [];
  items.push('perda, extravio ou furto de volume, e entrega falsa sem prova de entrega válida (incluindo entrega fora do ponto de recolha ou cacifo designado sem receção pelo destinatário) — <b>' + V.perda + ',00 € por volume</b> ou, sendo superior, o valor declarado da mercadoria' + (V.teto > 0 ? ', até ao limite de <b>' + V.teto + ',00 €</b>' : ''));
  items.push('dano de volume — <b>' + V.dano + ',00 € por volume</b>');
  items.push('entrega em local diferente do indicado, incluindo fora do ponto de recolha ou cacifo designado, com receção final pelo destinatário — <b>' + V.local + ',00 € por volume</b>');
  if (V.cNoshow) items.push('não execução de rota previamente confirmada, sem comunicação até às ' + esc(V.conf) + ' do dia anterior — <b>' + V.noshow + ',00 € por ocorrência</b>');
  if (V.cDev) items.push('não devolução ao hub, no próprio dia, de volumes não entregues ou com incidência — <b>' + V.dev + ',00 € por ocorrência</b>');
  const alTxt = items.map((t, i) => '<b>' + al[i] + ')</b> ' + t).join('; ') + '.';
  const extra = []; if (V.cNoshow) extra.push('d)'); if (V.cDev) extra.push(V.cNoshow ? 'e)' : 'd)');
  const exTxt = extra.length ? ' ' + (extra.length > 1 ? 'As alíneas ' + extra.join(' e ') : 'A alínea ' + extra[0]) + ' do n.º 1 não ' + (extra.length > 1 ? 'prejudicam' : 'prejudica') + ' o ressarcimento de danos que as excedam, nos termos gerais.' : '';

  const p1 = '<div class="a4"><div class="pagepad">' + mhead("Aditivo · Entregas e responsabilidade") +
    '<div class="doctitle"><div class="kk">Entregas e responsabilidade pelos volumes · ' + esc(H.curto) + '</div><h1>Aditivo ao Contrato de Prestação de Serviços</h1></div>' +
    '<div class="ct">' +
    '<p><b>Entre:</b></p>' +
    '<div class="idgrid"><b>LÉGUAS FRANZINAS — UNIPESSOAL, LDA.</b> (adiante, «1.º Outorgante»), pessoa coletiva n.º 517307243, com sede na Rua Padre Giesteira, n.º 225, Apart. 55, 4740-283 Esposende, neste ato representada por ' + bl(rep, 50) + ', na qualidade de gerente, com poderes para o ato;</div>' +
    '<p style="margin:1.5mm 0">e</p>' +
    '<div class="idgrid">' + idPrestador(false) + '</div>' +
    '<p style="margin-top:2mm"><b>Considerando que:</b></p>' +
    '<p class="par"><b>A)</b> As partes celebraram, em ' + bl(dorig, 40) + ', um contrato de prestação de serviços de transporte e distribuição de mercadorias de pequeno volume (adiante, «Contrato»), servido a partir do ' + esc(H.nome) + ';</p>' +
    '<p class="par"><b>B)</b> O cliente final reviu as regras de prova de entrega e de responsabilidade pelos volumes, que o 1.º Outorgante tem de cumprir e fazer cumprir na execução dos serviços;</p>' +
    '<p class="par"><b>C)</b> O Contrato prevê que as suas alterações constem de documento escrito assinado por ambas as partes;</p>' +
    '<p>é livremente e de boa-fé celebrado o presente <b>Aditivo</b>, que se rege pelas cláusulas seguintes:</p>' +
    '<div class="cl">Cláusula 1.ª — Objeto</div>' +
    '<p class="par">O presente Aditivo altera o Contrato <b>exclusivamente</b> quanto à execução das entregas e à responsabilidade pelos volumes, mantendo-se inalteradas todas as demais cláusulas e anexos, designadamente as relativas à retribuição, pagamento, caução ou retenção de garantia, seguros, vigência, cessação e liquidação de saldos.</p>' +
    '<div class="cl">Cláusula 2.ª — Protocolo de entrega</div>' +
    '<p class="par">À cláusula do Contrato relativa à execução do serviço é aditado o seguinte: «As entregas cumprem o Protocolo de Entrega anexo ao Aditivo, enquanto requisito técnico do cliente final, designadamente: registo do nome completo e do número do documento de identificação de quem recebe; fotografias obrigatórias nas entregas em caixa de correio, ponto de recolha, cacifo e porteiro; registo geolocalizado a menos de 200 metros do local de entrega; contacto prévio com o destinatário antes de registar ausência; proibição de entrega a menores e de deixar volumes em zonas comuns ou com terceiros sem autorização do destinatário.»</p>' +
    '<div class="cl">Cláusula 3.ª — Guarda e responsabilidade pelos volumes</div>' +
    '<p class="par">A cláusula do Contrato relativa à responsabilidade pelo serviço é substituída pela seguinte:</p>' +
    '<p class="par"><b>1.</b> A responsabilidade do Prestador pelos volumes inicia-se com a conferência física da carga no hub. Antes da saída, o Prestador confirma que os volumes atribuídos à rota na aplicação estão fisicamente presentes e em bom estado. Faltas ou danos comunicados antes da saída não lhe são imputados.</p>' +
    '<p class="par"><b>2.</b> Após a saída para distribuição, são da responsabilidade do Prestador, quando lhe sejam imputáveis: <b>a)</b> a perda, extravio ou furto de volumes; <b>b)</b> o dano de volumes; <b>c)</b> o registo de entrega sem entrega efetiva ou sem prova de entrega válida («entrega falsa»); <b>d)</b> a entrega em local diferente do indicado, incluindo fora do ponto de recolha ou cacifo designado; <b>e)</b> o registo de ausência sem tentativa real («falso ausente»).</p>' +
    '<p class="par"><b>3.</b> Considera-se perdido o volume que, tendo saído para distribuição, não seja entregue nem devolvido ao hub no prazo de 3 dias úteis, bem como o volume registado como entregue cuja prova de entrega válida não seja apresentada no prazo do n.º 4 da Cláusula 4.ª do presente Aditivo.</p>' +
    '</div>' + dfoot(LABEL, 1, TOTAL) + '</div></div>';

  const p2 = '<div class="a4"><div class="pagepad">' + mhead("Aditivo · Entregas e responsabilidade") +
    '<div class="ct">' +
    '<p class="par"><b>4.</b> Os danos detetados durante a rota são comunicados de imediato ao 1.º Outorgante e sempre no próprio dia; não o sendo, presumem-se ocorridos sob a guarda do Prestador.</p>' +
    '<p class="par"><b>5.</b> Não há lugar a responsabilidade em caso de força maior, designadamente furto com violência, desde que o Prestador tenha cumprido os procedimentos de segurança aplicáveis. Em caso de furto ou tentativa de furto, o Prestador apresenta queixa às autoridades policiais e comunica de imediato ao 1.º Outorgante as referências dos volumes, o local, o dia e a hora da ocorrência.</p>' +
    '<p class="par"><b>6.</b> Não são remunerados: <b>a)</b> os serviços registados na aplicação por pessoa diferente do Prestador ou de substituto por ele previamente identificado ao 1.º Outorgante; <b>b)</b> os volumes destinados a ponto de recolha registados como entregues mas deixados a rececionista ou a pessoa não autorizada.</p>' +
    '<div class="cl">Cláusula 4.ª — Cláusulas penais e ressarcimento</div>' +
    '<p class="par">A cláusula do Contrato relativa às cláusulas penais, bem como os valores de reclamação («claim») e de ressarcimento constantes do Contrato e do seu Anexo I, são substituídos pelo seguinte:</p>' +
    '<p class="par"><b>1.</b> A título de indemnização pré-fixada, nos termos dos artigos 810.º e seguintes do Código Civil, são devidos os seguintes valores: ' + alTxt + '</p>' +
    '<p class="par"><b>2.</b> O valor declarado é o comunicado pelo cliente final e consta da evidência entregue ao Prestador nos termos do n.º 4.</p>' +
    '<p class="par"><b>3.</b> As deduções são aplicadas no fecho de apuramento imediatamente seguinte à confirmação, nos termos e com a periodicidade previstos no Contrato, e refletidas no extrato desse ciclo; sendo o valor a pagar insuficiente, o remanescente é deduzido à caução ou garantia prevista no Contrato.</p>' +
    '<p class="par"><b>4.</b> Nenhuma dedução é efetuada sem notificação prévia ao Prestador, acompanhada da evidência disponível (reclamação, prova de entrega, registo GPS, valor declarado), dispondo o Prestador de <b>' + esc(V.resp) + ' horas</b> para responder com os seus elementos de prova. Nas reclamações de não receção, é prova de entrega válida o registo de nome e documento de identificação, fotografia conforme o Protocolo de Entrega, ou registo de chamada, e-mail ou SMS do destinatário a confirmar a entrega.</p>' +
    '<p class="par"><b>5.</b> As quantias previstas nesta cláusula têm natureza indemnizatória e não constituem contrapartida de qualquer prestação de serviços.' + exTxt + '</p>' +
    '<div class="cl">Cláusula 5.ª — Produção de efeitos</div>' +
    '<p class="par">O presente Aditivo produz efeitos na data da sua assinatura e aplica-se às ocorrências relativas a volumes que saiam para distribuição a partir dessa data. As ocorrências anteriores continuam reguladas pelo Contrato na redação então em vigor.</p>' +
    '<div class="cl">Cláusula 6.ª — Disposições finais</div>' +
    '<p class="par">O presente Aditivo e o Protocolo de Entrega anexo fazem parte integrante do Contrato, prevalecendo sobre este nas matérias neles reguladas. Em tudo o mais, mantém-se integralmente em vigor o Contrato. Feito em dois exemplares, ficando um na posse de cada parte.</p>' +
    '<p style="margin-top:4mm">' + esc(local) + ', ' + bl(dass, 44) + '</p>' +
    '<div class="sign">' +
    '<div class="box"><div class="line"></div><b>1.º Outorgante</b><br>Léguas Franzinas — Unipessoal, Lda.<br>' + esc(rep) + '</div>' +
    '<div class="box"><div class="line"></div><b>2.º Outorgante</b><br>' + (val("g_nome").trim() ? esc(val("g_nome")) : "&nbsp;") + '</div>' +
    '</div>' +
    '</div>' + dfoot(LABEL, 2, TOTAL) + '</div></div>';

  const p3 = '<div class="a4"><div class="pagepad">' + mhead("Anexo ao Aditivo · Protocolo de Entrega") +
    '<div class="doctitle"><div class="kk">Parte integrante do aditivo ao contrato de prestação de serviços</div><h1>Protocolo de Entrega</h1></div>' +
    '<p class="ct par">Requisitos técnicos exigidos pelo cliente final para a rastreabilidade e prova de entrega (Cláusula 2.ª do Aditivo). Em todos os tipos de entrega, o registo na aplicação é feito a <b>menos de 200 metros</b> do local de entrega.</p>' +
    protocolo() + dfoot(LABEL, 3, TOTAL) + '</div></div>';

  $("preview").innerHTML = p1 + p2 + p3;
  return {
    regime: GEN.driver.regime || "",
    hubs: [{ hub_id: hub.id, name: hub.name, cp4s: [], primary: true }],
    params: Object.assign({}, V, { local, dass: val("g_dass"), dorig: val("g_dorig"), rep }),
    ok: !!val("g_dorig"),
  };
}

/* ═══════════════════════ ligação ═══════════════════════ */

const render = GEN.kind === "ADITIVO" ? renderAditivo : renderContrato;
let last = null;
if (GEN.kind !== "ADITIVO") buildZoneList();
function rerender() { last = render(); }
document.querySelectorAll(".panel input, .panel select").forEach(el => {
  el.addEventListener("input", rerender);
  el.addEventListener("change", rerender);
});
rerender();

$("btnSave").addEventListener("click", () => {
  rerender();
  if (!last.ok) {
    $("warns").insertAdjacentHTML("afterbegin", '<div class="warn">Não é possível registar: corrija os avisos.</div>');
    return;
  }
  $("f_regime").value = last.regime;
  $("f_hubs").value = JSON.stringify(last.hubs);
  $("f_params").value = JSON.stringify(last.params);
  $("f_html").value = $("preview").innerHTML;
  $("saveForm").submit();
});
$("btnPrint").addEventListener("click", () => window.print());
})();
