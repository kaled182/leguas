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


def _days_chart(days):
    """Barras empilhadas por dia: porta, mesma porta, PUDO."""
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
    bc.valueAxis.valueMax = vmax * 1.18
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

    kpis = Table([[
        _kpi_cell("TOTAL ENTREGUE", t["delivered"], f"{n_days} dias · média {avg}/dia", PURPLE),
        _kpi_cell("PORTA", t["door_normal"], "preço normal", DOOR),
        _kpi_cell("MESMA PORTA", t["same_door"], "pacotes adicionais", SAME_DOOR),
        _kpi_cell("PUDO", t["pudo"], "1ª + adicionais", colors.HexColor("#7C3AED")),
        _kpi_cell("FALHAS", t["failures"], f"sucesso {rate:.1f}%", FAIL),
    ]], colWidths=[FULL_W / 5] * 5)
    kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    out += [kpis, Spacer(1, 0.2 * cm)]

    days = [x for x in bd["days"] if x["delivered"] or x["failures"]]
    if days:
        out.append(_days_chart(days))

        head = ["Dia", "Total entregue", "Porta", "Mesma porta", "PUDO", "Falhas"]
        rows = [head] + [
            [x["date"].strftime("%d/%m"), x["delivered"], x["door_normal"],
             x["same_door"] or "—", x["pudo"] or "—", x["failures"] or "—"]
            for x in days
        ] + [["Total", t["delivered"], t["door_normal"], t["same_door"], t["pudo"], t["failures"]]]
        tbl = Table(rows, colWidths=[2.4 * cm, 3.4 * cm, 2.8 * cm, 3 * cm, 2.6 * cm, 2.8 * cm], repeatRows=1)
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
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        out += [Spacer(1, 0.1 * cm), tbl]

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


def financial_summary(pre_invoice, section_header, n_delivered=None, n_days=None):
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
        ind = Paragraph(
            f"<b>Indicadores:</b> produção por pacote entregue <b>{eur(per_pkg)}</b>"
            f" · produção por dia trabalhado <b>{eur(per_day)}</b>"
            f" · descontos = <b>{discount_pct:.1f}%</b> da produção",
            _style("ind", fontSize=8, textColor=MUTED, alignment=TA_LEFT),
        )
        block_items += [Spacer(1, 0.25 * cm), ind]
    # O resumo financeiro nunca se parte entre páginas
    return [KeepTogether(block_items)]
