"""Caderneta anual do motorista — PDF com todos os pagamentos no ano.

Útil para o motorista no fim do ano fiscal: lista todas as PFs pagas,
total, médias mensais. Pode também servir para entregar à contabilidade.
"""
from decimal import Decimal
from io import BytesIO

from django.http import HttpResponse


def render_caderneta_pdf(driver, year):
    """Devolve HttpResponse com PDF da caderneta anual.

    Lista todas as DriverPreInvoice do motorista no ano (todos os
    estados), agrupadas por mês, com total, IVA, IRS e líquido.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError:
        return HttpResponse(
            "ReportLab não está instalado.", status=500,
        )

    from settlements.models import DriverPreInvoice

    pfs = (
        DriverPreInvoice.objects
        .filter(driver=driver, periodo_inicio__year=year)
        .order_by("periodo_inicio")
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title", parent=styles["Heading1"],
        textColor=colors.HexColor("#4f46e5"), alignment=1, fontSize=18,
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12)

    elements = []
    elements.append(Paragraph(f"Caderneta Anual — {year}", title))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph(
        f"<b>Motorista:</b> {driver.nome_completo}", styles["Normal"],
    ))
    elements.append(Paragraph(
        f"<b>NIF:</b> {driver.nif or '—'} · "
        f"<b>Apelido:</b> {driver.apelido or '—'}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 0.5*cm))

    if not pfs.exists():
        elements.append(Paragraph(
            f"<i>Sem pré-faturas registadas em {year}.</i>",
            styles["Normal"],
        ))
        doc.build(elements)
        response = HttpResponse(buf.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="caderneta_{year}_{driver.id}.pdf"'
        )
        return response

    # Tabela
    headers = [
        "Nº", "Período", "Bruto", "IVA", "IRS", "Líquido", "Estado", "Pago em",
    ]
    data = [headers]
    total_bruto = Decimal("0")
    total_iva = Decimal("0")
    total_irs = Decimal("0")
    total_liquido = Decimal("0")
    total_pago = Decimal("0")
    n_pago = 0

    for pf in pfs:
        bruto = pf.total_a_receber or Decimal("0")
        iva = pf.vat_amount or Decimal("0")
        irs = pf.irs_retention_amount or Decimal("0")
        liquido = bruto - irs  # caderneta usa bruto - retenção
        data.append([
            pf.numero,
            f"{pf.periodo_inicio.strftime('%d/%m')}–{pf.periodo_fim.strftime('%d/%m')}",
            f"€{bruto:.2f}",
            f"€{iva:.2f}",
            f"€{irs:.2f}",
            f"€{liquido:.2f}",
            pf.get_status_display(),
            pf.data_pagamento.strftime("%d/%m") if pf.data_pagamento else "—",
        ])
        total_bruto += bruto
        total_iva += iva
        total_irs += irs
        total_liquido += liquido
        if pf.status == "PAGO":
            total_pago += bruto
            n_pago += 1

    data.append([
        "", "TOTAL",
        f"€{total_bruto:.2f}", f"€{total_iva:.2f}",
        f"€{total_irs:.2f}", f"€{total_liquido:.2f}", "", "",
    ])

    tbl = Table(data, colWidths=[
        2*cm, 2.6*cm, 2*cm, 1.6*cm, 1.6*cm, 2*cm, 2.4*cm, 1.8*cm,
    ])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (5, -1), "RIGHT"),
        ("ALIGN", (6, 0), (7, -1), "CENTER"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0e7ff")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 0.5*cm))

    # Resumo
    elements.append(Paragraph("Resumo", h2))
    summary_data = [
        ["PFs no ano", str(pfs.count())],
        ["Pagas", f"{n_pago} ({float(total_pago):.2f} €)"],
        ["Bruto total", f"€{float(total_bruto):.2f}"],
        ["IVA acumulado", f"€{float(total_iva):.2f}"],
        ["Retenção IRS", f"€{float(total_irs):.2f}"],
        ["Líquido total", f"€{float(total_liquido):.2f}"],
    ]
    sumtbl = Table(summary_data, colWidths=[5*cm, 5*cm])
    sumtbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    elements.append(sumtbl)

    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph(
        f"<font size=7 color='#6b7280'>"
        f"Documento gerado automaticamente · {driver.nome_completo} · {year}"
        f"</font>",
        styles["Normal"],
    ))

    doc.build(elements)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="caderneta_{year}_{driver.id}.pdf"'
    )
    return response
