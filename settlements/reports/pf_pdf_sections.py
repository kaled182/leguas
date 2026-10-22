"""Secções do PDF da pré-fatura: logótipo, resumo da operação e resumo
financeiro em 3 blocos.

O PDF segue esta ordem lógica:
  1. Quem / quando (cabeçalho e dados da PF)
  2. O que o motorista fez (KPIs, gráfico por dia, tabela por dia)
  3. Como se paga (linhas de cálculo, PUDO, bónus, descontos)
  4. Resumo financeiro: Produção → Ajustes → Fatura-recibo → Pagamento

Os valores financeiros vêm SEMPRE dos campos da pré-fatura (recalcular()).
Os números da operação vêm de services_driver_breakdown (mesma fonte do
portal), com uma linha de conferência contra as linhas da PF.
"""
from __future__ import annotations

import os
from decimal import Decimal

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

PURPLE = colors.HexColor("#5B21B6")
DOOR = colors.HexColor("#6D28D9")
SAME_DOOR = colors.HexColor("#14B8A6")
PUDO = colors.HexColor("#C4B5FD")
FAIL = colors.HexColor("#DC2626")
GREEN = colors.HexColor("#16A34A")
GRID = colors.HexColor("#E5E7EB")
MUTED = colors.HexColor("#6B7280")
INK = colors.HexColor("#111827")
LIGHT = colors.HexColor("#F3F4F6")
LIGHT_PURPLE = colors.HexColor("#EDE9FE")

FULL_W = 17 * cm
WEEKDAYS = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def eur(v):
    """€ 1 234,56 — formato português."""
    v = Decimal(v or 0).quantize(Decimal("0.01"))
    s = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",")
    return f"{'-' if v < 0 else ''}€ {s}"


def fallback_logo_path():
    """Logótipo Léguas que vem com o código (quando o configurado em
    Configurações → Empresa não existe no disco)."""
    from django.contrib.staticfiles import finders

    for rel in ("dashboard_leguas/img/logo.png", "img/logo.png"):
        p = finders.find(rel)
        if p and os.path.exists(p):
            return p
    return None


def pf_rates(pre_invoice):
    """(taxa média por pacote à porta, taxa por pacote adicional na mesma
    porta) desta pré-fatura. Sem linhas "mesma porta", usa a taxa da porta."""
    lines = list(pre_invoice.linhas.all())
    sd = [l for l in lines if "mesma porta" in (l.observacoes or "").lower()]
    door = [l for l in lines if l not in sd]
    door_n = sum(l.total_pacotes for l in door)
    sd_n = sum(l.total_pacotes for l in sd)
    door_rate = (sum((l.base_entregas for l in door), Decimal("0")) / door_n) if door_n else Decimal("0")
    sd_rate = (sum((l.base_entregas for l in sd), Decimal("0")) / sd_n) if sd_n else door_rate
    return door_rate, sd_rate


def hours_worked(x):
    """Horas entre a 1ª e a última entrega do dia (None se < 30 min)."""
    if not x.get("first") or not x.get("last"):
        return None
    h = Decimal((x["last"] - x["first"]).total_seconds()) / 3600
    return h if h >= Decimal("0.5") else None


def day_values(pre_invoice, days):
    """Valor produzido por dia, com os preços DESTA pré-fatura.

    porta × taxa média das linhas de porta + mesma porta × taxa das
    linhas "mesma porta" + PUDO do dia (PreInvoicePudo) + bónus do dia.
    A soma dos dias = base das linhas + PUDO + bónus da PF (quando a
    conferência confere).
    """
    from collections import defaultdict

    door_rate, sd_rate = pf_rates(pre_invoice)

    extra = defaultdict(Decimal)
    for p in pre_invoice.pudos.all():
        if p.data:
            extra[p.data] += p.valor or 0
    for b in pre_invoice.bonificacoes.all():
        if b.data:
            extra[b.data] += b.bonus_calculado or 0

    out = {}
    for x in days:
        out[x["date"]] = (
            x["door_normal"] * door_rate + x["same_door"] * sd_rate + extra.get(x["date"], 0)
        ).quantize(Decimal("0.01"))
    return out


