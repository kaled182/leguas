from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal
import os


def validate_document_extension(value):
    """Valida as extensões de arquivo permitidas para upload"""
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.xlsx', '.xls', '.doc', '.docx']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            f'Arquivo não suportado. Extensões permitidas: {", ".join(allowed_extensions)}'
        )


def upload_to_revenues(instance, filename):
    """Define o caminho de upload para documentos de receitas"""
    return f'accounting/revenues/{instance.user.id}/{filename}'


def upload_to_expenses(instance, filename):
    """Define o caminho de upload para documentos de despesas"""
    return f'accounting/expenses/{instance.user.id}/{filename}'

# Create your models here.
class Revenues(models.Model):
    """
    Modelo para armazenar todas receitas/entradas da empresa
    """
    
    NATUREZA_CHOICES = [
        ('VENDA', 'Venda de Serviços'),
        ('CONSULTORIA', 'Consultoria'),
        ('PRODUTO', 'Venda de Produtos'),
        ('JUROS', 'Juros'),
        ('DIVIDENDOS', 'Dividendos'),
        ('ROYALTIES', 'Royalties'),
        ('OUTROS', 'Outros'),
    ]
    
    FONTE_CHOICES = [
        ('CLIENTE_DIRETO', 'Cliente Direto'),
        ('MARKETPLACE', 'Marketplace'),
        ('PARCEIRO', 'Parceiro'),
        ('INVESTIMENTO', 'Investimento'),
        ('BANCO', 'Banco'),
        ('GOVERNO', 'Governo'),
        ('OUTROS', 'Outros'),
    ]
    
    # Usuário que está registrando a receita
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Usuário",
        help_text="Usuário responsável pelo registro"
    )
    
    # Natureza da entrada
    natureza = models.CharField(
        max_length=20,
        choices=NATUREZA_CHOICES,
        verbose_name="Natureza da Entrada",
        help_text="Tipo/categoria da receita"
    )
    
    # Valores
    valor_sem_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor sem IVA",
        help_text="Valor da receita sem impostos"
    )
    
    valor_com_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor com IVA",
        help_text="Valor da receita com impostos incluídos"
    )
    
    # Data da entrada
    data_entrada = models.DateField(
        verbose_name="Data da Entrada",
        help_text="Data em que a receita foi recebida"
    )
    
    # Fonte da entrada
    fonte = models.CharField(
        max_length=20,
        choices=FONTE_CHOICES,
        verbose_name="Fonte da Entrada",
        help_text="Origem/fonte da receita"
    )
    
    # Campos adicionais úteis
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da receita"
    )
    
    referencia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Referência",
        help_text="Número de fatura, contrato ou outra referência"
    )
    
    # Upload de documento
    documento = models.FileField(
        upload_to=upload_to_revenues,
        validators=[validate_document_extension],
        blank=True,
        null=True,
        verbose_name="Documento",
        help_text="Upload do documento que comprova a receita (PDF, JPG, XLSX, etc.)"
    )
    
    # Metadados
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Receita"
        verbose_name_plural = "Receitas"
        ordering = ['-data_entrada', '-criado_em']
        
    def __str__(self):
        return f"{self.natureza} - €{self.valor_com_iva} - {self.data_entrada}"
    
    @property
    def iva_valor(self):
        """Calcula o valor do IVA"""
        return self.valor_com_iva - self.valor_sem_iva
    
    @property
    def percentual_iva(self):
        """Calcula o percentual de IVA"""
        if self.valor_sem_iva > 0:
            return ((self.valor_com_iva - self.valor_sem_iva) / self.valor_sem_iva) * 100
        return Decimal('0.00')
    
    @property
    def tem_documento(self):
        """Verifica se há documento anexado"""
        return bool(self.documento)
    
    @property
    def nome_documento(self):
        """Retorna o nome do arquivo sem o caminho"""
        if self.documento:
            return os.path.basename(self.documento.name)
        return None
    
    @property
    def extensao_documento(self):
        """Retorna a extensão do documento"""
        if self.documento:
            return os.path.splitext(self.documento.name)[1].lower()
        return None


