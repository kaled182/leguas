"""PDF do relatório de motoristas: do hub (A4 horizontal) e de um motorista (A4 vertical)."""
from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

PURPLE = colors.HexColor("#2E0A3E")
ORANGE = colors.HexColor("#F7941D")
LILAC = colors.HexColor("#EFE7F6")
GRID = colors.HexColor("#D9D2E3")
MUTED = colors.HexColor("#5E5470")

TITLE = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=14, textColor=PURPLE, leading=17)
SUB = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, textColor=MUTED, leading=11)
H2 = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10.5, textColor=PURPLE,
                    leading=13, spaceBefore=8, spaceAfter=4)
CELL = ParagraphStyle("c", fontName="Helvetica", fontSize=7.5, leading=9)
VAT_SHORT = {"normal": "Normal", "isento": "Isento", "simplificado": "Simplif."}
NOTE = ParagraphStyle("n", fontName="Helvetica", fontSize=7.5, textColor=MUTED, leading=10)


def _num(v, dec=0):
    if v is None:
        return "-"
    q = Decimal(v).quantize(Decimal(1) if dec == 0 else Decimal("0.01"))
    s = f"{q:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s


def eur(v):
    return "-" if v is None else f"{_num(v, 2)} €"


def _d(day):
    return day.strftime("%d/%m/%Y") if day else "-"


def _period(date_from, date_to):
    return f"{_d(date_from)} a {_d(date_to)}"