def _style(name, **kw):
    base = {"fontName": "Helvetica", "fontSize": 9, "leading": 11, "textColor": INK}
    base.update(kw)
    return ParagraphStyle(name, **base)


def _kpi_cell(label, value, sub, color):
    t = Table(
        [
            [Paragraph(label, _style("kl", fontSize=7, textColor=MUTED, fontName="Helvetica-Bold"))],
            [Paragraph(str(value), _style("kv", fontSize=16, leading=19, textColor=color, fontName="Helvetica-Bold"))],
            [Paragraph(sub, _style("ks", fontSize=7, textColor=MUTED))],
        ],
        colWidths=[None],
    )
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, color),
    ]))
    return t


def _days_chart(days, values=None):
    """Barras empilhadas por dia: porta, mesma porta, PUDO. Por cima de
    cada barra: pacotes entregues e, se houver, o valor produzido."""
    width, height = FULL_W, 5.2 * cm
    d = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x, bc.y = 1.0 * cm, 0.9 * cm
    bc.width, bc.height = width - 1.4 * cm, height - 1.7 * cm
    bc.categoryAxis.style = "stacked"
    bc.data = [
        [x["door_normal"] for x in days],
        [x["same_door"] for x in days],
        [x["pudo"] for x in days],
    ]
    bc.categoryAxis.categoryNames = [x["date"].strftime("%d/%m") for x in days]
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.fontName = "Helvetica"
    bc.categoryAxis.labels.fillColor = MUTED
    bc.categoryAxis.strokeColor = GRID
    vmax = max((x["delivered"] for x in days), default=0) or 1
    step = max(1, round(vmax / 4 / 10) * 10) if vmax > 20 else max(1, vmax // 4 or 1)
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = vmax * (1.32 if values else 1.18)
    bc.valueAxis.valueStep = step
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.labels.fontName = "Helvetica"
    bc.valueAxis.labels.fillColor = MUTED
    bc.valueAxis.strokeColor = GRID
    bc.valueAxis.gridStrokeColor = GRID
    bc.valueAxis.visibleGrid = True
    bc.barSpacing = 1
    bc.groupSpacing = 6
    for i, c in enumerate((DOOR, SAME_DOOR, PUDO)):
        bc.bars[i].fillColor = c
        bc.bars[i].strokeColor = None
    d.add(bc)
    # Total entregue por cima de cada barra
    n = len(days)
    for i, x in enumerate(days):
        if not x["delivered"]:
            continue
        cx = bc.x + (i + 0.5) * bc.width / n
        cy = bc.y + x["delivered"] / bc.valueAxis.valueMax * bc.height + 2
        d.add(String(cx, cy, str(x["delivered"]), fontSize=7, fontName="Helvetica-Bold",
                     fillColor=INK, textAnchor="middle"))
        if values and values.get(x["date"]):
            d.add(String(cx, cy + 9, eur(values[x["date"]]), fontSize=6.5,
                         fontName="Helvetica-Bold", fillColor=GREEN, textAnchor="middle"))
    # Legenda
    lx = bc.x
    for label, c in (("Porta", DOOR), ("Mesma porta", SAME_DOOR), ("PUDO", PUDO)):
        d.add(Rect(lx, 0.15 * cm, 7, 7, fillColor=c, strokeColor=None))
        d.add(String(lx + 10, 0.15 * cm + 1, label, fontSize=7, fontName="Helvetica", fillColor=MUTED))
        lx += 2.6 * cm
    return d


def operation_summary(pre_invoice, section_header, bd):
    """KPIs + gráfico + tabela por dia + conferência com as linhas da PF.

    `bd` = services_driver_breakdown.driver_breakdown(driver, período da PF).
    """
    t = bd["totals"]
    if not t["delivered"] and not t["failures"]:
        return []

    out = [section_header("RESUMO DA OPERAÇÃO"), Spacer(1, 0.15 * cm)]
    completed = t["delivered"] + t["failures"]
    rate = (t["delivered"] / completed * 100) if completed else 0
    n_days = bd["n_days"] or 0
    avg = round(t["delivered"] / n_days) if n_days else 0

    days = [x for x in bd["days"] if x["delivered"] or x["failures"]]
    values = day_values(pre_invoice, days)
    worked = [values[x["date"]] for x in days if x["delivered"]]
    avg_value = (sum(worked, Decimal("0")) / len(worked)) if worked else Decimal("0")
    best = max(days, key=lambda x: values[x["date"]], default=None)
    door_rate, _sd_rate = pf_rates(pre_invoice)
    fail_value = (t["failures"] * door_rate).quantize(Decimal("0.01"))

    kpis = Table([[
        _kpi_cell("ENTREGUE", t["delivered"], f"{n_days} dias · {avg}/dia", PURPLE),
        _kpi_cell("PORTA", t["door_normal"], "preço normal", DOOR),
        _kpi_cell("MESMA PORTA", t["same_door"], "adicionais", SAME_DOOR),
        _kpi_cell("PUDO", t["pudo"], "1ª + adicionais", colors.HexColor("#7C3AED")),
        _kpi_cell("FALHAS", t["failures"],
                  f"aprox. {eur(fail_value)} não ganhos" if fail_value else f"sucesso {rate:.0f}%", FAIL),
        _kpi_cell("€ POR DIA", eur(avg_value).replace("€ ", "€"),
                  f"melhor {best['date'].strftime('%d/%m')}" if best else "—", GREEN),
    ]], colWidths=[FULL_W / 6] * 6)
    kpis.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    out += [kpis, Spacer(1, 0.2 * cm)]

    if days:
        out.append(_days_chart(days, values))

        def per_hour(value, hours):
            return eur(value / hours) if hours else "—"

        def schedule(x):
            if not x.get("first"):
                return "—"
            return f'{x["first"].strftime("%H:%M")}–{x["last"].strftime("%H:%M")}'

        total_hours = sum((hours_worked(x) or 0 for x in days), Decimal("0"))
        total_value = sum(values.values(), Decimal("0"))
        hourly_value = sum((values[x["date"]] for x in days if hours_worked(x)), Decimal("0"))
        head = ["Dia", "Entregue", "Porta", "Mesma porta", "PUDO", "Falhas", "Horário", "€/hora*", "Valor"]
        rows = [head] + [
            [f'{WEEKDAYS[x["date"].weekday()]} {x["date"].strftime("%d/%m")}', x["delivered"], x["door_normal"],
             x["same_door"] or "—", x["pudo"] or "—", x["failures"] or "—", schedule(x),
             per_hour(values[x["date"]], hours_worked(x)), eur(values[x["date"]])]
            for x in days
        ] + [["Total", t["delivered"], t["door_normal"], t["same_door"], t["pudo"], t["failures"],
              f"{total_hours:.1f} h".replace(".", ","), per_hour(hourly_value, total_hours), eur(total_value)]]
        tbl = Table(rows, colWidths=[2.0 * cm, 1.6 * cm, 1.4 * cm, 1.9 * cm, 1.2 * cm, 1.2 * cm,
                                     2.6 * cm, 2.0 * cm, 3.1 * cm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, GRID),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT]),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), LIGHT_PURPLE),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
            ("FONTNAME", (-1, 1), (-1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (-1, 1), (-1, -1), GREEN),
            ("TEXTCOLOR", (-2, 1), (-2, -1), colors.HexColor("#0E7490")),
            ("TEXTCOLOR", (-3, 1), (-3, -2), MUTED),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        for i, x in enumerate(days, start=1):
            if x["date"].weekday() == 6:
                tbl.setStyle(TableStyle([("TEXTCOLOR", (0, i), (0, i), FAIL)]))
        # Melhor dia em destaque
        if best:
            i = days.index(best) + 1
            tbl.setStyle(TableStyle([("BACKGROUND", (0, i), (-1, i), colors.HexColor("#DCFCE7"))]))
        # Nota do €/hora fica sempre junto da tabela
        out += [Spacer(1, 0.1 * cm), KeepTogether([tbl, Spacer(1, 0.1 * cm), Paragraph(
            "* € por hora = valor do dia ÷ tempo entre a 1ª e a última entrega. É uma estimativa: "
            "não inclui a carga no hub nem o regresso. Dias com menos de 30 min ficam com —.",
            _style("fnh", fontSize=7, leading=8.5, textColor=MUTED))])]

    out += previous_comparison(pre_invoice, bd, values)

    # Conferência: linhas da PF + PUDO da PF = total do sistema
    n_lines = sum(
        l.total_pacotes for l in pre_invoice.linhas.all()
        if l.parceiro and l.parceiro.name.upper() == "CAINIAO"
    )
    n_pudo = sum(p.n_pacotes for p in pre_invoice.pudos.all())
    ok = n_lines + n_pudo == t["delivered"]
    verdict = (
        '<font color="#16A34A"><b>confere</b></font>' if ok
        else '<font color="#DC2626"><b>não confere</b></font>'
    )
    msg = (
        f"<b>Conferência:</b> nesta pré-fatura {n_lines} pacotes nas linhas"
        f" + {n_pudo} PUDO = <b>{n_lines + n_pudo}</b> · registos Cainiao: <b>{t['delivered']}</b>"
        f" — {verdict}"
    )
    out += [Spacer(1, 0.15 * cm), Paragraph(msg, _style("conf", fontSize=8, textColor=MUTED)), Spacer(1, 0.5 * cm)]
    return out


def _pct_change(new, old):
    if not old:
        return None
    return (Decimal(new) - Decimal(old)) / Decimal(old) * 100


def previous_comparison(pre_invoice, bd, values):
    """Tabela "esta PF contra a PF anterior" do mesmo motorista.

    Compara valores por dia (os períodos podem ter durações diferentes).
    """
    from settlements.models import DriverPreInvoice
    from settlements.services_driver_breakdown import driver_breakdown

    prev = (
        DriverPreInvoice.objects
        .filter(driver=pre_invoice.driver, periodo_fim__lt=pre_invoice.periodo_inicio)
        .exclude(status__in=("RASCUNHO", "REPROVADO"))
        .order_by("-periodo_fim").first()
    )
    if not prev:
        return []
    pbd = driver_breakdown(prev.driver, prev.periodo_inicio, prev.periodo_fim)

    def metrics(pf, b):
        t, n = b["totals"], b["n_days"] or 0
        done = t["delivered"] + t["failures"]
        return {
            "delivered": t["delivered"], "days": n,
            "per_day": Decimal(t["delivered"]) / n if n else Decimal("0"),
            "eur_day": pf.subtotal_bruto / n if n else Decimal("0"),
            "production": pf.subtotal_bruto,
            "success": Decimal(t["delivered"]) / done * 100 if done else Decimal("0"),
        }

    a, b = metrics(prev, pbd), metrics(pre_invoice, bd)
    rows_def = [
        ("Produção por dia", "eur_day", eur),
        ("Entregas por dia", "per_day", lambda v: f"{v:.0f}"),
        ("Taxa de sucesso", "success", lambda v: f"{v:.1f}%".replace(".", ",")),
        ("Dias trabalhados", "days", str),
        ("Entregas", "delivered", str),
        ("Produção bruta", "production", eur),
    ]
    head = ["", f"{prev.numero} · {prev.periodo_inicio:%d/%m}–{prev.periodo_fim:%d/%m}",
            f"Esta PF · {pre_invoice.periodo_inicio:%d/%m}–{pre_invoice.periodo_fim:%d/%m}", "Variação"]
    rows, styles = [head], []
    for i, (label, key, fmt) in enumerate(rows_def, start=1):
        ch = _pct_change(b[key], a[key])
        if ch is None:
            txt = "—"
        else:
            txt = f"{'+' if ch >= 0 else ''}{ch:.1f}%".replace(".", ",")
            styles.append(("TEXTCOLOR", (3, i), (3, i), GREEN if ch >= 0 else FAIL))
        rows.append([label, fmt(a[key]), fmt(b[key]), txt])
    tbl = Table(rows, colWidths=[4.2 * cm, 4.6 * cm, 4.6 * cm, 3.6 * cm])
    tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("FONTNAME", (0, 1), (0, 2), "Helvetica-Bold"),
        ("FONTNAME", (2, 1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ] + styles))
    title = Paragraph("<b>Comparação com a pré-fatura anterior</b> — compare os valores por dia "
                      "(os períodos podem ter durações diferentes).",
                      _style("cmpt", fontSize=8, textColor=MUTED))
    return [Spacer(1, 0.3 * cm), KeepTogether([title, Spacer(1, 0.1 * cm), tbl])]


