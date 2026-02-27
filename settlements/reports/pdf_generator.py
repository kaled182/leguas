"""
PDFGenerator: Gerador de PDFs de settlement para motoristas.
Usa reportlab para criar extratos detalhados.
"""
from decimal import Decimal
from io import BytesIO
from datetime import datetime
from django.core.files.base import ContentFile

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
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
                "reportlab não está instalado. "
                "Instale com: pip install reportlab"
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
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Elementos do PDF
        elements = []
        
        # Header
        elements.append(self._create_header())
        elements.append(Spacer(1, 0.5*cm))
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2196F3'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        period_text = self._format_period(settlement)
        title = Paragraph(f'EXTRATO DE ACERTO<br/>{period_text}', title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.5*cm))
        
        # Informações do motorista
        driver_info = [
            ['<b>Motorista:</b>', settlement.driver.nome_completo],
            ['<b>Email:</b>', settlement.driver.email or '-'],
            ['<b>Telefone:</b>', settlement.driver.contact_phone or '-'],
        ]
        
        if settlement.partner:
            driver_info.append(['<b>Parceiro:</b>', settlement.partner.name])
        
        driver_table = Table(driver_info, colWidths=[4*cm, 12*cm])
        driver_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        elements.append(driver_table)
        elements.append(Spacer(1, 0.8*cm))
        
        # Estatísticas de entregas
        stats_data = [
            ['ESTATÍSTICAS DE ENTREGAS', '', ''],
            ['Total de Pedidos:', str(settlement.total_orders), ''],
            ['Pedidos Entregues:', str(settlement.delivered_orders), ''],
            ['Pedidos Falhados:', str(settlement.failed_orders), ''],
            ['Taxa de Sucesso:', f'{settlement.success_rate}%', ''],
        ]
        
        stats_table = Table(stats_data, colWidths=[8*cm, 4*cm, 4*cm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 0.8*cm))
        
        # Valores financeiros
        financial_data = [
            ['VALORES FINANCEIROS', '', ''],
            ['Valor Bruto:', f'€{settlement.gross_amount:,.2f}', '+'],
            ['Bônus por Performance:', f'€{settlement.bonus_amount:,.2f}', '+'],
            ['Desconto Combustível:', f'€{settlement.fuel_deduction:,.2f}', '-'],
            ['Descontos (Claims):', f'€{settlement.claims_deducted:,.2f}', '-'],
            ['Outros Descontos:', f'€{settlement.other_deductions:,.2f}', '-'],
            ['<b>VALOR LÍQUIDO:</b>', f'<b>€{settlement.net_amount:,.2f}</b>', ''],
        ]
        
        financial_table = Table(financial_data, colWidths=[8*cm, 6*cm, 2*cm])
        financial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 10),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F5E9')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
        ]))
        
        elements.append(financial_table)
        elements.append(Spacer(1, 0.8*cm))
        
        # Claims detalhados (se houver)
        claims = settlement.claims.all()
        if claims.exists():
            elements.append(Paragraph('<b>DESCONTOS APLICADOS:</b>', self.styles['Heading3']))
            elements.append(Spacer(1, 0.3*cm))
            
            claims_data = [['Tipo', 'Descrição', 'Valor']]
            
            for claim in claims:
                claims_data.append([
                    claim.get_claim_type_display(),
                    claim.description[:50] + '...' if len(claim.description) > 50 else claim.description,
                    f'€{claim.amount:,.2f}'
                ])
            
            claims_table = Table(claims_data, colWidths=[4*cm, 8*cm, 4*cm])
            claims_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF5722')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ]))
            
            elements.append(claims_table)
            elements.append(Spacer(1, 0.5*cm))
        
        # Notas
        if settlement.notes:
            elements.append(Spacer(1, 0.5*cm))
            elements.append(Paragraph('<b>Notas:</b>', self.styles['Heading4']))
            elements.append(Paragraph(settlement.notes, self.styles['Normal']))
        
        # Footer
        elements.append(Spacer(1, 1*cm))
        footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        footer = Paragraph(
            f'Documento gerado automaticamente em {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/>'
            'Léguas Franzinas - Sistema de Gestão Logística',
            footer_style
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
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        elements = []
        
        # Header
        elements.append(self._create_header())
        elements.append(Spacer(1, 0.5*cm))
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2196F3'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        title = Paragraph(f'FATURA<br/>{invoice.invoice_number}', title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.5*cm))
        
        # Informações
        info_data = [
            ['<b>Parceiro:</b>', invoice.partner.name],
            ['<b>Período:</b>', f'{invoice.period_start.strftime("%d/%m/%Y")} a {invoice.period_end.strftime("%d/%m/%Y")}'],
            ['<b>Data de Emissão:</b>', invoice.issue_date.strftime("%d/%m/%Y")],
            ['<b>Data de Vencimento:</b>', invoice.due_date.strftime("%d/%m/%Y")],
            ['<b>Status:</b>', invoice.get_status_display()],
        ]
        
        info_table = Table(info_data, colWidths=[5*cm, 11*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 1*cm))
        
        # Valores
        values_data = [
            ['DISCRIMINAÇÃO', 'VALOR'],
            ['Valor Bruto:', f'€{invoice.gross_amount:,.2f}'],
            ['IVA (23%):', f'€{invoice.tax_amount:,.2f}'],
            ['<b>TOTAL A PAGAR:</b>', f'<b>€{invoice.net_amount:,.2f}</b>'],
        ]
        
        values_table = Table(values_data, colWidths=[10*cm, 6*cm])
        values_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E3F2FD')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(values_table)
        elements.append(Spacer(1, 1*cm))
        
        # Estatísticas
        stats = Paragraph(
            f'<b>Total de pedidos:</b> {invoice.total_orders}<br/>'
            f'<b>Pedidos entregues:</b> {invoice.total_delivered}',
            self.styles['Normal']
        )
        elements.append(stats)
        
        # Footer
        elements.append(Spacer(1, 2*cm))
        footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        footer = Paragraph(
            f'Documento gerado automaticamente em {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/>'
            'Léguas Franzinas - Sistema de Gestão Logística',
            footer_style
        )
        elements.append(footer)
        
        doc.build(elements)
        
        self.buffer.seek(0)
        return self.buffer
    
    def _create_header(self):
        """Cria header padrão do PDF"""
        header_style = ParagraphStyle(
            'Header',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#2196F3'),
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        
        return Paragraph('Léguas Franzinas', header_style)
    
    def _format_period(self, settlement):
        """Formata período do settlement"""
        if settlement.period_type == 'WEEKLY':
            return f'Semana {settlement.week_number}/{settlement.year}'
        return f'{settlement.month_number:02d}/{settlement.year}'
    
    def save_to_field(self, settlement_or_invoice, pdf_buffer):
        """
        Salva PDF gerado no field do model.
        
        Args:
            settlement_or_invoice: DriverSettlement ou PartnerInvoice
            pdf_buffer: BytesIO com PDF
        """
        filename = f'{settlement_or_invoice.__class__.__name__}_{settlement_or_invoice.id}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        settlement_or_invoice.pdf_file.save(
            filename,
            ContentFile(pdf_buffer.read()),
            save=True
        )