def _table(rows, widths, head_rows=1, total_rows=(), right_from=1, zebra=True):
    t = Table(rows, colWidths=widths, repeatRows=head_rows)
    st = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 7.5),
        ("FONT", (0, 0), (-1, head_rows - 1), "Helvetica-Bold", 7),
        ("TEXTCOLOR", (0, 0), (-1, head_rows - 1), colors.white),
        ("BACKGROUND", (0, 0), (-1, head_rows - 1), PURPLE),
        ("ALIGN", (right_from, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, head_rows), (-1, -1), 0.25, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if zebra:
        for i in range(head_rows, len(rows)):
            if (i - head_rows) % 2:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAF8FC")))
    for i in total_rows:
        st += [("FONT", (0, i), (-1, i), "Helvetica-Bold", 7.5),
               ("BACKGROUND", (0, i), (-1, i), LILAC)]
    t.setStyle(TableStyle(st))
    return t


def _footer(text):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        w, _h = doc.pagesize
        canvas.drawString(doc.leftMargin, 0.8 * cm, text)
        canvas.drawRightString(w - doc.rightMargin, 0.8 * cm, f"Página {doc.page}")
        canvas.restoreState()
    return draw


def _header(title, sub):
    return [Paragraph(f"Léguas Franzinas · {title}", TITLE), Paragraph(sub, SUB), Spacer(1, 6)]


def _signatures(width):
    t = Table([["Conferido por", "", "Data", "", "Aprovado por"]],
              colWidths=[width * 0.28, width * 0.08, width * 0.18, width * 0.08, width * 0.28])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), MUTED),
        ("LINEABOVE", (0, 0), (0, 0), 0.6, colors.grey),
        ("LINEABOVE", (2, 0), (2, 0), 0.6, colors.grey),
        ("LINEABOVE", (4, 0), (4, 0), 0.6, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([Spacer(1, 28), t])


def _emitted(user):
    who = (user.get_full_name() or user.username) if user else ""
    return f"Emitido em {timezone.localtime():%d/%m/%Y %H:%M}" + (f" por {who}" if who else "")


def hub_pdf(report, hub_label, date_from, date_to, user=None):
    """Uma linha por motorista, agrupada por frota, com subtotais e assinaturas."""
    buf = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.4 * cm,
                            title=f"Relatório de motoristas {hub_label}")
    width = page[0] - doc.leftMargin - doc.rightMargin
    tot = report["total"]
    story = _header(
        f"Relatório de motoristas · {hub_label}",
        f"Período {_period(date_from, date_to)} · {tot['drivers']} motoristas · {_emitted(user)}",
    )
    kpi = [["Entregues", "Porta", "Mesma porta", "PUDO", "Falhas", "Sem IVA", "IVA", "Com IVA"],
           [_num(tot["delivered"]), _num(tot["door_normal"]), _num(tot["same_door"]),
            _num(tot["pudo"]), _num(tot["failures"]), eur(tot["amount"]), eur(tot["vat"]),
            eur(tot["with_vat"])]]
    k = Table(kpi, colWidths=[width / 8] * 8)
    k.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica", 7), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 11), ("TEXTCOLOR", (0, 1), (-1, 1), PURPLE),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF9FD")),
    ]))
    story += [k, Spacer(1, 10)]

    head = ["Motorista", "Regime IVA", "Dias", "Entregues", "Porta", "Mesma\nporta", "PUDO",
            "Falhas", "% suc.", "Sem IVA", "IVA", "Com IVA", "PF", "OK"]
    widths = [0.20, 0.07, 0.04, 0.065, 0.06, 0.06, 0.045, 0.05, 0.05, 0.085, 0.07, 0.085, 0.09, 0.03]
    widths = [w * width for w in widths]
    rows, totals = [head], []
    for g in report["groups"]:
        fleet = g["fleet"].nome if g["fleet"] else "Motoristas diretos"
        rows.append([Paragraph(f"<b>{fleet}</b>", CELL)] + [""] * 13)
        for r in g["rows"]:
            d = r["driver"]
            name = d.nome_completo
            if r["other_hubs"]:
                name += f' <font color="#5E5470">(também {", ".join(r["other_hubs"])})</font>'
            pf = r["pf"]
            pf_txt = f"{pf.numero} {pf.get_status_display()}" if pf else "Sem PF"
            rows.append([
                Paragraph(name, CELL), VAT_SHORT.get(d.vat_regime, "Isento"), r["days"],
                _num(r["delivered"]), _num(r["door_normal"]), _num(r["same_door"]),
                _num(r["pudo"]), _num(r["failures"]),
                f'{_num(r["success_pct"], 0)} %' if r["success_pct"] is not None else "-",
                eur(r["amount"]), eur(r["vat"]), eur(r["with_vat"]),
                Paragraph(pf_txt, CELL), "",
            ])
        t = g["total"]
        rows.append([f"Subtotal {fleet}", "", "", _num(t["delivered"]), _num(t["door_normal"]),
                     _num(t["same_door"]), _num(t["pudo"]), _num(t["failures"]), "",
                     eur(t["amount"]), eur(t["vat"]), eur(t["with_vat"]), "", ""])
        totals.append(len(rows) - 1)
    rows.append(["Total", "", "", _num(tot["delivered"]), _num(tot["door_normal"]),
                 _num(tot["same_door"]), _num(tot["pudo"]), _num(tot["failures"]), "",
                 eur(tot["amount"]), eur(tot["vat"]), eur(tot["with_vat"]), "", ""])
    totals.append(len(rows) - 1)
    table = _table(rows, widths, total_rows=totals, right_from=2, zebra=False)
    st = []
    for i, row in enumerate(rows[1:], start=1):
        if i in totals:
            continue
        if row[3] == "":  # cabeçalho da frota
            st += [("SPAN", (0, i), (-1, i)), ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F6F1FA"))]
        else:  # caixa para marcar a conferência
            st.append(("BOX", (-1, i), (-1, i), 0.4, MUTED))
    table.setStyle(TableStyle(st))
    story.append(table)

    alerts = report["alerts"]
    notes = ["Valor sem IVA: entregas à porta (preço por CP ou preço do motorista), mesma porta e PUDO. "
             "IVA 23 % só no regime normal. Bónus, extras, descontos e adiantamentos estão na PF."]
    if alerts["orphans_n"]:
        notes.append(f"{alerts['orphans_n']} entregas do período não pertencem a nenhum motorista com ficha.")
    if alerts["shared_n"]:
        notes.append(f"{alerts['shared_n']} entregas pertencem a mais de um motorista.")
    story += [Spacer(1, 6)] + [Paragraph(n, NOTE) for n in notes] + [_signatures(width)]
    doc.build(story, onFirstPage=_footer(f"Relatório de motoristas · {hub_label} · {_period(date_from, date_to)}"),
              onLaterPages=_footer(f"Relatório de motoristas · {hub_label} · {_period(date_from, date_to)}"))
    return buf.getvalue()


def driver_pdf(detail, user=None):
    """Resumo na página 1; depois dia a dia, por CP4 e grupos de mesma porta."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.3 * cm, bottomMargin=1.4 * cm)
    width = A4[0] - doc.leftMargin - doc.rightMargin
    d = detail["driver"]
    date_from, date_to = detail["period"]
    tot = detail["total"]
    doc.title = f"Relatório {d.nome_completo}"
    story = _header(f"Relatório do motorista", f"Período {_period(date_from, date_to)} · {_emitted(user)}")

    ident = [
        ["Motorista", d.nome_completo, "NIF", d.nif or "-"],
        ["Logins", Paragraph(", ".join(detail["logins"]) or "-", CELL), "Frota",
         d.empresa_parceira.nome if d.empresa_parceira else "Direto"],
        ["Regime IVA", d.get_vat_regime_display(), "Preço base", eur(detail["base_price"])],
    ]
    t = Table(ident, colWidths=[width * 0.14, width * 0.42, width * 0.14, width * 0.30])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8.5),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8), ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED), ("TEXTCOLOR", (2, 0), (2, -1), MUTED),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [t, Paragraph("Entregas por hub", H2)]

    rows = [["Hub", "Dias", "Entregues", "Porta", "Mesma porta", "PUDO", "Falhas", "Sem IVA"]]
    for h in detail["hubs"]:
        rows.append([h["hub"], h["days"], _num(h["delivered"]), _num(h["door_normal"]),
                     _num(h["same_door"]), _num(h["pudo"]), _num(h["failures"]), eur(h["amount"])])
    rows.append(["Total", tot["days"], _num(tot["delivered"]), _num(tot["door_normal"]),
                 _num(tot["same_door"]), _num(tot["pudo"]), _num(tot["failures"]), eur(tot["amount"])])
    story.append(_table(rows, [width * w for w in (0.22, 0.08, 0.12, 0.11, 0.13, 0.09, 0.1, 0.15)],
                        total_rows=[len(rows) - 1]))

    story.append(Paragraph("Valores", H2))
    vals = [["Produção (sem IVA)", eur(tot["amount"])],
            ["IVA (23 % no regime normal)", eur(detail["vat"])],
            ["Valor com IVA", eur(detail["with_vat"])]]
    if detail["irs"]:
        vals.append(["Retenção IRS", f"- {eur(detail['irs'])}"])
    v = _table([["Item", "Valor"]] + vals, [width * 0.7, width * 0.3], total_rows=[3])
    story.append(v)

    pf = detail["pf"]
    story.append(Paragraph("Pré-fatura", H2))
    if pf:
        pf_rows = [
            ["Item", "Valor"],
            ["Entregas na PF", eur(pf.base_entregas)], ["PUDO na PF", eur(pf.total_pudo)],
            ["Bónus", eur(pf.total_bonus)], ["Extras", eur(pf.total_extras)],
            ["Ajuste manual", eur(pf.ajuste_manual)],
            ["Penalizações", f"- {eur(pf.penalizacoes_gerais)}"],
            ["Pacotes perdidos", f"- {eur(pf.total_pacotes_perdidos)}"],
            ["IVA", eur(pf.vat_amount)], ["Retenção IRS", f"- {eur(pf.irs_retention_amount)}"],
            ["Adiantamentos", f"- {eur(pf.total_adiantamentos)}"],
            ["Total a receber (sem IVA, depois dos adiantamentos)", eur(pf.total_a_receber)],
        ]
        story.append(Paragraph(
            f"{pf.numero} · {pf.get_status_display()} · {_period(pf.periodo_inicio, pf.periodo_fim)}", NOTE))
        story.append(_table(pf_rows, [width * 0.7, width * 0.3], total_rows=[len(pf_rows) - 1]))
        if pf.periodo_inicio == date_from and pf.periodo_fim == date_to:
            diff = tot["amount"] - (pf.base_entregas + pf.total_pudo)
            story.append(Paragraph(
                f"Diferença entre o relatório e a PF (entregas + PUDO): <b>{eur(diff)}</b>.", NOTE))
        else:
            story.append(Paragraph("O período da PF é diferente do período do relatório. "
                                   "Não comparo os valores.", NOTE))
    else:
        story.append(Paragraph("Não há pré-fatura para este período.", NOTE))
    story.append(_signatures(width))

    story += [PageBreak(), Paragraph("Dia a dia", H2)]
    rows = [["Data", "Entregues", "Porta", "Mesma porta", "PUDO", "Falhas", "1.ª entrega",
             "Última", "Sem IVA"]]
    for x in detail["by_day"]:
        rows.append([_d(x["date"]), _num(x["delivered"]), _num(x["door_normal"]), _num(x["same_door"]),
                     _num(x["pudo"]), _num(x["failures"]),
                     x["first"].strftime("%H:%M") if x["first"] else "-",
                     x["last"].strftime("%H:%M") if x["last"] else "-", eur(x["amount"])])
    story.append(_table(rows, [width * w for w in (0.13, 0.1, 0.09, 0.12, 0.08, 0.08, 0.12, 0.1, 0.18)]))

    story.append(Paragraph("Por CP4", H2))
    rows = [["CP4", "Hub", "Entregues", "Porta", "Mesma porta", "PUDO", "Preço à porta", "Sem IVA"]]
    for x in detail["by_cp"]:
        rows.append([x["cp4"] or "-", x["hub"], _num(x["delivered"]), _num(x["door_normal"]),
                     _num(x["same_door"]), _num(x["pudo"]),
                     " / ".join(eur(u) for u in x["unit"]) or "-", eur(x["amount"])])
    story.append(_table(rows, [width * w for w in (0.08, 0.16, 0.1, 0.09, 0.12, 0.08, 0.22, 0.15)], right_from=2))

    if detail["same_door"]:
        story.append(Paragraph(f"Mesma porta ({len(detail['same_door'])} moradas)", H2))
        story.append(Paragraph("A 1.ª guia da morada conta como porta. As guias extra são pagas "
                               "ao preço de mesma porta.", NOTE))
        rows = [["Data", "Morada", "CP", "Extra", "Guias"]]
        for x in detail["same_door"]:
            rows.append([_d(x["date"]), Paragraph(x["address"][:90], CELL), x["zip"], x["n"],
                         Paragraph(", ".join(x["waybills"]), CELL)])
        story.append(_table(rows, [width * w for w in (0.11, 0.37, 0.1, 0.07, 0.35)], right_from=3))
        story[-1].setStyle(TableStyle([("ALIGN", (4, 0), (4, -1), "LEFT")]))

    label = f"{d.nome_completo} · {_period(date_from, date_to)}"
    doc.build(story, onFirstPage=_footer(label), onLaterPages=_footer(label))
    return buf.getvalue()