def same_door_section(pre_invoice, section_header, bd):
    """Lista das portas com vários pacotes no mesmo dia (como a lista PUDO)."""
    groups = bd.get("same_door_groups") or []
    if not groups:
        return []
    door_rate, sd_rate = pf_rates(pre_invoice)
    addr_style = _style("sda", fontSize=8, leading=10)
    wb_style = _style("sdw", fontSize=6.5, leading=8, textColor=MUTED)
    head = ["Data", "Morada", "Pacotes", "Valor"]
    rows = [head]
    total = Decimal("0")
    for g in groups:
        value = (door_rate + (g["n"] - 1) * sd_rate).quantize(Decimal("0.01"))
        total += value
        addr = (g["address"] or "—").replace("&", "&amp;").replace("<", "&lt;")
        rows.append([
            g["date"].strftime("%d/%m/%Y"),
            [Paragraph(f'{addr} <font color="#6B7280">{g["zip_code"]}</font>', addr_style),
             Paragraph(" · ".join(g["waybills"]), wb_style)],
            f'1 + {g["n"] - 1}',
            eur(value),
        ])
    n_extra = sum(g["n"] - 1 for g in groups)
    rows.append(["", f"{len(groups)} portas · {n_extra} pacotes adicionais", "", eur(total)])
    tbl = Table(rows, colWidths=[2.4 * cm, 10.2 * cm, 1.8 * cm, 2.6 * cm], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D9488")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#CCFBF1")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    note = Paragraph(
        f"Regra mesma porta: o 1º pacote de cada porta é pago a {eur(door_rate)} e cada adicional "
        f"a {eur(sd_rate)}. A mesma porta = mesma morada ou mesma paragem Cainiao, no mesmo dia.",
        _style("sdn", fontSize=7, leading=8.5, textColor=MUTED))
    return [section_header("MESMA PORTA", colors.HexColor("#0D9488")), Spacer(1, 0.1 * cm),
            tbl, Spacer(1, 0.1 * cm), note, Spacer(1, 0.5 * cm)]


