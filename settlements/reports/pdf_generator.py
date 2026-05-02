"""
PDFGenerator: Gerador de PDFs de settlement para motoristas.
Usa reportlab para criar extratos detalhados.
"""

from datetime import datetime
from io import BytesIO

from django.core.files.base import ContentFile

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PDFGenerator:
    """
    Gera PDFs de extratos de settlements e invoices.
    """

    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "reportlab não está instalado. " "Instale com: pip install reportlab"
            )

        self.styles = getSampleStyleSheet()
        self.buffer = None

    def generate_settlement_pdf(self, settlement):
        """
        Gera PDF de extrato de settlement para motorista.

        Args:
            settlement: DriverSettlement instance

        Returns:
            BytesIO com o PDF gerado
        """
        self.buffer = BytesIO()

        # Criar documento
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        # Elementos do PDF
        elements = []

        # Header
        elements.append(self._create_header())
        elements.append(Spacer(1, 0.5 * cm))

        # Título
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=self.styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#2196F3"),
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        period_text = self._format_period(settlement)
        title = Paragraph(f"EXTRATO DE ACERTO<br/>{period_text}", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.5 * cm))

        # Informações do motorista
        driver_info = [
            ["<b>Motorista:</b>", settlement.driver.nome_completo],
            ["<b>Email:</b>", settlement.driver.email or "-"],
            ["<b>Telefone:</b>", settlement.driver.contact_phone or "-"],
        ]

        if settlement.partner:
            driver_info.append(["<b>Parceiro:</b>", settlement.partner.name])

        driver_table = Table(driver_info, colWidths=[4 * cm, 12 * cm])
        driver_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )

        elements.append(driver_table)
        elements.append(Spacer(1, 0.8 * cm))

        # Estatísticas de entregas
        stats_data = [
            ["ESTATÍSTICAS DE ENTREGAS", "", ""],
            ["Total de Pedidos:", str(settlement.total_orders), ""],
            ["Pedidos Entregues:", str(settlement.delivered_orders), ""],
            ["Pedidos Falhados:", str(settlement.failed_orders), ""],
            ["Taxa de Sucesso:", f"{settlement.success_rate}%", ""],
        ]

        stats_table = Table(stats_data, colWidths=[8 * cm, 4 * cm, 4 * cm])
        stats_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#2196F3"),
                    ),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ]
            )
        )

        elements.append(stats_table)
        elements.append(Spacer(1, 0.8 * cm))

        # Valores financeiros
        financial_data = [
            ["VALORES FINANCEIROS", "", ""],
            ["Valor Bruto:", f"€{settlement.gross_amount:,.2f}", "+"],
            [
                "Bônus por Performance:",
                f"€{settlement.bonus_amount:,.2f}",
                "+",
            ],
            [
                "Desconto Combustível:",
                f"€{settlement.fuel_deduction:,.2f}",
                "-",
            ],
            [
                "Descontos (Claims):",
                f"€{settlement.claims_deducted:,.2f}",
                "-",
            ],
            ["Outros Descontos:", f"€{settlement.other_deductions:,.2f}", "-"],
            [
                "<b>VALOR LÍQUIDO:</b>",
                f"<b>€{settlement.net_amount:,.2f}</b>",
                "",
            ],
        ]

        financial_table = Table(financial_data, colWidths=[8 * cm, 6 * cm, 2 * cm])
        financial_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#4CAF50"),
                    ),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -2), 10),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    (
                        "BACKGROUND",
                        (0, -1),
                        (-1, -1),
                        colors.HexColor("#E8F5E9"),
                    ),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, -1), (-1, -1), 12),
                ]
            )
        )

        elements.append(financial_table)
        elements.append(Spacer(1, 0.8 * cm))

        # Claims detalhados (se houver)
        claims = settlement.claims.all()
        if claims.exists():
            elements.append(
                Paragraph("<b>DESCONTOS APLICADOS:</b>", self.styles["Heading3"])
            )
            elements.append(Spacer(1, 0.3 * cm))

            claims_data = [["Tipo", "Descrição", "Valor"]]

            for claim in claims:
                claims_data.append(
                    [
                        claim.get_claim_type_display(),
                        (
                            claim.description[:50] + "..."
                            if len(claim.description) > 50
                            else claim.description
                        ),
                        f"€{claim.amount:,.2f}",
                    ]
                )

            claims_table = Table(claims_data, colWidths=[4 * cm, 8 * cm, 4 * cm])
            claims_table.setStyle(
                TableStyle(
                    [
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, 0),
                            colors.HexColor("#FF5722"),
                        ),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 9),
                        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                    ]
                )
            )

            elements.append(claims_table)
            elements.append(Spacer(1, 0.5 * cm))

        # Notas
        if settlement.notes:
            elements.append(Spacer(1, 0.5 * cm))
            elements.append(Paragraph("<b>Notas:</b>", self.styles["Heading4"]))
            elements.append(Paragraph(settlement.notes, self.styles["Normal"]))

        # Footer
        elements.append(Spacer(1, 1 * cm))
        footer_style = ParagraphStyle(
            "Footer",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
        )
        footer = Paragraph(
            f'Documento gerado automaticamente em {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/>'
            "Léguas Franzinas - Sistema de Gestão Logística",
            footer_style,
        )
        elements.append(footer)

        # Construir PDF
        doc.build(elements)

        # Retornar buffer
        self.buffer.seek(0)
        return self.buffer

    def generate_invoice_pdf(self, invoice):
        """
        Gera PDF de fatura para partner.

        Args:
            invoice: PartnerInvoice instance

        Returns:
            BytesIO com o PDF gerado
        """
        self.buffer = BytesIO()

        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []

        # Header
        elements.append(self._create_header())
        elements.append(Spacer(1, 0.5 * cm))

        # Título
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=self.styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#2196F3"),
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        title = Paragraph(f"FATURA<br/>{invoice.invoice_number}", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.5 * cm))

        # Informações
        info_data = [
            ["<b>Parceiro:</b>", invoice.partner.name],
            [
                "<b>Período:</b>",
                f'{invoice.period_start.strftime("%d/%m/%Y")} a {invoice.period_end.strftime("%d/%m/%Y")}',
            ],
            [
                "<b>Data de Emissão:</b>",
                invoice.issue_date.strftime("%d/%m/%Y"),
            ],
            [
                "<b>Data de Vencimento:</b>",
                invoice.due_date.strftime("%d/%m/%Y"),
            ],
            ["<b>Status:</b>", invoice.get_status_display()],
        ]

        info_table = Table(info_data, colWidths=[5 * cm, 11 * cm])
        info_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements.append(info_table)
        elements.append(Spacer(1, 1 * cm))

        # Valores
        values_data = [
            ["DISCRIMINAÇÃO", "VALOR"],
            ["Valor Bruto:", f"€{invoice.gross_amount:,.2f}"],
            ["IVA (23%):", f"€{invoice.tax_amount:,.2f}"],
            ["<b>TOTAL A PAGAR:</b>", f"<b>€{invoice.net_amount:,.2f}</b>"],
        ]

        values_table = Table(values_data, colWidths=[10 * cm, 6 * cm])
        values_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#2196F3"),
                    ),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    (
                        "BACKGROUND",
                        (0, -1),
                        (-1, -1),
                        colors.HexColor("#E3F2FD"),
                    ),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, -1), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        elements.append(values_table)
        elements.append(Spacer(1, 1 * cm))

        # Estatísticas
        stats = Paragraph(
            f"<b>Total de pedidos:</b> {invoice.total_orders}<br/>"
            f"<b>Pedidos entregues:</b> {invoice.total_delivered}",
            self.styles["Normal"],
        )
        elements.append(stats)

        # Footer
        elements.append(Spacer(1, 2 * cm))
        footer_style = ParagraphStyle(
            "Footer",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
        )
        footer = Paragraph(
            f'Documento gerado automaticamente em {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/>'
            "Léguas Franzinas - Sistema de Gestão Logística",
            footer_style,
        )
        elements.append(footer)

        doc.build(elements)

        self.buffer.seek(0)
        return self.buffer

    def _create_header(self):
        """Cria header padrão do PDF"""
        header_style = ParagraphStyle(
            "Header",
            parent=self.styles["Normal"],
            fontSize=14,
            textColor=colors.HexColor("#2196F3"),
            alignment=TA_LEFT,
            fontName="Helvetica-Bold",
        )

        return Paragraph("Léguas Franzinas", header_style)

    def _format_period(self, settlement):
        """Formata período do settlement"""
        if settlement.period_type == "WEEKLY":
            return f"Semana {settlement.week_number}/{settlement.year}"
        return f"{settlement.month_number:02d}/{settlement.year}"

    def generate_pre_invoice_pdf(self, pre_invoice):
        """
        Gera PDF de pré-fatura de motorista (DriverPreInvoice).
        Layout equivalente ao modelo Excel.
        """
        self.buffer = BytesIO()

        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []
        purple = colors.HexColor("#5B21B6")
        orange = colors.HexColor("#F97316")
        light_purple = colors.HexColor("#EDE9FE")
        light_gray = colors.HexColor("#F3F4F6")
        red = colors.HexColor("#DC2626")
        green = colors.HexColor("#16A34A")

        # ── Carregar dados da empresa do SystemConfiguration ───────────────
        import os as _os
        try:
            from system_config.models import SystemConfiguration, CompanyProfile
            sys_config = SystemConfiguration.get_config()
            empresa_nome = sys_config.company_name or "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            empresa_morada = sys_config.company_morada or ""
            empresa_localidade = sys_config.company_localidade or ""
            empresa_telefone = sys_config.company_telefone or ""
            empresa_email = sys_config.company_email or ""
            empresa_nif = sys_config.company_nif or ""

            # Tenta logo do SystemConfiguration primeiro, depois CompanyProfile como fallback
            empresa_logo_path = None
            if sys_config.logo:
                try:
                    _p = sys_config.logo.path
                    if _os.path.exists(_p):
                        empresa_logo_path = _p
                except Exception:
                    pass
            if not empresa_logo_path:
                try:
                    cp = CompanyProfile.objects.first()
                    if cp and cp.assets_logo:
                        _p = cp.assets_logo.path
                        if _os.path.exists(_p):
                            empresa_logo_path = _p
                except Exception:
                    pass
        except Exception:
            empresa_nome = pre_invoice.dsp_empresa or "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            empresa_morada = empresa_localidade = empresa_telefone = ""
            empresa_email = empresa_nif = ""
            empresa_logo_path = None

        # ── Estilos ────────────────────────────────────────────────────────
        sub_style = ParagraphStyle(
            "PISub", parent=self.styles["Normal"],
            fontSize=9, textColor=colors.grey,
        )
        label_col_style = ParagraphStyle(
            "PILabelCol", parent=self.styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#6B7280"),
        )
        value_col_style = ParagraphStyle(
            "PIValueCol", parent=self.styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#111827"),
        )
        title_style = ParagraphStyle(
            "PITitle", parent=self.styles["Heading1"],
            fontSize=15, textColor=colors.whitesmoke,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        )

        # ── Cabeçalho: logo centrada + dados empresa ──────────────────────
        from reportlab.platypus import Image as RLImage

        try:
            if empresa_logo_path:
                raw_logo = RLImage(empresa_logo_path, width=3 * cm, height=3 * cm,
                                   kind="proportional")
            else:
                raw_logo = Paragraph("", sub_style)
        except Exception:
            raw_logo = Paragraph("", sub_style)

        # Logo dentro de uma célula própria para garantir centralização
        logo_cell = Table(
            [[raw_logo]],
            colWidths=[3.5 * cm],
        )
        logo_cell.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        # Coluna direita: dados empresa formatados como tabela de 2 colunas
        empresa_rows = []
        for label, val in [
            ("Empresa", empresa_nome),
            ("Morada", empresa_morada),
            ("Localidade", empresa_localidade),
            ("Telefone", empresa_telefone),
            ("Email", empresa_email),
            ("NIF", empresa_nif),
        ]:
            if val:
                empresa_rows.append([
                    Paragraph(label, label_col_style),
                    Paragraph(val, value_col_style),
                ])

        empresa_inner = Table(empresa_rows, colWidths=[2.5 * cm, 9.5 * cm])
        empresa_inner.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
        ]))

        header_outer = Table(
            [[logo_cell, empresa_inner]],
            colWidths=[4 * cm, 13 * cm],
        )
        header_outer.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("RIGHTPADDING", (1, 0), (1, -1), 0),
            ("LINEAFTER", (0, 0), (0, -1), 0.5, colors.HexColor("#E5E7EB")),
        ]))
        elements.append(header_outer)
        elements.append(Spacer(1, 0.5 * cm))

        # ── Título da pré-fatura ───────────────────────────────────────────
        title_table = Table(
            [[Paragraph("PRÉ-FATURA DE MOTORISTA", title_style)]],
            colWidths=[17 * cm],
        )
        title_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), purple),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 0.5 * cm))

        # ── Dados da pré-fatura ────────────────────────────────────────────
        label_style = ParagraphStyle(
            "PILabel", parent=self.styles["Normal"],
            fontSize=8, textColor=colors.grey,
        )
        value_style = ParagraphStyle(
            "PIValue", parent=self.styles["Normal"],
            fontSize=10, fontName="Helvetica-Bold",
        )

        def lv(label, value):
            return [Paragraph(label, label_style), Paragraph(str(value or "—"), value_style)]

        linhas = list(pre_invoice.linhas.all())
        parceiros_nomes = ", ".join(
            l.parceiro.name for l in linhas if l.parceiro
        ) or "—"
        dados = Table([
            lv("Nº Pré-Fatura", pre_invoice.numero) +
            lv("Data Emissão", datetime.now().strftime("%d/%m/%Y")),
            lv("Motorista", pre_invoice.driver.nome_completo) +
            lv("Parceiro(s) / Operação", parceiros_nomes),
            lv("Período Início", pre_invoice.periodo_inicio.strftime("%d/%m/%Y")) +
            lv("Período Fim", pre_invoice.periodo_fim.strftime("%d/%m/%Y")),
            lv("DSP / Empresa", empresa_nome) +
            lv("Status", pre_invoice.get_status_display()),
        ], colWidths=[3 * cm, 5.5 * cm, 3 * cm, 5.5 * cm])

        dados.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), light_gray),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, light_gray]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(dados)
        elements.append(Spacer(1, 0.6 * cm))

        # ── Cálculo Operacional ────────────────────────────────────────────
        section_style = ParagraphStyle(
            "PISection", parent=self.styles["Normal"],
            fontSize=10, textColor=colors.whitesmoke,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        )
        row_label = ParagraphStyle(
            "PIRowLabel", parent=self.styles["Normal"], fontSize=9,
        )
        row_val = ParagraphStyle(
            "PIRowVal", parent=self.styles["Normal"],
            fontSize=9, alignment=TA_CENTER,
        )
        row_small = ParagraphStyle(
            "PIRowSmall", parent=self.styles["Normal"],
            fontSize=7, alignment=TA_CENTER,
            textColor=colors.HexColor("#6B7280"),
        )

        def section_header(text, color=purple):
            t = Table([[Paragraph(text, section_style)]], colWidths=[17 * cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            return t

        elements.append(section_header("CÁLCULO OPERACIONAL"))
        elements.append(Spacer(1, 0.1 * cm))

        op_header = Table(
            [[
                Paragraph("Descrição", section_style),
                Paragraph("Qtd.", section_style),
                Paragraph("Valor Unit.", section_style),
                Paragraph("Total (€)", section_style),
            ]],
            colWidths=[7 * cm, 3 * cm, 3.5 * cm, 3.5 * cm],
        )
        op_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#7C3AED")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(op_header)

        # Helper para extrair o login da linha (observacoes ou courier_id)
        import re as _re

        def _login_label(obj):
            """Extrai o nome do login (courier_name) das observações ou
            cai no courier_id. Retorna '' se nada disponível."""
            obs = getattr(obj, "observacoes", "") or ""
            m = _re.search(
                r"Login(?:\s*Cainiao)?\s*:\s*([^\n·()]+)", obs,
            )
            if m:
                return m.group(1).strip()
            cid = getattr(obj, "courier_id", "") or ""
            return cid

        # Mostrar logins para identificar — útil quando há >1 login no driver
        n_distinct_logins = len({
            _login_label(l) for l in linhas if l.parceiro
        })

        op_rows = []
        for l in linhas:
            parceiro_label = l.parceiro.name if l.parceiro else "Sem parceiro"
            login = _login_label(l)
            if login and n_distinct_logins > 1:
                desc = (
                    f'<b>{parceiro_label}</b>'
                    f'<br/><font size="8" color="#6b21a8">'
                    f'↳ Login: {login}</font>'
                )
            elif login:
                desc = (
                    f'<b>{parceiro_label}</b>'
                    f'<br/><font size="8" color="#6b7280">'
                    f'Login: {login}</font>'
                )
            else:
                desc = parceiro_label
            # DSR como linha pequena abaixo da quantidade
            qtd_cell = Paragraph(str(l.total_pacotes), row_val)
            if l.dsr_percentual:
                from reportlab.platypus import KeepTogether
                dsr_p = Paragraph(
                    f"DSR {float(l.dsr_percentual):.1f}%", row_small
                )
                qtd_cell = Table(
                    [[qtd_cell], [dsr_p]],
                    colWidths=[3 * cm],
                )
                qtd_cell.setStyle(TableStyle([
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]))
            op_rows.append([
                Paragraph(desc, row_label),
                qtd_cell,
                Paragraph(f"€{float(l.taxa_por_entrega):.2f}", row_val),
                Paragraph(f"€{float(l.base_entregas):.2f}", row_val),
            ])
        if pre_invoice.ajuste_manual:
            op_rows.append([
                Paragraph("Ajuste Manual", row_label),
                Paragraph("—", row_val),
                Paragraph(f"€{float(pre_invoice.ajuste_manual):.2f}", row_val),
                Paragraph(f"€{float(pre_invoice.ajuste_manual):.2f}", row_val),
            ])
        if pre_invoice.penalizacoes_gerais:
            op_rows.append([
                Paragraph("Penalizações Gerais", row_label),
                Paragraph("—", row_val),
                Paragraph(f"-€{float(pre_invoice.penalizacoes_gerais):.2f}", row_val),
                Paragraph(f"-€{float(pre_invoice.penalizacoes_gerais):.2f}", row_val),
            ])
        if not op_rows:
            op_rows = [[
                Paragraph("Sem linhas de trabalho", row_label),
                Paragraph("—", row_val),
                Paragraph("—", row_val),
                Paragraph("€0.00", row_val),
            ]]
        op_table = Table(
            op_rows,
            colWidths=[8 * cm, 3 * cm, 3 * cm, 3 * cm],
        )
        op_table.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, light_gray]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(op_table)
        elements.append(Spacer(1, 0.3 * cm))

        # ── Detalhe de Helpers Cainiao (apenas se existirem) ──────────────
        cainiao_linhas = [l for l in linhas if getattr(l, "api_source", "") == "cainiao"]
        if cainiao_linhas:
            from django.db.models import Count as _DbCount
            from settlements.models import CainiaoDelivery

            helpers_qs = (
                CainiaoDelivery.objects
                .filter(
                    driver=pre_invoice.driver,
                    delivery_time__date__gte=pre_invoice.periodo_inicio,
                    delivery_time__date__lte=pre_invoice.periodo_fim,
                )
                .values("helper_name")
                .annotate(count=_DbCount("id"))
                .order_by("-count")
            )
            helpers_list = list(helpers_qs)
            if helpers_list:
                total_helper_pcts = sum(h["count"] for h in helpers_list)
                helper_section_color = colors.HexColor("#1E40AF")
                helper_header_color  = colors.HexColor("#2563EB")
                helper_sub_color     = colors.HexColor("#DBEAFE")

                helper_title = Table(
                    [[Paragraph("DETALHE DE ASSISTENTES (HELPERS) — CAINIAO", section_style)]],
                    colWidths=[17 * cm],
                )
                helper_title.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), helper_section_color),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                elements.append(helper_title)
                elements.append(Spacer(1, 0.1 * cm))

                col_style = ParagraphStyle(
                    "HColStyle", parent=self.styles["Normal"],
                    fontSize=8, textColor=colors.whitesmoke,
                    fontName="Helvetica-Bold", alignment=TA_CENTER,
                )
                h_header = Table(
                    [[
                        Paragraph("Helper / Assistente", col_style),
                        Paragraph("Entregas", col_style),
                        Paragraph("% do Total", col_style),
                    ]],
                    colWidths=[10 * cm, 3.5 * cm, 3.5 * cm],
                )
                h_header.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), helper_header_color),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                elements.append(h_header)

                h_row_label = ParagraphStyle(
                    "HRowLabel", parent=self.styles["Normal"], fontSize=9,
                )
                h_row_val = ParagraphStyle(
                    "HRowVal", parent=self.styles["Normal"],
                    fontSize=9, alignment=TA_CENTER,
                )
                h_rows = []
                for h in helpers_list:
                    name = h["helper_name"] or "Principal (motorista)"
                    pct  = (h["count"] / total_helper_pcts * 100) if total_helper_pcts else 0
                    is_main = not h["helper_name"]
                    label_p = ParagraphStyle(
                        "HMain" if is_main else "HHelper",
                        parent=self.styles["Normal"],
                        fontSize=9,
                        fontName="Helvetica-Bold" if is_main else "Helvetica",
                    )
                    h_rows.append([
                        Paragraph(name, label_p),
                        Paragraph(str(h["count"]), h_row_val),
                        Paragraph(f"{pct:.1f}%", h_row_val),
                    ])
                # Linha de total
                h_rows.append([
                    Paragraph("TOTAL", ParagraphStyle("HTot", parent=self.styles["Normal"],
                                                       fontSize=9, fontName="Helvetica-Bold")),
                    Paragraph(str(total_helper_pcts), h_row_val),
                    Paragraph("100%", h_row_val),
                ])

                h_table = Table(h_rows, colWidths=[10 * cm, 3.5 * cm, 3.5 * cm])
                h_table.setStyle(TableStyle([
                    ("ROWBACKGROUNDS", (0, 0), (-1, -2), [colors.white, helper_sub_color]),
                    ("BACKGROUND", (0, -1), (-1, -1), helper_sub_color),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]))
                elements.append(h_table)
                elements.append(Spacer(1, 0.5 * cm))

        # ── Bonificações (apenas se existirem) ────────────────────────────
        bonificacoes = list(pre_invoice.bonificacoes.all())
        if bonificacoes:
            elements.append(section_header("BONIFICAÇÕES DOMINGO / FERIADO", orange))
            elements.append(Spacer(1, 0.1 * cm))

            # Detectar se há mais que um login nas bonificações
            distinct_bonus_logins = {_login_label(b) for b in bonificacoes}
            distinct_bonus_logins.discard("")
            show_login_col = len(distinct_bonus_logins) > 1

            if show_login_col:
                col_widths = [3 * cm, 3.5 * cm, 4 * cm, 3 * cm, 3.5 * cm]
                bon_header = Table(
                    [[
                        Paragraph("Data", section_style),
                        Paragraph("Tipo", section_style),
                        Paragraph("Login", section_style),
                        Paragraph("Qtd. Eleg.", section_style),
                        Paragraph("Bônus (€)", section_style),
                    ]],
                    colWidths=col_widths,
                )
            else:
                col_widths = [3.5 * cm, 5 * cm, 4.5 * cm, 4 * cm]
                bon_header = Table(
                    [[
                        Paragraph("Data", section_style),
                        Paragraph("Tipo", section_style),
                        Paragraph("Qtd. Elegíveis", section_style),
                        Paragraph("Bônus (€)", section_style),
                    ]],
                    colWidths=col_widths,
                )
            bon_header.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EA580C")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            elements.append(bon_header)

            bon_rows = []
            for b in bonificacoes:
                if show_login_col:
                    bon_rows.append([
                        b.data.strftime("%d/%m/%Y"),
                        b.get_tipo_display(),
                        _login_label(b) or "—",
                        str(b.qtd_entregas_elegiveis),
                        f"€{float(b.bonus_calculado):.2f}",
                    ])
                else:
                    bon_rows.append([
                        b.data.strftime("%d/%m/%Y"),
                        b.get_tipo_display(),
                        str(b.qtd_entregas_elegiveis),
                        f"€{float(b.bonus_calculado):.2f}",
                    ])
            if show_login_col:
                bon_rows.append([
                    "", "", "", "Total",
                    f"€{float(pre_invoice.total_bonus):.2f}",
                ])
            else:
                bon_rows.append([
                    "", "", "Total",
                    f"€{float(pre_invoice.total_bonus):.2f}",
                ])
            bon_table = Table(bon_rows, colWidths=col_widths)
            bon_table.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-2, -1), [colors.white, light_gray]),
                ("BACKGROUND", (0, -1), (-1, -1), light_purple),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("ALIGN", (-2, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(bon_table)
            elements.append(Spacer(1, 0.5 * cm))

        # ── Pacotes Perdidos (apenas se existirem) ────────────────────────
        perdidos = list(pre_invoice.pacotes_perdidos.all())
        if perdidos:
            elements.append(section_header("PACOTES PERDIDOS", colors.HexColor("#B91C1C")))
            elements.append(Spacer(1, 0.1 * cm))

            pp_header = Table(
                [[
                    Paragraph("Data", section_style),
                    Paragraph("Nº Pacote", section_style),
                    Paragraph("Descrição", section_style),
                    Paragraph("Valor Base", section_style),
                    Paragraph("IVA", section_style),
                    Paragraph("Total (€)", section_style),
                ]],
                colWidths=[3 * cm, 3.5 * cm, 4 * cm, 2.5 * cm, 2.5 * cm, 3.5 * cm],
            )
            pp_header.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#DC2626")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            elements.append(pp_header)

            pp_rows = []
            for p in perdidos:
                iva_pct = float(p.iva_percentual)
                valor_base = float(p.valor)
                valor_iva = float(p.valor_iva)
                valor_total = float(p.valor_com_iva)
                iva_str = f"{iva_pct:.0f}% (€{valor_iva:.2f})" if iva_pct > 0 else "—"
                pp_rows.append([
                    p.data.strftime("%d/%m/%Y") if p.data else "—",
                    p.numero_pacote or "—",
                    p.descricao or "—",
                    f"€{valor_base:.2f}",
                    iva_str,
                    f"-€{valor_total:.2f}",
                ])
            pp_rows.append(["", "", "", "", "Total",
                             f"-€{float(pre_invoice.total_pacotes_perdidos):.2f}"])
            pp_table = Table(pp_rows,
                             colWidths=[3 * cm, 3.5 * cm, 4 * cm, 2.5 * cm, 2.5 * cm, 3.5 * cm])
            pp_table.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-2, -1), [colors.white, light_gray]),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEE2E2")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), red),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("ALIGN", (3, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(pp_table)
            elements.append(Spacer(1, 0.5 * cm))

        # ── Adiantamentos (apenas se existirem, com quebra de página) ─────
        adiantamentos = list(pre_invoice.adiantamentos.all())
        if adiantamentos:
            elements.append(PageBreak())
            elements.append(section_header("ADIANTAMENTOS / COMBUSTÍVEL / ABASTECIMENTOS",
                                           colors.HexColor("#B45309")))
            elements.append(Spacer(1, 0.1 * cm))

            adv_header = Table(
                [[
                    Paragraph("Data", section_style),
                    Paragraph("Tipo", section_style),
                    Paragraph("Descrição", section_style),
                    Paragraph("Valor (€)", section_style),
                ]],
                colWidths=[3.5 * cm, 4 * cm, 5.5 * cm, 4 * cm],
            )
            adv_header.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#D97706")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            elements.append(adv_header)

            adv_rows = [
                [a.data.strftime("%d/%m/%Y") if a.data else "—",
                 a.get_tipo_display(), a.descricao or "—",
                 f"-€{float(a.valor):.2f}"]
                for a in adiantamentos
            ]
            adv_rows.append(["", "", "Total",
                              f"-€{float(pre_invoice.total_adiantamentos):.2f}"])
            adv_table = Table(adv_rows, colWidths=[3.5 * cm, 4 * cm, 5.5 * cm, 4 * cm])
            adv_table.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-2, -1), [colors.white, light_gray]),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEF3C7")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#92400E")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("ALIGN", (3, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(adv_table)
            elements.append(Spacer(1, 0.7 * cm))

        # ── Comissões de Indicação ─────────────────────────────────────────
        from decimal import Decimal
        from drivers_app.models import DriverReferral
        from settlements.models import DriverPreInvoice as DPI

        comissoes_detail = []
        total_comissoes = Decimal("0.00")
        for ref in pre_invoice.driver.referrals_given.filter(ativo=True):
            referred_pfs = DPI.objects.filter(
                driver=ref.referred,
                periodo_inicio=pre_invoice.periodo_inicio,
                periodo_fim=pre_invoice.periodo_fim,
            )
            for rpf in referred_pfs:
                total_pcts = sum(l.total_pacotes for l in rpf.linhas.all())
                valor = Decimal(total_pcts) * ref.comissao_por_pacote
                total_comissoes += valor
                comissoes_detail.append({
                    "nome": ref.referred.nome_completo,
                    "pacotes": total_pcts,
                    "comissao": ref.comissao_por_pacote,
                    "valor": valor,
                })

        if comissoes_detail:
            teal_color = colors.HexColor("#0D9488")
            teal_light = colors.HexColor("#F0FDFA")
            elements.append(section_header("COMISSÕES DE INDICAÇÃO", teal_color))
            elements.append(Spacer(1, 0.1 * cm))

            com_header = Table(
                [[
                    Paragraph("Motorista Indicado", section_style),
                    Paragraph("Pacotes", section_style),
                    Paragraph("€/pacote", section_style),
                    Paragraph("Comissão (€)", section_style),
                ]],
                colWidths=[7 * cm, 3 * cm, 3 * cm, 4 * cm],
            )
            com_header.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), teal_color),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            elements.append(com_header)

            com_rows = [
                [
                    Paragraph(c["nome"], row_val),
                    Paragraph(str(c["pacotes"]), row_val),
                    Paragraph(f"€{float(c['comissao']):.4f}", row_val),
                    Paragraph(f"+€{float(c['valor']):.2f}", row_val),
                ]
                for c in comissoes_detail
            ]
            com_rows.append([
                Paragraph("", row_val),
                Paragraph("", row_val),
                Paragraph("Total Comissões", ParagraphStyle(
                    "ComTotal", parent=self.styles["Normal"],
                    fontSize=8, fontName="Helvetica-Bold",
                    textColor=teal_color,
                )),
                Paragraph(f"+€{float(total_comissoes):.2f}", ParagraphStyle(
                    "ComTotalVal", parent=self.styles["Normal"],
                    fontSize=9, fontName="Helvetica-Bold",
                    textColor=teal_color,
                )),
            ])
            com_table = Table(com_rows, colWidths=[7 * cm, 3 * cm, 3 * cm, 4 * cm])
            com_table.setStyle(TableStyle([
                ("ROWBACKGROUNDS", (0, 0), (-1, -2), [colors.white, teal_light]),
                ("BACKGROUND", (0, -1), (-1, -1), teal_light),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#99F6E4")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(com_table)
            elements.append(Spacer(1, 0.7 * cm))

        # ── Resumo Financeiro ──────────────────────────────────────────────
        elements.append(section_header("RESUMO FINANCEIRO"))
        elements.append(Spacer(1, 0.1 * cm))

        resumo_rows = [
            ["Base Entregas", f"€{float(pre_invoice.base_entregas):.2f}",
             "Pacotes entregues × taxa"],
            ["Bonificações Dom/Feriado", f"€{float(pre_invoice.total_bonus):.2f}",
             "Soma das bonificações"],
            ["Ajustes Positivos", f"€{float(pre_invoice.ajuste_manual):.2f}",
             "Correções positivas"],
            ["Subtotal Bruto", f"€{float(pre_invoice.subtotal_bruto):.2f}", ""],
            ["Penalizações Gerais", f"-€{float(pre_invoice.penalizacoes_gerais):.2f}",
             "Descontos gerais"],
            ["Pacotes Perdidos", f"-€{float(pre_invoice.total_pacotes_perdidos):.2f}",
             "Valor base + IVA incluído"],
            ["Adiantamentos / Combustível", f"-€{float(pre_invoice.total_adiantamentos):.2f}",
             "Deduzido automaticamente"],
        ]
        # Adicionar linha de comissões apenas se existirem
        if total_comissoes > 0:
            resumo_rows.append(
                ["Comissões de Indicação", f"+€{float(total_comissoes):.2f}",
                 "Bónus por motoristas indicados"]
            )

        subtotal_idx = 3  # índice da linha "Subtotal Bruto"
        comissoes_idx = len(resumo_rows) - 1 if total_comissoes > 0 else None

        res_table = Table(resumo_rows, colWidths=[7 * cm, 4 * cm, 6 * cm])
        ts = [
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, light_gray]),
            ("FONTNAME", (0, subtotal_idx), (-1, subtotal_idx), "Helvetica-Bold"),
            ("BACKGROUND", (0, subtotal_idx), (-1, subtotal_idx), light_purple),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TEXTCOLOR", (1, 4), (1, 6), red),
        ]
        if comissoes_idx is not None:
            ts.append(("TEXTCOLOR", (1, comissoes_idx), (1, comissoes_idx),
                        colors.HexColor("#0D9488")))
            ts.append(("FONTNAME", (0, comissoes_idx), (-1, comissoes_idx),
                        "Helvetica-Bold"))
        res_table.setStyle(TableStyle(ts))
        elements.append(res_table)
        elements.append(Spacer(1, 0.2 * cm))

        # Total a receber — destaque
        total_table = Table(
            [[
                Paragraph("TOTAL A RECEBER", ParagraphStyle(
                    "TotalLabel", parent=self.styles["Normal"],
                    fontSize=13, textColor=colors.whitesmoke,
                    fontName="Helvetica-Bold",
                )),
                Paragraph(f"€{float(pre_invoice.total_a_receber):.2f}", ParagraphStyle(
                    "TotalVal", parent=self.styles["Normal"],
                    fontSize=16, textColor=colors.whitesmoke,
                    fontName="Helvetica-Bold", alignment=TA_CENTER,
                )),
            ]],
            colWidths=[11 * cm, 6 * cm],
        )
        total_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), green),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (0, -1), 10),
        ]))
        elements.append(total_table)

        # ── Rodapé ────────────────────────────────────────────────────────
        elements.append(Spacer(1, 1.5 * cm))
        footer_style = ParagraphStyle(
            "PIFooter", parent=self.styles["Normal"],
            fontSize=7, textColor=colors.grey, alignment=TA_CENTER,
        )
        elements.append(Paragraph(
            f"Documento gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
            "Léguas Franzinas - Sistema de Gestão Logística",
            footer_style,
        ))

        doc.build(elements)
        self.buffer.seek(0)
        return self.buffer

    def generate_fleet_invoice_pdf(self, fleet_invoice):
        """Gera PDF da Pré-fatura da Frota (FleetInvoice FF-NNNN).

        Layout:
          1. Cabeçalho — logo Léguas + dados fiscais
          2. Título "PRÉ-FATURA FROTA FF-NNNN"
          3. Dados da factura (frota, NIF, período, status, total)
          4. Sumário (entregas, base, bónus, claims, total)
          5. Tabela detalhe por motorista
          6. Detalhe de bónus/claims agrupado (sem PageBreak entre drivers)
        """
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            KeepTogether, Image as RLImage,
        )
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib import colors as rlcolors
        import os as _os

        fi = fleet_invoice
        self.buffer = BytesIO()
        doc = SimpleDocTemplate(
            self.buffer, pagesize=A4,
            rightMargin=1.5 * cm, leftMargin=1.5 * cm,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )

        elements = []
        purple = rlcolors.HexColor("#5B21B6")
        light_purple = rlcolors.HexColor("#EDE9FE")
        light_gray = rlcolors.HexColor("#F3F4F6")

        # ── Carregar dados Léguas ────────────────────────────────────
        try:
            from system_config.models import (
                SystemConfiguration, CompanyProfile,
            )
            sys_config = SystemConfiguration.get_config()
            empresa_nome = (
                sys_config.company_name
                or "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            )
            empresa_morada = sys_config.company_morada or ""
            empresa_localidade = sys_config.company_localidade or ""
            empresa_telefone = sys_config.company_telefone or ""
            empresa_email = sys_config.company_email or ""
            empresa_nif = sys_config.company_nif or ""

            empresa_logo_path = None
            if sys_config.logo:
                try:
                    _p = sys_config.logo.path
                    if _os.path.exists(_p):
                        empresa_logo_path = _p
                except Exception:
                    pass
            if not empresa_logo_path:
                try:
                    cp = CompanyProfile.objects.first()
                    if cp and cp.assets_logo:
                        _p = cp.assets_logo.path
                        if _os.path.exists(_p):
                            empresa_logo_path = _p
                except Exception:
                    pass
        except Exception:
            empresa_nome = "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            empresa_morada = empresa_localidade = empresa_telefone = ""
            empresa_email = empresa_nif = ""
            empresa_logo_path = None

        # ── Estilos ──────────────────────────────────────────────────
        label_col_style = ParagraphStyle(
            "FILabelCol", parent=self.styles["Normal"],
            fontSize=8, textColor=rlcolors.HexColor("#6B7280"),
        )
        value_col_style = ParagraphStyle(
            "FIValueCol", parent=self.styles["Normal"],
            fontSize=8.5, textColor=rlcolors.HexColor("#111827"),
        )
        title_style = ParagraphStyle(
            "FITitle", parent=self.styles["Heading1"],
            fontSize=14, textColor=rlcolors.whitesmoke,
            fontName="Helvetica-Bold", alignment=TA_CENTER,
        )
        section_style = ParagraphStyle(
            "FISection", parent=self.styles["Normal"],
            fontSize=10, textColor=purple,
            fontName="Helvetica-Bold",
        )
        sub_style = ParagraphStyle(
            "FISub", parent=self.styles["Normal"],
            fontSize=9, textColor=rlcolors.grey,
        )

        # ── Cabeçalho: logo + dados Léguas ───────────────────────────
        try:
            if empresa_logo_path:
                raw_logo = RLImage(
                    empresa_logo_path, width=2.8 * cm, height=2.8 * cm,
                    kind="proportional",
                )
            else:
                raw_logo = Paragraph("", sub_style)
        except Exception:
            raw_logo = Paragraph("", sub_style)

        logo_cell = Table([[raw_logo]], colWidths=[3.2 * cm])
        logo_cell.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        empresa_rows = []
        for label, val in [
            ("Empresa", empresa_nome),
            ("NIF", empresa_nif),
            ("Morada", empresa_morada),
            ("Localidade", empresa_localidade),
            ("Telefone", empresa_telefone),
            ("Email", empresa_email),
        ]:
            if val:
                empresa_rows.append([
                    Paragraph(label, label_col_style),
                    Paragraph(val, value_col_style),
                ])

        empresa_inner = Table(
            empresa_rows, colWidths=[2.2 * cm, 12 * cm],
        )
        empresa_inner.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3,
             rlcolors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, 0), (-1, 0),
             rlcolors.HexColor("#F9FAFB")),
        ]))

        header_outer = Table(
            [[logo_cell, empresa_inner]],
            colWidths=[3.5 * cm, 14.5 * cm],
        )
        header_outer.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("RIGHTPADDING", (1, 0), (1, -1), 0),
            ("LINEAFTER", (0, 0), (0, -1), 0.5,
             rlcolors.HexColor("#E5E7EB")),
        ]))
        elements.append(header_outer)
        elements.append(Spacer(1, 0.3 * cm))

        # ── Título ────────────────────────────────────────────────────
        title_table = Table(
            [[Paragraph(
                f"PRÉ-FATURA FROTA · {fi.numero}", title_style,
            )]],
            colWidths=[18 * cm],
        )
        title_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), purple),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 0.3 * cm))

        # ── Dados da factura (cliente = empresa parceira) ────────────
        small_label = ParagraphStyle(
            "FISmallLbl", parent=self.styles["Normal"],
            fontSize=7.5, textColor=rlcolors.grey,
        )
        small_val = ParagraphStyle(
            "FISmallVal", parent=self.styles["Normal"],
            fontSize=9, fontName="Helvetica-Bold",
        )

        def lv(label, value):
            return [
                Paragraph(label, small_label),
                Paragraph(str(value or "—"), small_val),
            ]

        cliente_nif = getattr(fi.empresa, "nif", "") or ""
        cliente_morada = getattr(fi.empresa, "morada", "") or ""
        cliente_loc = (
            f"{getattr(fi.empresa, 'codigo_postal', '') or ''} "
            f"{getattr(fi.empresa, 'cidade', '') or ''}"
        ).strip()

        dados = Table([
            lv("Frota / Cliente", fi.empresa.nome) +
            lv("NIF", cliente_nif),
            lv("Morada", cliente_morada) +
            lv("Localidade", cliente_loc),
            lv(
                "Período Início",
                fi.periodo_inicio.strftime("%d/%m/%Y"),
            ) +
            lv("Período Fim", fi.periodo_fim.strftime("%d/%m/%Y")),
            lv("Nº Factura", fi.numero) +
            lv("Status", fi.get_status_display()),
        ], colWidths=[3 * cm, 6 * cm, 3 * cm, 6 * cm])
        dados.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), light_gray),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [rlcolors.white, light_gray]),
            ("GRID", (0, 0), (-1, -1), 0.4,
             rlcolors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(dados)
        elements.append(Spacer(1, 0.4 * cm))

        # ── Sumário totais ───────────────────────────────────────────
        elements.append(Paragraph("Sumário", section_style))
        elements.append(Spacer(1, 0.15 * cm))
        summary = [
            ["Total entregas", str(fi.total_deliveries)],
            ["Base", f"€ {fi.total_base}"],
            ["Bónus", f"€ {fi.total_bonus}"],
            ["Claims", f"-€ {fi.total_claims}"],
            ["TOTAL A RECEBER", f"€ {fi.total_a_receber}"],
        ]
        t = Table(summary, colWidths=[7 * cm, 5 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, -1), (-1, -1), light_purple),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 10),
            ("BOX", (0, 0), (-1, -1), 0.4, rlcolors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.2,
             rlcolors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.4 * cm))

        # ── Detalhe por motorista ────────────────────────────────────
        elements.append(Paragraph(
            "Detalhe por Motorista", section_style,
        ))
        elements.append(Spacer(1, 0.15 * cm))

        header = [
            "Motorista", "Entregas", "€/pacote",
            "Base", "Bónus", "Claims", "Subtotal",
        ]
        rows = [header]
        for line in fi.lines.all().order_by("-deliveries"):
            rows.append([
                line.driver_name_snapshot or "?",
                str(line.deliveries),
                f"€{line.price_per_package}",
                f"€{line.base_amount}",
                f"€{line.bonus_amount}",
                (
                    f"-€{line.claims_amount}"
                    if line.claims_amount else "—"
                ),
                f"€{line.subtotal}",
            ])
        t2 = Table(rows, colWidths=[
            5 * cm, 1.6 * cm, 1.8 * cm, 2 * cm,
            2 * cm, 2 * cm, 2.5 * cm,
        ])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), purple),
            ("TEXTCOLOR", (0, 0), (-1, 0), rlcolors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("BOX", (0, 0), (-1, -1), 0.4, rlcolors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.2,
             rlcolors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [rlcolors.white, rlcolors.HexColor("#f5f3ff")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t2)

        # ── Detalhe bónus + claims (compactado, sem PageBreak) ───────
        drivers_with_detail = [
            ln for ln in fi.lines.all().order_by("-deliveries")
            if ln.bonus_days_detail.exists()
            or ln.claims_detail.exists()
        ]
        if drivers_with_detail:
            elements.append(Spacer(1, 0.5 * cm))
            elements.append(Paragraph(
                "Detalhes (Bónus &amp; Claims)", section_style,
            ))
            elements.append(Spacer(1, 0.2 * cm))

            for line in drivers_with_detail:
                bds = list(line.bonus_days_detail.all())
                cls = list(line.claims_detail.all())
                driver_block = []
                driver_block.append(Paragraph(
                    f"<b>{line.driver_name_snapshot}</b> "
                    f"<font color='#6B7280' size='8'>"
                    f"({line.deliveries} entregas)</font>",
                    sub_style,
                ))
                driver_block.append(Spacer(1, 0.1 * cm))

                # Bónus dias compacto
                if bds:
                    r = [["Data", "Tipo", "Nome", "Entregas", "Bónus"]]
                    for bd in bds:
                        r.append([
                            bd.data.strftime("%d/%m/%Y"),
                            bd.tipo,
                            (bd.feriado_nome or "-")[:30],
                            str(bd.deliveries),
                            f"€{bd.bonus}",
                        ])
                    tb = Table(r, colWidths=[
                        2.2 * cm, 1.6 * cm, 5 * cm,
                        1.8 * cm, 2 * cm,
                    ])
                    tb.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0),
                         rlcolors.HexColor("#fef3c7")),
                        ("FONTNAME", (0, 0), (-1, 0),
                         "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("BOX", (0, 0), (-1, -1), 0.4,
                         rlcolors.grey),
                        ("INNERGRID", (0, 0), (-1, -1), 0.2,
                         rlcolors.lightgrey),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]))
                    driver_block.append(tb)

                # Claims compacto
                if cls:
                    if bds:
                        driver_block.append(Spacer(1, 0.1 * cm))
                    r = [["Waybill", "Descrição", "Valor"]]
                    for cd in cls:
                        r.append([
                            cd.waybill_number or "—",
                            (cd.descricao or "")[:55],
                            f"-€{cd.valor}",
                        ])
                    tc = Table(r, colWidths=[
                        4.5 * cm, 6 * cm, 2.5 * cm,
                    ])
                    tc.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0),
                         rlcolors.HexColor("#fee2e2")),
                        ("FONTNAME", (0, 0), (-1, 0),
                         "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("BOX", (0, 0), (-1, -1), 0.4,
                         rlcolors.grey),
                        ("INNERGRID", (0, 0), (-1, -1), 0.2,
                         rlcolors.lightgrey),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]))
                    driver_block.append(tc)

                driver_block.append(Spacer(1, 0.3 * cm))
                elements.append(KeepTogether(driver_block))

        # ── Footer ──────────────────────────────────────────────────
        elements.append(Spacer(1, 0.5 * cm))
        footer_style = ParagraphStyle(
            "FIFooter", parent=self.styles["Normal"],
            fontSize=7, textColor=rlcolors.grey, alignment=TA_CENTER,
        )
        elements.append(Paragraph(
            f"{empresa_nome} · NIF {empresa_nif} · "
            f"Documento gerado em "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')}",
            footer_style,
        ))

        doc.build(elements)
        self.buffer.seek(0)
        return self.buffer

    def generate_empresa_parceira_pdf(self, empresa, mes, ano, pre_invoices, lancamentos, totais):
        """
        Gera PDF de pré-fatura unificada para uma Empresa Parceira.
        Inclui pré-faturas dos motoristas e lançamentos manuais, com IVA.
        """
        from decimal import Decimal as D
        import calendar

        self.buffer = BytesIO()
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []
        purple      = colors.HexColor("#5B21B6")
        indigo      = colors.HexColor("#4338CA")
        emerald     = colors.HexColor("#059669")
        orange      = colors.HexColor("#F97316")
        red_c       = colors.HexColor("#DC2626")
        light_gray  = colors.HexColor("#F3F4F6")
        light_indigo= colors.HexColor("#EEF2FF")
        white       = colors.whitesmoke
        dark_text   = colors.HexColor("#111827")
        gray_text   = colors.HexColor("#6B7280")

        # ── Estilos ────────────────────────────────────────────────────────
        normal = self.styles["Normal"]
        sub_style = ParagraphStyle("EPSub", parent=normal, fontSize=8, textColor=gray_text)
        label_style = ParagraphStyle("EPLabel", parent=normal, fontSize=9, textColor=gray_text)
        value_style = ParagraphStyle("EPValue", parent=normal, fontSize=9, textColor=dark_text)
        bold_style  = ParagraphStyle("EPBold", parent=normal, fontSize=9,
                                     textColor=dark_text, fontName="Helvetica-Bold")
        title_style = ParagraphStyle("EPTitle", parent=normal, fontSize=14,
                                     textColor=white, fontName="Helvetica-Bold",
                                     alignment=TA_CENTER)
        th_style    = ParagraphStyle("EPTH", parent=normal, fontSize=8,
                                     textColor=white, fontName="Helvetica-Bold",
                                     alignment=TA_CENTER)
        td_style    = ParagraphStyle("EPTD", parent=normal, fontSize=8,
                                     textColor=dark_text, alignment=TA_CENTER)
        td_left     = ParagraphStyle("EPTDLeft", parent=normal, fontSize=8,
                                     textColor=dark_text)
        money_style = ParagraphStyle("EPMoney", parent=normal, fontSize=8,
                                     textColor=dark_text, fontName="Helvetica-Bold",
                                     alignment=TA_CENTER)
        total_lbl   = ParagraphStyle("EPTotalLbl", parent=normal, fontSize=9,
                                     textColor=white)
        total_val   = ParagraphStyle("EPTotalVal", parent=normal, fontSize=13,
                                     textColor=white, fontName="Helvetica-Bold",
                                     alignment=TA_CENTER)

        # ── Dados da Léguas Franzinas (emitente) ──────────────────────────
        import os as _os
        try:
            from system_config.models import SystemConfiguration
            sc = SystemConfiguration.get_config()
            lf_nome      = sc.company_name or "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            lf_morada    = sc.company_morada or ""
            lf_localidade= sc.company_localidade or ""
            lf_nif       = sc.company_nif or ""
            lf_email     = sc.company_email or ""
            lf_logo_path = None
            if sc.logo:
                try:
                    _p = sc.logo.path
                    if _os.path.exists(_p): lf_logo_path = _p
                except Exception: pass
        except Exception:
            lf_nome = "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            lf_morada = lf_localidade = lf_nif = lf_email = ""
            lf_logo_path = None

        # ── Logo + header emitente ────────────────────────────────────────
        from reportlab.platypus import Image as RLImage
        try:
            raw_logo = RLImage(lf_logo_path, width=3*cm, height=3*cm, kind="proportional") if lf_logo_path else Paragraph("", sub_style)
        except Exception:
            raw_logo = Paragraph("", sub_style)

        logo_cell = Table([[raw_logo]], colWidths=[3.5*cm])
        logo_cell.setStyle(TableStyle([
            ("ALIGN",  (0,0),(-1,-1), "CENTER"),
            ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ]))

        emitente_rows = []
        for lbl, val in [("Empresa", lf_nome), ("Morada", lf_morada),
                         ("Localidade", lf_localidade), ("NIF", lf_nif), ("Email", lf_email)]:
            if val:
                emitente_rows.append([Paragraph(lbl, label_style), Paragraph(val, value_style)])
        emitente_tbl = Table(emitente_rows, colWidths=[2.5*cm, 9.5*cm])
        emitente_tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
            ("LINEBELOW",     (0,0),(-1,-1), 0.3, colors.HexColor("#E5E7EB")),
        ]))

        header = Table([[logo_cell, emitente_tbl]], colWidths=[4*cm, 13*cm])
        header.setStyle(TableStyle([
            ("VALIGN",      (0,0),(-1,-1), "MIDDLE"),
            ("LINEAFTER",   (0,0),(0,-1), 0.5, colors.HexColor("#E5E7EB")),
        ]))
        elements.append(header)
        elements.append(Spacer(1, 0.4*cm))

        # ── Faixa título ──────────────────────────────────────────────────
        month_name = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                      "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][mes-1]
        title_tbl = Table(
            [[Paragraph(f"PRÉ-FATURA EMPRESA PARCEIRA — {month_name.upper()} {ano}", title_style)]],
            colWidths=[17*cm],
        )
        title_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), indigo),
            ("TOPPADDING",    (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 10),
            ("ROUNDEDCORNERS", [4]),
        ]))
        elements.append(title_tbl)
        elements.append(Spacer(1, 0.4*cm))

        # ── Dados da Empresa Parceira (destinatária) ──────────────────────
        ep_rows = []
        for lbl, val in [
            ("Empresa",   empresa.nome),
            ("NIF",       empresa.nif or "—"),
            ("Morada",    empresa.morada or "—"),
            ("Localidade",f"{empresa.codigo_postal} {empresa.cidade}".strip() or "—"),
            ("Email",     empresa.email or "—"),
            ("Telefone",  empresa.telefone or "—"),
            ("Taxa IVA",  f"{empresa.taxa_iva}%"),
        ]:
            ep_rows.append([Paragraph(lbl, label_style), Paragraph(str(val), value_style)])
        ep_tbl = Table(ep_rows, colWidths=[3*cm, 14*cm])
        ep_tbl.setStyle(TableStyle([
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("BACKGROUND",    (0,0),(0,-1), light_gray),
            ("LINEBELOW",     (0,0),(-1,-1), 0.3, colors.HexColor("#E5E7EB")),
        ]))
        section_lbl = ParagraphStyle("EPSec", parent=normal, fontSize=9,
                                     textColor=indigo, fontName="Helvetica-Bold")
        elements.append(Paragraph("DADOS DA EMPRESA DESTINATÁRIA", section_lbl))
        elements.append(Spacer(1, 0.15*cm))
        elements.append(ep_tbl)
        elements.append(Spacer(1, 0.5*cm))

        # ── Tabela: Pré-faturas dos motoristas ────────────────────────────
        if pre_invoices:
            elements.append(Paragraph("PRÉ-FATURAS DOS MOTORISTAS", section_lbl))
            elements.append(Spacer(1, 0.15*cm))
            pf_header = [
                Paragraph("Motorista", th_style),
                Paragraph("NIF", th_style),
                Paragraph("Período", th_style),
                Paragraph("Base €", th_style),
                Paragraph("Bónus €", th_style),
                Paragraph("Total €", th_style),
                Paragraph("Estado", th_style),
            ]
            pf_rows = [pf_header]
            for pf in pre_invoices:
                pf_rows.append([
                    Paragraph(pf["driver_nome"], td_left),
                    Paragraph(pf["driver_nif"], td_style),
                    Paragraph(pf["periodo"], td_style),
                    Paragraph(f"€{float(pf['base_entregas']):.2f}", money_style),
                    Paragraph(f"€{float(pf['total_bonus']):.2f}", money_style),
                    Paragraph(f"€{float(pf['total_a_receber']):.2f}", money_style),
                    Paragraph(pf["status_display"], td_style),
                ])
            pf_tbl = Table(pf_rows, colWidths=[4.5*cm, 2*cm, 3*cm, 2*cm, 2*cm, 2*cm, 1.5*cm])
            pf_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0), indigo),
                ("TEXTCOLOR",     (0,0),(-1,0), white),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [white, light_indigo]),
                ("GRID",          (0,0),(-1,-1), 0.3, colors.HexColor("#E5E7EB")),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ]))
            elements.append(pf_tbl)
            elements.append(Spacer(1, 0.4*cm))

        # ── Tabela: Lançamentos manuais ────────────────────────────────────
        if lancamentos:
            elements.append(Paragraph("LANÇAMENTOS MANUAIS", section_lbl))
            elements.append(Spacer(1, 0.15*cm))
            lc_header = [
                Paragraph("Descrição", th_style),
                Paragraph("Período", th_style),
                Paragraph("Qtd.", th_style),
                Paragraph("Base €", th_style),
                Paragraph("Bónus €", th_style),
                Paragraph("Perdidos €", th_style),
                Paragraph("Adiant. €", th_style),
                Paragraph("Total €", th_style),
                Paragraph("Estado", th_style),
            ]
            lc_rows = [lc_header]
            for lc in lancamentos:
                lc_rows.append([
                    Paragraph(lc["descricao"], td_left),
                    Paragraph(lc["periodo"], td_style),
                    Paragraph(str(lc["qtd_entregas"]) if lc["qtd_entregas"] else "—", td_style),
                    Paragraph(f"€{float(lc['valor_base']):.2f}", money_style),
                    Paragraph(f"€{float(lc['valor_bonus']):.2f}" if float(lc['valor_bonus']) else "—", td_style),
                    Paragraph(f"-€{float(lc['pacotes_perdidos']):.2f}" if float(lc['pacotes_perdidos']) else "—", td_style),
                    Paragraph(f"-€{float(lc['adiantamentos']):.2f}" if float(lc['adiantamentos']) else "—", td_style),
                    Paragraph(f"€{float(lc['total_a_receber']):.2f}", money_style),
                    Paragraph(lc["status_display"], td_style),
                ])
            lc_tbl = Table(lc_rows, colWidths=[4*cm, 2.2*cm, 1*cm, 1.8*cm, 1.5*cm, 1.8*cm, 1.5*cm, 1.8*cm, 1.4*cm])
            lc_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,0), colors.HexColor("#4338CA")),
                ("TEXTCOLOR",     (0,0),(-1,0), white),
                ("ROWBACKGROUNDS",(0,1),(-1,-1), [white, light_indigo]),
                ("GRID",          (0,0),(-1,-1), 0.3, colors.HexColor("#E5E7EB")),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ]))
            elements.append(lc_tbl)
            elements.append(Spacer(1, 0.5*cm))

        # ── Totais com IVA ────────────────────────────────────────────────
        t = totais
        taxa_iva = float(empresa.taxa_iva)

        def money(v):
            return f"€{float(v):.2f}"

        totais_data = [
            [Paragraph("Subtotal Motoristas", label_style),
             Paragraph(money(t["total_liquido"]), bold_style)],
            [Paragraph("Subtotal Lançamentos", label_style),
             Paragraph(money(t["total_lancamentos"]), bold_style)],
            [Paragraph("Subtotal Líquido", bold_style),
             Paragraph(money(t["grand_total"]), bold_style)],
            [Paragraph(f"IVA ({taxa_iva:.2f}%)", label_style),
             Paragraph(money(t["total_iva"]), bold_style)],
        ]
        totais_tbl = Table(totais_data, colWidths=[14*cm, 3*cm])
        totais_tbl.setStyle(TableStyle([
            ("ALIGN",         (1,0),(-1,-1), "RIGHT"),
            ("TOPPADDING",    (0,0),(-1,-1), 4),
            ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LINEABOVE",     (0,2),(-1,2), 0.8, indigo),
            ("LINEABOVE",     (0,3),(-1,3), 0.4, colors.HexColor("#E5E7EB")),
            ("BACKGROUND",    (0,2),(-1,2), light_indigo),
        ]))
        elements.append(totais_tbl)
        elements.append(Spacer(1, 0.3*cm))

        # Total com IVA — destaque
        total_box = Table(
            [[Paragraph("TOTAL C/ IVA", total_lbl),
              Paragraph(money(t["total_com_iva"]), total_val)]],
            colWidths=[14*cm, 3*cm],
        )
        total_box.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), emerald),
            ("ALIGN",         (1,0),(-1,-1), "RIGHT"),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
            ("LEFTPADDING",   (0,0),(0,-1), 12),
            ("RIGHTPADDING",  (-1,0),(-1,-1), 12),
        ]))
        elements.append(total_box)
        elements.append(Spacer(1, 0.6*cm))

        # ── Rodapé ────────────────────────────────────────────────────────
        footer_style = ParagraphStyle("EPFooter", parent=normal, fontSize=7,
                                      textColor=gray_text, alignment=TA_CENTER)
        elements.append(Paragraph(
            f"Documento gerado automaticamente — {lf_nome} • {lf_nif} • {lf_email}",
            footer_style,
        ))

        doc.build(elements)
        self.buffer.seek(0)
        return self.buffer

    def save_to_field(self, settlement_or_invoice, pdf_buffer):
        """
        Salva PDF gerado no field do model.

        Args:
            settlement_or_invoice: DriverSettlement ou PartnerInvoice
            pdf_buffer: BytesIO com PDF
        """
        filename = f'{settlement_or_invoice.__class__.__name__}_{settlement_or_invoice.id}_{datetime.now().strftime("%Y%m%d")}.pdf'

        settlement_or_invoice.pdf_file.save(
            filename, ContentFile(pdf_buffer.read()), save=True
        )

    def generate_lancamento_pdf(self, lancamento):
        """
        Gera PDF de lançamento de empresa parceira (EmpresaParceiraLancamento).
        """
        self.buffer = BytesIO()

        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []
        purple = colors.HexColor("#5B21B6")
        indigo = colors.HexColor("#4338CA")
        light_indigo = colors.HexColor("#EEF2FF")
        light_gray = colors.HexColor("#F3F4F6")
        green = colors.HexColor("#16A34A")
        red = colors.HexColor("#DC2626")

        import os as _os
        try:
            from system_config.models import SystemConfiguration, CompanyProfile
            sys_config = SystemConfiguration.get_config()
            empresa_nome = sys_config.company_name or "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            empresa_morada = sys_config.company_morada or ""
            empresa_localidade = sys_config.company_localidade or ""
            empresa_nif = sys_config.company_nif or ""
            empresa_logo_path = None
            if sys_config.logo:
                try:
                    _p = sys_config.logo.path
                    if _os.path.exists(_p):
                        empresa_logo_path = _p
                except Exception:
                    pass
            if not empresa_logo_path:
                try:
                    cp = CompanyProfile.objects.first()
                    if cp and cp.assets_logo:
                        _p = cp.assets_logo.path
                        if _os.path.exists(_p):
                            empresa_logo_path = _p
                except Exception:
                    pass
        except Exception:
            empresa_nome = "LÉGUAS FRANZINAS - UNIPESSOAL LDA"
            empresa_morada = empresa_localidade = empresa_nif = ""
            empresa_logo_path = None

        normal = self.styles["Normal"]
        sub_style = ParagraphStyle("LSub", parent=normal, fontSize=9, textColor=colors.grey)
        label_style = ParagraphStyle("LLabel", parent=normal, fontSize=9, textColor=colors.HexColor("#6B7280"))
        value_style = ParagraphStyle("LValue", parent=normal, fontSize=9, textColor=colors.HexColor("#111827"))
        title_style = ParagraphStyle("LTitle", parent=self.styles["Heading1"],
            fontSize=14, textColor=colors.whitesmoke, fontName="Helvetica-Bold", alignment=TA_CENTER)

        # ── Logo + cabeçalho empresa ──────────────────────────────────────
        from reportlab.platypus import Image as RLImage
        try:
            if empresa_logo_path:
                raw_logo = RLImage(empresa_logo_path, width=3 * cm, height=3 * cm, kind="proportional")
            else:
                raw_logo = Paragraph("", sub_style)
        except Exception:
            raw_logo = Paragraph("", sub_style)

        empresa_rows = []
        for label, val in [
            ("Empresa", empresa_nome),
            ("Morada", empresa_morada),
            ("Localidade", empresa_localidade),
            ("NIF", empresa_nif),
        ]:
            if val:
                empresa_rows.append([Paragraph(label, label_style), Paragraph(val, value_style)])

        empresa_inner = Table(empresa_rows, colWidths=[2.5 * cm, 9 * cm])
        empresa_inner.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))

        header_tbl = Table([[raw_logo, empresa_inner]], colWidths=[4 * cm, 13 * cm])
        header_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_tbl)
        elements.append(Spacer(1, 0.5 * cm))

        # ── Barra de título ───────────────────────────────────────────────
        status_colors = {
            "RASCUNHO": colors.HexColor("#6B7280"),
            "APROVADO": colors.HexColor("#2563EB"),
            "PENDENTE": colors.HexColor("#D97706"),
            "PAGO": colors.HexColor("#16A34A"),
            "CANCELADO": colors.HexColor("#DC2626"),
        }
        bar_color = status_colors.get(lancamento.status, indigo)

        title_tbl = Table(
            [[Paragraph(f"LANÇAMENTO DE EMPRESA PARCEIRA", title_style)]],
            colWidths=[17 * cm],
        )
        title_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), indigo),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(title_tbl)
        elements.append(Spacer(1, 0.4 * cm))

        # ── Dados do lançamento ───────────────────────────────────────────
        info_rows = [
            ["Empresa Parceira", lancamento.empresa.nome],
            ["NIF", lancamento.empresa.nif or "—"],
            ["IBAN", lancamento.empresa.iban or "—"],
            ["Descrição do Serviço", lancamento.descricao],
            ["Período",
             f"{lancamento.periodo_inicio.strftime('%d/%m/%Y')} → {lancamento.periodo_fim.strftime('%d/%m/%Y')}"],
            ["Status", lancamento.get_status_display()],
        ]
        if lancamento.data_pagamento:
            info_rows.append(["Data de Pagamento", lancamento.data_pagamento.strftime("%d/%m/%Y")])
        if lancamento.referencia_pagamento:
            info_rows.append(["Referência de Pagamento", lancamento.referencia_pagamento])

        info_data = [
            [Paragraph(r[0], label_style), Paragraph(str(r[1]), value_style)]
            for r in info_rows
        ]
        info_tbl = Table(info_data, colWidths=[5 * cm, 12 * cm])
        info_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), light_indigo),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(info_tbl)
        elements.append(Spacer(1, 0.5 * cm))

        # ── Tabela de valores ─────────────────────────────────────────────
        val_header = ParagraphStyle("VH", parent=normal, fontSize=9, textColor=colors.whitesmoke, fontName="Helvetica-Bold")
        val_label = ParagraphStyle("VL", parent=normal, fontSize=9, textColor=colors.HexColor("#374151"))
        val_num = ParagraphStyle("VN", parent=normal, fontSize=9, textColor=colors.HexColor("#111827"), alignment=TA_LEFT)

        valores_header = [[
            Paragraph("Componente", val_header),
            Paragraph("Valor (€)", val_header),
        ]]
        valores_rows = []
        if lancamento.qtd_entregas > 0:
            valores_rows.append([
                Paragraph(f"Entregas ({lancamento.qtd_entregas} × €{lancamento.valor_por_entrega})", val_label),
                Paragraph(f"€ {lancamento.valor_base:,.2f}", val_num),
            ])
        else:
            valores_rows.append([
                Paragraph("Base", val_label),
                Paragraph(f"€ {lancamento.valor_base:,.2f}", val_num),
            ])
        if lancamento.valor_bonus:
            valores_rows.append([
                Paragraph("Bónus", val_label),
                Paragraph(f"€ {lancamento.valor_bonus:,.2f}", val_num),
            ])
        if lancamento.pacotes_perdidos:
            valores_rows.append([
                Paragraph("Pacotes Perdidos (desconto)", val_label),
                Paragraph(f"- € {lancamento.pacotes_perdidos:,.2f}", val_num),
            ])
        if lancamento.adiantamentos:
            valores_rows.append([
                Paragraph("Adiantamentos / Combustível (desconto)", val_label),
                Paragraph(f"- € {lancamento.adiantamentos:,.2f}", val_num),
            ])

        subtotal_style = ParagraphStyle("VS", parent=normal, fontSize=9,
            textColor=colors.HexColor("#374151"), fontName="Helvetica-Bold")
        total_style = ParagraphStyle("VT", parent=normal, fontSize=10,
            textColor=colors.whitesmoke, fontName="Helvetica-Bold")

        # Subtotal sem IVA
        valores_rows.append([
            Paragraph("Subtotal (sem IVA)", subtotal_style),
            Paragraph(f"€ {lancamento.total_a_receber:,.2f}", subtotal_style),
        ])
        # IVA
        if lancamento.taxa_iva:
            valores_rows.append([
                Paragraph(f"IVA ({lancamento.taxa_iva}%)", val_label),
                Paragraph(f"€ {lancamento.valor_iva:,.2f}", val_num),
            ])
        # Total com IVA
        valores_rows.append([
            Paragraph("TOTAL COM IVA", total_style),
            Paragraph(f"€ {lancamento.total_com_iva:,.2f}", total_style),
        ])

        val_data = valores_header + valores_rows
        val_tbl = Table(val_data, colWidths=[12 * cm, 5 * cm])
        last = len(val_data) - 1
        subtotal_idx = last - (2 if lancamento.taxa_iva else 1)
        val_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), indigo),
            ("BACKGROUND", (0, subtotal_idx), (-1, subtotal_idx), light_gray),
            ("BACKGROUND", (0, last), (-1, last), green if lancamento.total_com_iva >= 0 else red),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, subtotal_idx - 1), [colors.white, light_gray]),
        ]))
        elements.append(val_tbl)

        if lancamento.notas:
            elements.append(Spacer(1, 0.4 * cm))
            notas_header = ParagraphStyle("NH", parent=normal, fontSize=9, textColor=colors.whitesmoke, fontName="Helvetica-Bold")
            notas_tbl = Table(
                [[Paragraph("Notas", notas_header)], [Paragraph(lancamento.notas, value_style)]],
                colWidths=[17 * cm],
            )
            notas_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6B7280")),
                ("BACKGROUND", (0, 1), (-1, 1), light_gray),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]))
            elements.append(notas_tbl)

        # ── Rodapé ────────────────────────────────────────────────────────
        elements.append(Spacer(1, 1 * cm))
        footer_style = ParagraphStyle("LF", parent=normal, fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
        elements.append(Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — {empresa_nome}",
            footer_style,
        ))

        doc.build(elements)
        self.buffer.seek(0)
        return self.buffer
