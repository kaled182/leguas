/* Gerador de proposta para motoristas — Léguas Franzinas.
 *
 * Os valores vêm do sistema (window GEN, json_script), os mesmos que o
 * contrato e a PF usam: tarifas por CP, condições por hub, parâmetros do
 * contrato e regras PUDO / mesma porta da ficha CAINIAO. Nada fica fixo aqui.
 */
(function () {
const GEN = JSON.parse(document.getElementById("gen-data").textContent);
const S = GEN.settings, M = GEN.multi || {};
const LOGO = GEN.logo;
const $ = id => document.getElementById(id);

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const DIAS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"];
/* HubContractTerms.weekly_payday: 0 = segunda … 6 = domingo (igual ao contrato). */
const jsDay = payday => (Number(payday) + 1) % 7;

function esc(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function eur(n) { return n == null || isNaN(n) ? "" : Number(n).toFixed(2).replace(".", ",") + " €"; }
function eur0(n) { return Number(n).toLocaleString("pt-PT") + ",00 €"; }
function iso(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
function pd(v) { return v ? new Date(v + "T12:00:00") : null; }
function addD(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function fl(d) { return d ? d.getDate() + " de " + MESES[d.getMonth()] + " de " + d.getFullYear() : ""; }
function fs(d) { return d ? d.getDate() + " de " + MESES[d.getMonth()] : ""; }
function num(v) { const t = String(v).trim().replace(",", "."); return t === "" ? null : +t; }
function r2(n) { return n == null ? null : Math.round(n * 100) / 100; }
function same(a, b) { return a == null && b == null || (a != null && b != null && Math.abs(a - b) < 0.005); }

/* ── hubs e zonas ── */
const HUBS = GEN.hubs || [];
let HUB = null;          // hub escolhido
const state = {};        // cp -> {on, s, p, sman}

(function () {
  const sel = $("a_hubsel");
  HUBS.forEach(h => { const o = document.createElement("option"); o.value = h.id; o.textContent = h.name + " (" + h.cps.length + " CP4)"; sel.appendChild(o); });
  $("n_desc").textContent = eur(S.desc);
})();

function hubAddr(h) { return h ? "Hub " + h.name + (h.address ? " — " + h.address : "") : "—"; }
function monthlyShort(h) {
  return h.monthly_mode === "DAY_OF_NEXT_MONTH"
    ? "o que entregas de 1 ao último dia do mês, recebes de uma vez no dia " + h.monthly_value + " do mês seguinte"
    : "um pagamento por mês, com todas as entregas do dia 1 ao último dia; a fatura é paga a " + h.monthly_value + " dias";
}
function monthlyExample(h) {
  return h.monthly_mode === "DAY_OF_NEXT_MONTH"
    ? "o que entregas de 1 a 31 de agosto, recebes de uma vez no dia " + h.monthly_value + " de setembro."
    : "o que entregas de 1 a 30 de setembro é faturado no início de outubro e pago a " + h.monthly_value + " dias (1 de novembro).";
}

function applyHub(id) {
  HUB = HUBS.find(h => String(h.id) === String(id)) || HUBS[0] || null;
  Object.keys(state).forEach(k => delete state[k]);
  let h = "";
  (HUB ? HUB.cps : []).forEach(cp => {
    state[cp.cp] = { on: false, s: cp.s, p: cp.p, sman: false };
    const priced = cp.p != null;
    h += '<div class="zrow off" id="zr_' + cp.cp + '"><input type="checkbox" data-cp="' + cp.cp + '" class="zck" aria-label="Incluir ' + cp.cp + '"' + (priced ? "" : " disabled") + '>' +
      '<span class="cp">' + cp.cp + '</span><span class="zn">' + esc(cp.z || "") + (priced ? "" : ' <span style="color:#ffb27a">· sem tarifa</span>') + '</span><span class="esc">' + (cp.esc || "") + '</span>' +
      '<input class="zv zs" data-cp="' + cp.cp + '" inputmode="decimal" placeholder="—" aria-label="' + cp.cp + ' Semanal">' +
      '<input class="zv zp" data-cp="' + cp.cp + '" inputmode="decimal" placeholder="—" aria-label="' + cp.cp + ' Mensal"></div>';
  });
  $("zlist").innerHTML = h || '<div class="note">Este hub não tem CP4 configurados.</div>';
  bindZones();
  syncZoneInputs();
  if (HUB) {
    $("a_nome").value = HUB.name;
    $("t_min").checked = !!HUB.min_fare;
    const regs = [HUB.allows_monthly ? "mensal" : null, HUB.allows_weekly ? "semanal" : null].filter(Boolean).join(" e ");
    $("hub_terms").innerHTML = (HUB.has_terms ? "" : '<b style="color:#ffb27a">Hub sem condições de contrato configuradas — valores por omissão.</b><br>') +
      "Regimes aceites: <b>" + (regs || "nenhum") + "</b> · Mensal: " + esc(monthlyShort(HUB)) +
      (HUB.allows_weekly ? " · Semanal: toda a " + DIAS[jsDay(HUB.weekly_payday)] : "") +
      " · Tarifa mínima: <b>" + (HUB.min_fare ? eur0(HUB.min_fare_value) + " (rotas C com menos de " + HUB.min_fare_under + " vol.)" : "não") + "</b>" +
      "<br>Morada: " + esc(HUB.address || "por preencher");
    const reg = $("p_reg");
    [...reg.options].forEach(o => { o.disabled = (o.value === "semanal" || o.value === "ambos") && !HUB.allows_weekly || (o.value === "mensal" || o.value === "ambos") && !HUB.allows_monthly; });
    if (reg.selectedOptions[0] && reg.selectedOptions[0].disabled) reg.value = HUB.allows_weekly ? "semanal" : "mensal";
  }
}
function tableCp(cp) { return HUB ? HUB.cps.find(c => c.cp === cp) : null; }
function syncZoneInputs() {
  Object.keys(state).forEach(cp => {
    const st = state[cp];
    document.querySelector('.zck[data-cp="' + cp + '"]').checked = st.on;
    const zs = document.querySelector('.zs[data-cp="' + cp + '"]'), zp = document.querySelector('.zp[data-cp="' + cp + '"]');
    if (zs !== document.activeElement) zs.value = st.s == null ? "" : st.s.toFixed(2).replace(".", ",");
    if (zp !== document.activeElement) zp.value = st.p == null ? "" : st.p.toFixed(2).replace(".", ",");
    zs.disabled = !(HUB && HUB.allows_weekly);
    const t = tableCp(cp);
    zp.classList.toggle("diff", !!t && !same(st.p, t.p));
    zs.classList.toggle("diff", !!t && HUB.allows_weekly && !same(st.s, t.s));
    $("zr_" + cp).classList.toggle("off", !st.on);
  });
}
function bindZones() {
  document.querySelectorAll(".zck").forEach(el => el.addEventListener("change", () => {
    const cp = el.dataset.cp; state[cp].on = el.checked;
    syncZoneInputs(); render();
  }));
  document.querySelectorAll(".zp").forEach(el => el.addEventListener("input", () => {
    const cp = el.dataset.cp, v = num(el.value); state[cp].p = v;
    if (!state[cp].sman) state[cp].s = v == null ? null : r2(v - S.desc);
    if (v != null && !state[cp].on) state[cp].on = true;
    syncZoneInputs(); render();
  }));
  document.querySelectorAll(".zs").forEach(el => el.addEventListener("input", () => {
    const cp = el.dataset.cp; state[cp].s = num(el.value); state[cp].sman = el.value.trim() !== "";
    syncZoneInputs(); render();
  }));
}

/* ── datas por omissão ── */
(function () {
  const t = new Date(); t.setHours(12, 0, 0, 0);
  $("p_data").value = iso(t);
  $("p_val").value = iso(addD(t, 7));
  let m = addD(t, 1); while (m.getDay() !== 1) m = addD(m, 1);
  $("p_ini").value = iso(m);
})();

function firstName(n) { return (n || "").trim().split(/\s+/)[0] || ""; }
function initials(n) { return (n || "").trim().split(/\s+/).filter(w => w.length > 2 || /^[A-ZÁÉÍÓÚ]/.test(w)).map(w => w[0].toUpperCase()).join("").slice(0, 4); }
function rateRange(list, key) {
  const v = list.map(z => z[key]).filter(x => x != null && !isNaN(x));
  if (!v.length) return null;
  const mn = Math.min(...v), mx = Math.max(...v);
  return { mn, mx };
}
/* Contrato, Cl. 7.ª: 1.º pagamento no 1.º dia de pagamento após a maturação. */
function firstPay(start, payday) {
  let d = addD(start, S.matur); while (d.getDay() !== jsDay(payday)) d = addD(d, 1); return d;
}

let lastData = null;
function collect() {
  const nome = $("c_nome").value.trim();
  const trat = $("c_trat").value.trim() || firstName(nome);
  const sel = Object.keys(state).filter(cp => state[cp].on).map(cp => {
    const t = tableCp(cp) || {};
    return { cp, z: t.z || "", e: t.esc || "", s: state[cp].s, p: state[cp].p };
  });
  const reg = $("p_reg").value;
  const dData = pd($("p_data").value) || new Date(), dVal = pd($("p_val").value), dIni = pd($("p_ini").value);
  const ref = $("p_ref").value.trim() || ("LF-" + iso(dData).slice(2).replace(/-/g, "") + (initials(nome) ? "-" + initials(nome) : ""));
  const weekly = !!(HUB && HUB.allows_weekly), monthly = !HUB || HUB.allows_monthly;
  return {
    nome, trat, tel: $("c_tel").value.trim(), sel, reg,
    area: $("a_nome").value.trim() || "—", vol: num($("a_vol").value), dias: $("a_dias").value.trim(),
    dData, dVal, dIni, ref,
    sim: $("t_sim").checked, min: $("t_min").checked, multi: $("t_multi").checked && (M.pudo_on || M.porta_on), resp: $("t_resp").checked,
    kNome: $("k_nome").value.trim(), kTel: $("k_tel").value.trim(), kMail: $("k_mail").value.trim(),
    showS: weekly && reg !== "mensal", showP: monthly && reg !== "semanal",
  };
}

function header(D, c) {
  return '<div class="dh' + (c ? ' c' : '') + '"><img src="' + LOGO + '" alt="">' +
    '<div class="r"><div class="k">Proposta de parceria</div>' +
    '<div class="m">Ref. <b>' + esc(D.ref) + '</b> · ' + esc(fl(D.dData)) + '</div>' +
    (D.dVal ? '<div class="m">Válida até <b>' + esc(fl(D.dVal)) + '</b></div>' : '') + '</div></div>';
}
function footer(D, n) {
  return '<div class="df"><div><b>Léguas Franzinas — Unipessoal, Lda.</b> · NIPC 517307243 · Rua Padre Giesteira 225, 4740-283 Esposende<br>' +
    'Proposta pessoal' + (D.nome ? ' para ' + esc(D.nome) : '') + '. Não constitui contrato: as condições finais constam do contrato de prestação de serviços.</div><div style="white-space:nowrap;align-self:flex-end">' + n + '</div></div>';
}

function paginate(D, B) {
  const Mz = $("measure"); Mz.innerHTML = "";
  const shell = first => {
    const a = document.createElement("div"); a.className = "a4";
    a.innerHTML = '<div class="pad">' + header(D, !first) + '<div class="flow"></div>' + footer(D, "__PG__") + '</div>';
    Mz.appendChild(a); return a;
  };
  const fits = a => {
    const f = a.querySelector(".flow"), df = a.querySelector(".df"); const l = f.lastElementChild;
    return !l || l.getBoundingClientRect().bottom <= df.getBoundingClientRect().top - 6;
  };
  const out = []; let cur = shell(true);
  B.forEach(b => {
    const d = document.createElement("div"); d.className = "blk"; d.innerHTML = b;
    const f = cur.querySelector(".flow"); f.appendChild(d);
    if (!fits(cur) && f.children.length > 1) {
      f.removeChild(d); out.push(cur); cur = shell(false); cur.querySelector(".flow").appendChild(d);
    }
  });
  out.push(cur);
  const N = out.length;
  const html = out.map((a, i) => a.outerHTML.replace("__PG__", (i + 1) + " / " + N));
  Mz.innerHTML = ""; return html;
}

function render() {
  const D = collect(); lastData = D;
  const H = HUB || {};
  const sel = D.sel;
  const rS = rateRange(sel, "s"), rP = rateRange(sel, "p");
  const mainR = D.showS ? rS : rP;
  const hasC = sel.some(z => z.e === "C");
  const payday = DIAS[jsDay(H.weekly_payday || 1)];
  const paydayPl = payday.replace("-feira", "s-feiras").replace(/^(sábado|domingo)$/, "$1s");
  const nome = D.nome ? esc(D.nome) : '<span style="opacity:.55">[nome do candidato]</span>';
  const trat = D.trat ? esc(D.trat) : '<span style="opacity:.55">[nome]</span>';
  const cpList = sel.map(z => z.cp).join(" · ");

  /* ── página 1 ── */
  const REQS = '<div class="cols"><div><ul class="chk">' +
    '<li>Viatura própria</li><li>Carta de condução válida</li><li>Smartphone com dados móveis</li><li>Documento de identificação válido e IBAN</li></ul></div>' +
    '<div><ul class="chk"><li>Atividade aberta nas Finanças (independente ou empresa), para faturar</li>' +
    '<li>Seguro de acidentes de trabalho para independentes (Lei 98/2009 e DL 159/99)</li>' +
    '<li>Seguro automóvel de responsabilidade civil para uso profissional (DL 291/2007)</li></ul></div></div>' +
    '<div class="small">Os dois seguros são condição obrigatória para receber rotas.</div>';
  const rateTxt = r => r ? (r.mn !== r.mx ? '<span style="font-size:12.5pt">' + eur(r.mn).replace(" €", "") + "–" + eur(r.mx) + '</span>' : eur(r.mn)) : "a definir";
  const tiles = '<div class="tiles">' +
    '<div class="tile hl"><div class="k">Tarifa por entrega</div><div class="v">' + rateTxt(mainR) + '</div><div class="s">' + (D.showS ? "Regime Semanal" : "Regime Mensal") + ' · sem IVA' + (D.showS && D.showP ? ' · Mensal +' + eur(S.desc) : '') + '</div></div>' +
    '<div class="tile"><div class="k">Pagamento</div><div class="v">' + (D.showS ? "Semanal" : "Mensal") + '</div><div class="s">' + (D.showS ? "todas as " + paydayPl : "um pagamento único por mês") + '</div></div>' +
    (D.vol ? '<div class="tile"><div class="k">Volume médio</div><div class="v">' + D.vol + ' <span style="font-size:9pt;font-weight:600">vol./dia</span></div><div class="s">média por rota</div></div>' : '') +
    '<div class="tile"><div class="k">Operação</div><div class="v" style="font-size:11.5pt;line-height:1.3;padding-top:1mm">' + esc(D.dias || "—") + '</div><div class="s">rota oferecida na véspera</div></div>' +
    '</div>';

  const cell = v => v == null ? '<td class="num tbd">a definir</td>' : '<td class="num rate">' + eur(v) + '</td>';
  const mkTab = (list, dense) => {
    let rows = "";
    if (list.length) list.forEach(z => { rows += '<tr><td class="cp">' + z.cp + '</td><td>' + esc(z.z) + '</td>' + (D.showS ? cell(z.s) : "") + (D.showP ? cell(z.p) : "") + '</tr>'; });
    else rows = '<tr><td colspan="4" class="tbd">Selecione os códigos postais no painel.</td></tr>';
    const hS = dense ? "Semanal" : "Regime Semanal", hP = dense ? "Mensal" : "Regime Mensal";
    return '<table class="zt' + (dense ? ' dense' : '') + '"><thead><tr><th>CP4</th><th>Localidade</th>' + (D.showS ? '<th class="num">' + hS + '</th>' : '') + (D.showP ? '<th class="num">' + hP + '</th>' : '') + '</tr></thead><tbody>' + rows + '</tbody></table>';
  };
  const ztab = sel.length > 7
    ? '<div class="ztwo">' + mkTab(sel.slice(0, Math.ceil(sel.length / 2)), true) + mkTab(sel.slice(Math.ceil(sel.length / 2)), true) + '</div>'
    : mkTab(sel, false);

  const minBox = D.min
    ? '<div class="box"><div class="bt">Tarifa mínima por rota completa — ' + eur0(H.min_fare_value || 60) + '/dia</div><div class="txt">Nas rotas do Escalão C com menos de ' + (H.min_fare_under || 50) + ' volumes por dia, recebes no mínimo <b>' + eur0(H.min_fare_value || 60) + '</b> por rota. Condição única: <b>rota 100% concluída</b> — todos os volumes que saíram do hub entregues no próprio dia. Aplica-se sempre o maior valor: a tarifa mínima ou o que faturaste por entrega.</div></div>'
    : "";

  let simBox = "";
  if (D.sim && D.vol && mainR) {
    const t = mainR.mn, dia = D.vol * t;
    const nd = /s[áa]bado/i.test(D.dias) ? 6 : (/sexta/i.test(D.dias) ? 5 : 6);
    simBox = '<div class="box"><div class="bt">Exemplo ilustrativo de faturação</div>' +
      '<div class="sim">' +
      '<div class="c"><div class="k">Um dia</div><div class="f">' + D.vol + ' entregas × ' + eur(t) + '</div><div class="v">' + eur(dia) + '</div></div>' +
      '<div class="c"><div class="k">Uma semana (' + nd + ' dias)</div><div class="f">' + nd + ' × ' + eur(dia) + '</div><div class="v">' + eur(dia * nd) + '</div></div>' +
      '</div><div class="small">Valores antes de IVA e das tuas despesas, calculados sobre o volume médio da área e a ' + (mainR.mn !== mainR.mx ? 'tarifa mais baixa' : 'tarifa') + ' do ' + (D.showS ? 'Regime Semanal' : 'Regime Mensal') + '. O volume real varia de dia para dia: é um exemplo, não um valor garantido.' + (D.multi ? ' Entregas em ponto de recolha e volumes adicionais na mesma morada têm valores próprios (secção 2).' : '') + '</div></div>';
  }

  /* Secção: regras do contrato (Anexo I, secção 2) — mesmo texto e valores. */
  let multiBox = "";
  if (D.multi) {
    const li = [];
    if (M.pudo_on) li.push('<tr><td><b>Ponto de recolha (PUDO)</b> — volumes entregues no mesmo ponto, no mesmo dia</td><td class="v">1.º volume ' + eur(M.pudo1) + ' · cada adicional ' + eur(M.pudoadd) + '</td></tr>');
    if (M.porta_on) li.push('<tr><td><b>Mesma morada</b> — mais do que um volume na mesma morada, no mesmo dia (fora de ponto de recolha)</td><td class="v">1.º volume pela tabela · cada adicional ' + eur(M.porta) + '</td></tr>');
    multiBox = '<table class="rt"><tbody>' + li.join("") + '</tbody></table>' +
      '<div class="small">Estas regras substituem o valor por entrega da tabela nesses casos. Mesma morada: a mesma morada e código postal, ou a mesma paragem da rota na aplicação.</div>';
  }

  const B = [];
  let n = 0;
  B.push("<div>" + '<div class="hero"><div class="kk">Proposta personalizada · Distribuição last-mile</div>' +
    '<h1>Olá, ' + trat + '.</h1>' +
    '<p>Preparámos esta proposta para ti: distribuição de encomendas de pequeno volume na zona de <b>' + esc(D.area) + '</b>' + (cpList ? (sel.length > 6 ? ' (' + sel.length + ' códigos postais)' : ' (CP4 ' + cpList + ')') : '') + ', como prestador de serviços independente, com recolha no <b>Hub ' + esc(H.name || "") + '</b>.</p>' +
    '<div class="for"><div><div class="k">Preparada para</div><div class="v">' + nome + '</div></div>' +
    '<div><div class="k">Zona</div><div class="v">' + esc(D.area) + '</div></div>' +
    (D.dIni ? '<div><div class="k">Início previsto</div><div class="v">' + esc(fs(D.dIni)) + '</div></div>' : '') + '</div></div>' + tiles + "</div>");
  B.push('<div class="sh"><span class="n">' + (++n) + '</span><h2>A tua zona e quanto recebes por entrega</h2></div>' + ztab +
    '<div class="small">Valores por entrega concluída, sem IVA (acresce à taxa legal ou isenção, conforme o teu enquadramento). Combustível, portagens, manutenção e comunicações ficam por tua conta. Recolha dos volumes: ' + esc(hubAddr(H)) + '.</div>');
  if (minBox) B.push(minBox);
  if (simBox) B.push(simBox);
  if (multiBox) B.push('<div class="sh"><span class="n">' + (++n) + '</span><h2>Ponto de recolha e mesma morada</h2></div>' + multiBox);
  B.push('<div class="sh"><span class="n">' + (++n) + '</span><h2>O que precisas</h2></div>' + REQS);

  /* ── página 2: pagamento (Cl. 7.ª e Anexo I do contrato) ── */
  let ex = "";
  if (D.dIni && D.showS) {
    const f = firstPay(D.dIni, H.weekly_payday || 1);
    const n1 = addD(f, 7), n2 = addD(f, 14), n3 = addD(f, 21);
    ex = '<b>Exemplo:</b> começas ' + DIAS[D.dIni.getDay()] + ', ' + fs(D.dIni) + ' → 1.º pagamento ' + payday + ', ' + fs(f) + '; depois ' + n1.getDate() + ', ' + n2.getDate() + ', ' + n3.getDate() + '…';
  }
  const lag = H.weekly_lag_weeks || 4;
  const rangeTxt = r => r ? (r.mn === r.mx ? eur(r.mn) : eur(r.mn) + " a " + eur(r.mx)) + " por entrega" : "tarifa a definir";
  const regS = '<div class="reg"><div class="rh"><div class="k">Pagamento semanal</div><div class="t">Regime Semanal</div><div class="p">' + rangeTxt(rS) + '</div></div><ul>' +
    '<li>Recebes <b>todas as ' + paydayPl + '</b>.</li>' +
    '<li>A semana vai de segunda a domingo; o apuramento fecha na segunda-feira seguinte, para conferires e, se for o caso, reclamares.</li>' +
    '<li>O 1.º pagamento chega na 1.ª ' + payday + ' após ' + S.matur + ' dias do início; cada ' + payday + ' paga a semana trabalhada ' + lag + ' semanas antes.</li>' +
    '<li>Retenção de garantia rotativa: as ' + S.cauc + ' últimas semanas trabalhadas.</li>' +
    '<li>Tarifa ' + eur(S.desc) + ' por entrega abaixo do Regime Mensal.</li></ul>' +
    (ex ? '<div class="ex">' + ex + '</div>' : '') + '</div>';
  const regP = '<div class="reg alt"><div class="rh"><div class="k">Pagamento mensal</div><div class="t">Regime Mensal</div><div class="p">' + rangeTxt(rP) + '</div></div><ul>' +
    '<li><b>Tarifa mais alta</b> por entrega.</li>' +
    '<li>' + esc(monthlyShort(H).charAt(0).toUpperCase() + monthlyShort(H).slice(1)) + '.</li>' +
    '<li>Caução de ' + eur0(S.caucfix) + ', retida no(s) primeiro(s) pagamento(s) e restituída na liquidação final.</li></ul>' +
    '<div class="ex"><b>Exemplo:</b> ' + esc(monthlyExample(H)) + '</div></div>';
  const regs = '<div class="regs">' + (D.showS ? regS : "") + (D.showP ? regP : "") + '</div>' +
    (D.showS && D.showP ? '<div class="small">Escolhes o regime na assinatura do contrato. A mudança de regime é possível e produz efeitos no ciclo seguinte.</div>' : '');

  const steps = '<div class="steps">' +
    '<div class="step"><div class="w">Na véspera</div><div class="t">Recebes a rota</div><div class="d">A rota do dia seguinte é oferecida na véspera e confirmas até às <b>' + esc(S.conf) + '</b>. Recusar não tem penalização nem afeta as ofertas seguintes.</div></div>' +
    '<div class="step"><div class="w">Até às ' + esc(S.saida) + '</div><div class="t">Recolha no hub</div><div class="d">Levantas os volumes no hub até às ' + esc(S.saida) + ' (SLA de recolha). A partir daí, organizas a rota como entenderes.</div></div>' +
    '<div class="step"><div class="w">Durante o dia</div><div class="t">Entregas com autonomia</div><div class="d">Registas cada entrega na aplicação, com prova de entrega e a menos de 200 m do local, e devolves ao hub no próprio dia o que não for entregue.</div></div>' +
    '</div>';

  /* Regras claras: Cl. 10.ª e Anexo I do contrato (ContractSettings). */
  const teto = S.teto > 0 ? ", até " + eur0(S.teto) : "";
  const resp = D.resp ? (
    '<table class="rt"><tbody>' +
    '<tr><td>Perda, extravio ou entrega falsa sem prova de entrega</td><td class="v">' + eur0(S.perda) + ' por volume ou o valor declarado, se maior' + teto + '</td></tr>' +
    '<tr><td>Dano no volume</td><td class="v">' + eur0(S.dano) + ' por volume</td></tr>' +
    '<tr><td>Entrega em local diferente (incluindo fora do ponto de recolha), recebida pelo cliente</td><td class="v">' + eur0(S.local) + ' por volume</td></tr>' +
    '<tr><td>Rota confirmada e não executada, sem aviso até às ' + esc(S.conf) + ' da véspera</td><td class="v">' + eur0(S.noshow) + '</td></tr>' +
    '<tr><td>Volumes não devolvidos ao hub no próprio dia</td><td class="v">' + eur0(S.dev) + ' por ocorrência</td></tr>' +
    '</tbody></table>' +
    '<div class="small">Qualquer valor é comunicado com a evidência e tens <b>' + esc(S.resp) + ' horas</b> para responder; só é deduzido no fecho seguinte à confirmação e a ' + (D.showP && !D.showS ? 'caução' : 'garantia') + ' apenas cobre o que faltar. Não são pagos os volumes de ponto de recolha deixados a rececionista ou a pessoa não autorizada. <b>Saída:</b> com pré-aviso de ' + S.aviso + ' dias, o saldo é liquidado em ' + S.liq1 + ' dias; sem pré-aviso, no máximo em ' + S.liq2 + ' dias.</div>') : "";

  B.push('<div class="sh"><span class="n">' + (++n) + '</span><h2>Como recebes</h2></div>' + regs);
  B.push('<div class="sh"><span class="n">' + (++n) + '</span><h2>Como funciona o dia</h2></div>' + steps);
  if (resp) B.push('<div class="sh"><span class="n">' + (++n) + '</span><h2>Regras claras</h2></div>' + resp);
  B.push('<div class="sh"><span class="n">' + (++n) + '</span><h2>Próximos passos</h2></div>' +
    '<div class="next"><ol>' +
    '<li>Confirma o teu interesse' + (D.dVal ? ' até <b>' + esc(fl(D.dVal)) + '</b>' : '') + ', respondendo a esta proposta.</li>' +
    '<li>Envia os documentos: identificação, carta de condução, NIF/atividade, IBAN, apólices e matrícula.</li>' +
    '<li>Assinamos o contrato' + (D.showS && D.showP ? ' e escolhes o regime de pagamento' : '') + '.</li>' +
    '<li>Começas' + (D.dIni ? ' a <b>' + esc(fs(D.dIni)) + '</b>' : '') + ' — a primeira rota é oferecida na véspera.</li></ol>' +
    '<div class="contact"><div class="k">Fala connosco</div><div class="n">' + esc(D.kNome || "Léguas Franzinas") + '</div><div class="l">' +
    (D.kTel ? 'Telefone / WhatsApp: <b>' + esc(D.kTel) + '</b><br>' : '') + (D.kMail ? 'E-mail: <b>' + esc(D.kMail) + '</b><br>' : '') +
    'Léguas Franzinas · Hub ' + esc(H.name || "") + '</div></div></div>');

  const pages = paginate(D, B);
  $("preview").innerHTML = pages.map(h => '<div class="pwrap">' + h + '</div>').join("");

  /* ── avisos ── */
  const w = [];
  if (!HUBS.length) w.push("Não há hubs com CP4 configurados.");
  if (!D.nome) w.push("Falta o <b>nome do candidato</b>.");
  if (!sel.length) w.push("Nenhum <b>CP4</b> selecionado.");
  const miss = sel.filter(z => (D.showS && z.s == null) || (D.showP && z.p == null)).map(z => z.cp);
  if (miss.length) w.push("Tarifa por definir em: <b>" + miss.join(", ") + "</b> (aparece «a definir» no documento).");
  const diff = sel.filter(z => { const t = tableCp(z.cp); return t && (!same(z.p, t.p) || (D.showS && !same(z.s, t.s))); }).map(z => z.cp);
  if (diff.length) w.push("Valor diferente da tabela de tarifas em: <b>" + diff.join(", ") + "</b>. O contrato usa a tabela, salvo valor negociado na ficha do motorista.");
  if (HUB && !HUB.has_terms) w.push("O hub <b>" + esc(HUB.name) + "</b> não tem condições de contrato configuradas.");
  if (HUB && !HUB.address) w.push("O hub <b>" + esc(HUB.name) + "</b> não tem morada.");
  if (D.min && !hasC) w.push("Tarifa mínima ligada sem CP4 do Escalão C.");
  if (D.min && HUB && !HUB.min_fare) w.push("Tarifa mínima ligada, mas o hub não a tem ativa: o contrato não a inclui por omissão.");
  if (!D.min && HUB && HUB.min_fare && hasC) w.push("O hub tem tarifa mínima ativa e há CP4 do Escalão C, mas a proposta não a mostra.");
  if (D.sim && !D.vol) w.push("Exemplo de faturação ligado mas sem volume médio — não é mostrado.");
  if (D.dIni && D.dIni.getDay() !== 1) w.push("O início previsto não é uma segunda-feira.");
  if (pages.length > 3) w.push("A proposta ficou com <b>" + pages.length + " páginas</b> (os blocos que não cabiam passaram para a página seguinte).");
  $("warn").innerHTML = w.map(x => "• " + x).join("<br>");

  /* ── mensagem ── */
  const tarifa = mainR ? (mainR.mn !== mainR.mx ? "de " + eur(mainR.mn) + " a " + eur(mainR.mx) : eur(mainR.mn)) : "";
  const msg = (D.trat ? "Olá " + D.trat + "!" : "Olá!") + "\n\n" +
    "Segue em anexo a tua proposta da Léguas Franzinas para distribuição na zona de " + D.area + ".\n\n" +
    "Resumo:\n" +
    (tarifa ? "• " + tarifa + " por entrega (" + (D.showS ? "Regime Semanal, pago todas as " + paydayPl : "Regime Mensal") + ")\n" : "") +
    (D.vol ? "• cerca de " + D.vol + " volumes por dia, em média\n" : "") +
    (D.dias ? "• operação de " + D.dias + "\n" : "") +
    "• recolha no hub " + (H.name || "") + " até às " + S.saida + "\n\n" +
    (D.dVal ? "A proposta é válida até " + fl(D.dVal) + ". " : "") + "Se tiveres dúvidas, responde por aqui.\n\n" +
    (D.kNome ? D.kNome + " — " : "") + "Léguas Franzinas";
  $("w_msg").value = msg;
  const phone = (D.tel || "").replace(/[^\d]/g, "");
  const wa = $("b_wa");
  if (phone.length >= 9) { wa.style.display = ""; wa.href = "https://wa.me/" + (phone.length === 9 ? "351" + phone : phone) + "?text=" + encodeURIComponent(msg); }
  else wa.style.display = "none";
}

/* ── eventos ── */
$("a_hubsel").addEventListener("change", e => { applyHub(e.target.value); render(); });
["c_nome", "c_trat", "c_tel", "a_nome", "a_vol", "a_dias", "p_data", "p_val", "p_ini", "p_ref", "p_reg", "t_sim", "t_min", "t_multi", "t_resp", "k_nome", "k_tel", "k_mail"].forEach(id => {
  $(id).addEventListener("input", render); $(id).addEventListener("change", render);
});
$("b_copy").addEventListener("click", async () => {
  const ta = $("w_msg");
  try { await navigator.clipboard.writeText(ta.value); flash("Mensagem copiada."); }
  catch (e) { ta.focus(); ta.select(); try { document.execCommand("copy"); flash("Mensagem copiada."); } catch (_) { flash("Selecione o texto e copie com Ctrl+C."); } }
});
function flash(t) { $("status").textContent = t; }
/* Também corre como ficheiro isolado ou Artifact: num frame não há impressão
 * e o PDF é guardado pela capacidade "downloads", quando existe. */
const inFrame = (() => { try { return window.self !== window.top; } catch (e) { return true; } })();
if (inFrame) $("b_print").style.display = "none";
$("b_print").addEventListener("click", () => { try { window.print(); } catch (e) { } });
let downloads = null;
if (window.claude && typeof window.claude.use === "function") {
  window.claude.use("downloads").then(d => { downloads = d; }).catch(() => { });
}

function fileName(D) {
  const clean = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "");
  return "Proposta_LeguasFranzinas_" + (clean(D.nome) || "Candidato") + "_" + (clean(D.area) || "Area") + ".pdf";
}
$("b_pdf").addEventListener("click", async () => {
  const btn = $("b_pdf"); btn.disabled = true; flash("A gerar o PDF…");
  try {
    if (!window.html2canvas || !window.jspdf) throw new Error("Bibliotecas de PDF não carregaram.");
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    const root = $("render-root"); root.innerHTML = "";
    document.querySelectorAll("#preview .a4").forEach(p => root.appendChild(p.cloneNode(true)));
    const pdf = new window.jspdf.jsPDF({ unit: "mm", format: "a4", orientation: "portrait", compress: true });
    const pages = [...root.querySelectorAll(".a4")];
    for (let i = 0; i < pages.length; i++) {
      const c = await html2canvas(pages[i], { scale: 2.2, backgroundColor: "#ffffff", useCORS: true, logging: false });
      if (i > 0) pdf.addPage();
      pdf.addImage(c.toDataURL("image/jpeg", 0.93), "JPEG", 0, 0, 210, 297, undefined, "FAST");
    }
    root.innerHTML = "";
    const name = fileName(lastData);
    if (downloads) {
      try { await downloads.save({ filename: name, data: pdf.output("blob") }); flash("PDF guardado: " + name); }
      catch (err) { flash(err && err.code === "declined" ? "Download cancelado." : "Não foi possível guardar o PDF aqui (" + (err && err.code || "erro") + ")."); }
    } else if (inFrame) {
      flash("A gravação de ficheiros não está disponível nesta vista. Abra o gerador numa janela própria.");
    } else {
      pdf.save(name); flash("PDF guardado: " + name);
    }
  } catch (e) { flash("Erro ao gerar PDF: " + e.message); }
  finally { btn.disabled = false; }
});

const fao = HUBS.find(h => /f[ãa]o/i.test(h.name));
if (HUBS.length) { $("a_hubsel").value = (fao || HUBS[0]).id; applyHub($("a_hubsel").value); }
render();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => render());
})();