def financial_summary(pre_invoice, section_header, n_delivered=None, n_days=None, n_failures=0):
    """Resumo financeiro em 3 blocos: Produção → Ajustes → Pagamento.

    Só mostra linhas com valor (menos ruído). Os totais vêm dos campos da PF.
    """
    pf = pre_invoice
    vat = pf.vat_amount or Decimal("0")
    irs = pf.irs_retention_amount or Decimal("0")
    comissoes = pf.total_comissoes_indicacao or Decimal("0")

    label = _style("fl", fontSize=9)
    label_b = _style("flb", fontSize=9, fontName="Helvetica-Bold")
    note = _style("fn", fontSize=7, leading=8.5, textColor=MUTED)
    val = _style("fv", fontSize=9, alignment=TA_RIGHT)
    val_b = _style("fvb", fontSize=10, alignment=TA_RIGHT, fontName="Helvetica-Bold")
    block = _style("fbk", fontSize=8, fontName="Helvetica-Bold", textColor=PURPLE)

    rows, styles = [], []

    def add_block(title):
        rows.append([Paragraph(title, block), "", ""])
        i = len(rows) - 1
        styles.extend([("SPAN", (0, i), (-1, i)), ("TOPPADDING", (0, i), (-1, i), 8),
                       ("LINEBELOW", (0, i), (-1, i), 0.8, PURPLE)])

    def add(text, value, hint="", sign=""):
        color = "#DC2626" if sign == "-" else "#111827"
        rows.append([Paragraph(text, label), Paragraph(hint, note),
                     Paragraph(f'<font color="{color}">{sign}{eur(value)}</font>', val)])

    def add_total(text, value, bg, hint=""):
        rows.append([Paragraph(text, label_b), Paragraph(hint, note), Paragraph(eur(value), val_b)])
        i = len(rows) - 1
        styles.extend([("BACKGROUND", (0, i), (-1, i), bg), ("LINEABOVE", (0, i), (-1, i), 0.6, GRID)])

    # 1) Produção
    add_block("1 · PRODUÇÃO (o que o motorista ganhou)")
    sd_lines = [l for l in pf.linhas.all() if "mesma porta" in (l.observacoes or "").lower()]
    sd_amount = sum((l.base_entregas for l in sd_lines), Decimal("0"))
    sd_n = sum(l.total_pacotes for l in sd_lines)
    door_amount = pf.base_entregas - sd_amount
    door_n = sum(l.total_pacotes for l in pf.linhas.all()) - sd_n
    add("Entregas à porta", door_amount, f"{door_n} pacotes")
    if sd_amount:
        add("Mesma porta (adicionais)", sd_amount, f"{sd_n} pacotes a valor reduzido")
    if pf.total_pudo:
        add("Entregas PUDO", pf.total_pudo, "Fórmula 1ª + adicionais")
    if pf.total_bonus:
        add("Bónus domingo / feriado", pf.total_bonus)
    if pf.total_extras:
        add("Serviços extra", pf.total_extras, "Arrasto, apoio, ajustes a crédito")
    if pf.ajuste_manual:
        add("Ajuste manual", pf.ajuste_manual)
    add_total("Produção bruta", pf.subtotal_bruto, LIGHT_PURPLE)

    # 2) Ajustes ao serviço
    has_adj = pf.penalizacoes_gerais or pf.total_pacotes_perdidos or comissoes
    add_block("2 · AJUSTES AO SERVIÇO")
    if pf.penalizacoes_gerais:
        add("Penalizações", pf.penalizacoes_gerais, "Descontos gerais", "-")
    if pf.total_pacotes_perdidos:
        add("Pacotes perdidos / reclamações", pf.total_pacotes_perdidos, "Ver detalhe acima", "-")
    if comissoes:
        add("Comissões de indicação", comissoes, "Motoristas indicados", "+")
    if not has_adj:
        rows.append([Paragraph("Sem descontos neste período", note), "", ""])
    if vat:
        add_total("Base faturável (s/ IVA)", pf.base_faturavel, LIGHT)
        add("IVA 23%", vat, "Regime normal, sobre a produção", "+")
    add_total("VALOR DA FATURA-RECIBO", pf.total_fatura, colors.HexColor("#D1FAE5"),
              "Valor do recibo que o motorista emite")

    # 3) Pagamento
    add_block("3 · PAGAMENTO")
    if pf.total_adiantamentos:
        add("Adiantamentos / combustível", pf.total_adiantamentos, "Já pago ao motorista", "-")
    else:
        rows.append([Paragraph("Sem adiantamentos neste período", note), "", ""])

    table = Table(rows, colWidths=[6.2 * cm, 7.3 * cm, 3.5 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ] + styles))

    total_final = pf.total_com_iva if vat else pf.total_a_receber
    big = Table([[
        Paragraph("TOTAL A RECEBER", _style("tl", fontSize=13, textColor=colors.white, fontName="Helvetica-Bold")),
        Paragraph(eur(total_final), _style("tv", fontSize=17, leading=20, textColor=colors.white,
                                           fontName="Helvetica-Bold", alignment=TA_RIGHT)),
    ]], colWidths=[10 * cm, 7 * cm])
    big.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 11), ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))

    block_items = [section_header("RESUMO FINANCEIRO"), Spacer(1, 0.1 * cm), table, Spacer(1, 0.2 * cm), big]

    if irs:
        liq = Table([[
            Paragraph("Retenção IRS", _style("il", fontSize=9, textColor=colors.white)),
            Paragraph(f"-{eur(irs)}", _style("iv", fontSize=9, textColor=colors.white, alignment=TA_RIGHT)),
        ], [
            Paragraph("<b>TOTAL LÍQUIDO (após IRS)</b>", _style("ll", fontSize=11, textColor=colors.white)),
            Paragraph(f"<b>{eur(pf.total_liquido)}</b>", _style("lv", fontSize=13, leading=15,
                                                               textColor=colors.white, alignment=TA_RIGHT)),
        ]], colWidths=[10 * cm, 7 * cm])
        liq.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0E7490")),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        block_items += [Spacer(1, 0.15 * cm), liq]

    # Indicadores: quanto vale cada pacote e cada dia
    if n_delivered:
        per_pkg = pf.subtotal_bruto / n_delivered
        per_day = pf.subtotal_bruto / n_days if n_days else Decimal("0")
        discounts = (pf.penalizacoes_gerais or 0) + (pf.total_pacotes_perdidos or 0)
        discount_pct = (discounts / pf.subtotal_bruto * 100) if pf.subtotal_bruto else 0
        fail_txt = ""
        if n_failures:
            fail_value = n_failures * pf_rates(pf)[0]
            fail_txt = f" · {n_failures} falhas = aprox. <b>{eur(fail_value)}</b> não ganhos"
        ind = Paragraph(
            f"<b>Indicadores:</b> produção por pacote entregue <b>{eur(per_pkg)}</b>"
            f" · produção por dia trabalhado <b>{eur(per_day)}</b>"
            f" · descontos = <b>{discount_pct:.1f}%</b> da produção{fail_txt}",
            _style("ind", fontSize=8, textColor=MUTED, alignment=TA_LEFT),
        )
        block_items += [Spacer(1, 0.25 * cm), ind]
    # O resumo financeiro nunca se parte entre páginas
    return [KeepTogether(block_items)]


def numbered_canvas(numero, generated_at):
    """Canvas que escreve em todas as páginas: nº da PF, data de emissão e
    "Página N de M" (precisa de duas passagens: guarda as páginas e escreve
    o total no fim)."""
    from reportlab.pdfgen import canvas as rl_canvas

    class _Canvas(rl_canvas.Canvas):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self.setFont("Helvetica", 7)
                self.setFillColor(MUTED)
                w = self._pagesize[0]
                self.drawString(2 * cm, 1.1 * cm, f"{numero} · Léguas Franzinas · emitido {generated_at}")
                self.drawRightString(w - 2 * cm, 1.1 * cm, f"Página {self._pageNumber} de {total}")
                super().showPage()
            super().save()

    return _Canvas