class Expenses(models.Model):
    """
    Modelo para armazenar todas despesas/saídas da empresa
    """
    
    NATUREZA_CHOICES = [
        ('OPERACIONAL', 'Despesa Operacional'),
        ('MARKETING', 'Marketing e Publicidade'),
        ('TECNOLOGIA', 'Tecnologia e Software'),
        ('PESSOAL', 'Pessoal e Salários'),
        ('ALUGUEL', 'Aluguel e Utilities'),
        ('VIAGEM', 'Viagens e Hospedagem'),
        ('MATERIAL', 'Material de Escritório'),
        ('JURIDICO', 'Serviços Jurídicos'),
        ('CONTABIL', 'Serviços Contábeis'),
        ('FINANCEIRO', 'Taxas e Juros'),
        ('MANUTENCAO', 'Manutenção'),
        ('COMBUSTIVEL', 'Combustível'),
        ('SEGURO', 'Seguros'),
        ('IMPOSTOS', 'Impostos e Taxas'),
        ('OUTROS', 'Outros'),
    ]
    
    FONTE_CHOICES = [
        ('FORNECEDOR', 'Fornecedor'),
        ('PRESTADOR', 'Prestador de Serviços'),
        ('FUNCIONARIO', 'Funcionário'),
        ('GOVERNO', 'Governo'),
        ('BANCO', 'Banco'),
        ('SEGURADORA', 'Seguradora'),
        ('UTILIDADE', 'Empresa de Utilidades'),
        ('OUTROS', 'Outros'),
    ]
    
    # Usuário que está registrando a despesa
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Usuário",
        help_text="Usuário responsável pelo registro"
    )
    
    # Natureza da saída
    natureza = models.CharField(
        max_length=20,
        choices=NATUREZA_CHOICES,
        verbose_name="Natureza da Despesa",
        help_text="Tipo/categoria da despesa"
    )
    
    # Valores
    valor_sem_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor sem IVA",
        help_text="Valor da despesa sem impostos"
    )
    
    valor_com_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Valor com IVA",
        help_text="Valor da despesa com impostos incluídos"
    )
    
    # Data da saída
    data_entrada = models.DateField(
        verbose_name="Data da Despesa",
        help_text="Data em que a despesa foi realizada"
    )
    
    # Fonte da despesa
    fonte = models.CharField(
        max_length=20,
        choices=FONTE_CHOICES,
        verbose_name="Fonte da Despesa",
        help_text="Origem/destinatário da despesa"
    )
    
    # Campos adicionais úteis
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da despesa"
    )
    
    referencia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Referência",
        help_text="Número de fatura, recibo ou outra referência"
    )
    
    # Upload de documento
    documento = models.FileField(
        upload_to=upload_to_expenses,
        validators=[validate_document_extension],
        blank=True,
        null=True,
        verbose_name="Documento",
        help_text="Upload do documento que comprova a despesa (PDF, JPG, XLSX, etc.)"
    )
    
    # Status de pagamento
    pago = models.BooleanField(
        default=False,
        verbose_name="Pago",
        help_text="Indica se a despesa já foi paga"
    )
    
    data_pagamento = models.DateField(
        blank=True,
        null=True,
        verbose_name="Data do Pagamento",
        help_text="Data em que a despesa foi efetivamente paga"
    )
    
    # Metadados
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    
    atualizado_em = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    class Meta:
        verbose_name = "Despesa"
        verbose_name_plural = "Despesas"
        ordering = ['-data_entrada', '-criado_em']
        
    def __str__(self):
        status = "✓" if self.pago else "✗"
        return f"{self.natureza} - €{self.valor_com_iva} - {self.data_entrada} [{status}]"
    
    @property
    def iva_valor(self):
        """Calcula o valor do IVA"""
        return self.valor_com_iva - self.valor_sem_iva
    
    @property
    def percentual_iva(self):
        """Calcula o percentual de IVA"""
        if self.valor_sem_iva > 0:
            return ((self.valor_com_iva - self.valor_sem_iva) / self.valor_sem_iva) * 100
        return Decimal('0.00')
    
    @property
    def status_pagamento(self):
        """Retorna o status de pagamento em texto"""
        return "Pago" if self.pago else "Pendente"
    
    @property
    def tem_documento(self):
        """Verifica se há documento anexado"""
        return bool(self.documento)
    
    @property
    def nome_documento(self):
        """Retorna o nome do arquivo sem o caminho"""
        if self.documento:
            return os.path.basename(self.documento.name)
        return None
    
    @property
    def extensao_documento(self):
        """Retorna a extensão do documento"""
        if self.documento:
            return os.path.splitext(self.documento.name)[1].lower()
        return None