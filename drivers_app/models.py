from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta


class DriverProfile(models.Model):
    """Perfil completo do motorista com todos os dados pessoais e profissionais"""
    
    # Status do Cadastro
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente - Aguardando documentos'),
        ('EM_ANALISE', 'Em Analise - Documentos enviados'),
        ('ATIVO', 'Ativo - Aprovado'),
        ('BLOQUEADO', 'Bloqueado - Documentos expirados'),
        ('IRREGULAR', 'Irregular - Problemas no cadastro'),
    ]
    
    # Vinculo Profissional
    VINCULO_CHOICES = [
        ('DIRETO', 'Direto - Recibos Verdes'),
        ('PARCEIRO', 'Parceiro - Frota'),
    ]
    
    # === A. DADOS PESSOAIS E IDENTIFICACAO ===
    nif = models.CharField(
        max_length=9, 
        unique=True, 
        validators=[RegexValidator(r'^\d{9}$', 'NIF deve conter exatamente 9 digitos')],
        verbose_name='NIF'
    )
    nome_completo = models.CharField(max_length=200, verbose_name='Nome Completo')
    niss = models.CharField(
        max_length=11,
        validators=[RegexValidator(r'^\d{11}$', 'NISS deve conter 11 digitos')],
        verbose_name='NISS',
        blank=True,
        null=True
    )
    data_nascimento = models.DateField(verbose_name='Data de Nascimento', null=True, blank=True)
    nacionalidade = models.CharField(max_length=100, default='Portugal')
    telefone = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?[0-9]{9,15}$', 'Telefone invalido')],
        verbose_name='Telefone'
    )
    email = models.EmailField(verbose_name='Email')
    endereco_residencia = models.TextField(verbose_name='Endereco Completo', blank=True)
    codigo_postal = models.CharField(max_length=8, blank=True, verbose_name='Codigo Postal')
    cidade = models.CharField(max_length=100, blank=True)
    
    # === C. VINCULO PROFISSIONAL ===
    tipo_vinculo = models.CharField(
        max_length=10,
        choices=VINCULO_CHOICES,
        default='DIRETO',
        verbose_name='Tipo de Vinculo'
    )
    nome_frota = models.CharField(
        max_length=200, 
        blank=True,
        verbose_name='Nome da Frota (se Parceiro)'
    )
    
    # === STATUS E CONTROLE ===
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='PENDENTE',
        verbose_name='Status do Cadastro'
    )
    is_active = models.BooleanField(default=False, verbose_name='Ativo no Sistema')
    
    # === METADADOS ===
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='Data de Aprovacao')
    approved_by = models.CharField(max_length=100, blank=True, verbose_name='Aprovado por')
    
    # Observacoes internas
    observacoes = models.TextField(blank=True, verbose_name='Observacoes Internas')
    
    class Meta:
        verbose_name = 'Perfil de Motorista'
        verbose_name_plural = 'Perfis de Motoristas'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.nome_completo} - {self.nif}"
    
    def has_expired_documents(self):
        """Verifica se algum documento esta expirado"""
        return self.documents.filter(data_validade__lt=timezone.now().date()).exists()
    
    def get_documents_expiring_soon(self, days=30):
        """Retorna documentos que expiram em X dias"""
        future_date = timezone.now().date() + timedelta(days=days)
        return self.documents.filter(
            data_validade__lte=future_date,
            data_validade__gt=timezone.now().date()
        )


class DriverDocument(models.Model):
    """Documentos do motorista com controle de validade"""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('CC', 'Cartao de Cidadao'),
        ('TR', 'Titulo de Residencia'),
        ('PP', 'Passaporte'),
        ('MI', 'Manifestacao de Interesse'),
        ('CNH_FRENTE', 'Carta de Conducao - Frente'),
        ('CNH_VERSO', 'Carta de Conducao - Verso'),
        ('ADR', 'Certificado ADR'),
        ('RC', 'Registo Criminal'),
        ('DECLARACAO_ATIVIDADE', 'Declaracao de Inicio de Atividade'),
        ('OUTRO', 'Outro Documento'),
    ]
    
    motorista = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Motorista'
    )
    tipo_documento = models.CharField(
        max_length=30,
        choices=TIPO_DOCUMENTO_CHOICES,
        verbose_name='Tipo de Documento'
    )
    arquivo = models.FileField(
        upload_to='driver_documents/%Y/%m/',
        verbose_name='Arquivo'
    )
    data_validade = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data de Validade',
        help_text='Sistema alerta 30 dias antes do vencimento'
    )
    categoria_cnh = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Categoria CNH',
        help_text='Ex: B, C, D'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Upload')
    observacoes = models.TextField(blank=True, verbose_name='Observacoes')
    
    class Meta:
        verbose_name = 'Documento do Motorista'
        verbose_name_plural = 'Documentos dos Motoristas'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.motorista.nome_completo} - {self.get_tipo_documento_display()}"
    
    @property
    def is_expired(self):
        """Verifica se documento esta vencido"""
        if self.data_validade:
            return self.data_validade < timezone.now().date()
        return False
    
    @property
    def days_until_expiration(self):
        """Dias ate o vencimento"""
        if self.data_validade:
            delta = self.data_validade - timezone.now().date()
            return delta.days
        return None
    
    @property
    def file_extension(self):
        """Retorna a extensao do arquivo"""
        import os
        if self.arquivo:
            return os.path.splitext(self.arquivo.name)[1].lower()
        return ''


class Vehicle(models.Model):
    """Veiculo do motorista"""
    
    TIPO_VEICULO_CHOICES = [
        ('MOTA', 'Mota'),
        ('LIGEIRO', 'Ligeiro de Mercadorias'),
        ('CARRINHA_35T', 'Carrinha ate 3.5t'),
        ('CARRINHA_GRANDE', 'Carrinha acima 3.5t'),
        ('OUTRO', 'Outro'),
    ]
    
    motorista = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name='vehicles',
        verbose_name='Motorista'
    )
    matricula = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Matricula',
        validators=[RegexValidator(r'^[A-Z0-9-]+$', 'Matricula invalida')]
    )
    marca = models.CharField(max_length=100, verbose_name='Marca')
    modelo = models.CharField(max_length=100, verbose_name='Modelo')
    tipo_veiculo = models.CharField(
        max_length=20,
        choices=TIPO_VEICULO_CHOICES,
        verbose_name='Tipo de Veiculo'
    )
    ano = models.PositiveIntegerField(null=True, blank=True, verbose_name='Ano')
    cor = models.CharField(max_length=50, blank=True, verbose_name='Cor')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='Veiculo Ativo')
    
    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Veiculo'
        verbose_name_plural = 'Veiculos'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.matricula} - {self.marca} {self.modelo}"
    
    def has_expired_documents(self):
        """Verifica se algum documento do veiculo esta expirado"""
        return self.vehicle_documents.filter(data_validade__lt=timezone.now().date()).exists()


class VehicleDocument(models.Model):
    """Documentos do veiculo"""
    
    TIPO_DOC_VEICULO_CHOICES = [
        ('DUA', 'DUA - Documento Unico Automovel'),
        ('IPO', 'Folha da Inspecao (IPO)'),
        ('SEGURO', 'Certificado de Seguro (Carta Verde)'),
        ('OUTRO', 'Outro Documento'),
    ]
    
    veiculo = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='vehicle_documents',
        verbose_name='Veiculo'
    )
    tipo_documento = models.CharField(
        max_length=20,
        choices=TIPO_DOC_VEICULO_CHOICES,
        verbose_name='Tipo de Documento'
    )
    arquivo = models.FileField(
        upload_to='vehicle_documents/%Y/%m/',
        verbose_name='Arquivo'
    )
    data_validade = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data de Validade'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Data de Upload')
    observacoes = models.TextField(blank=True, verbose_name='Observacoes')
    
    class Meta:
        verbose_name = 'Documento do Veiculo'
        verbose_name_plural = 'Documentos dos Veiculos'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.veiculo.matricula} - {self.get_tipo_documento_display()}"
    
    @property
    def is_expired(self):
        """Verifica se documento esta vencido"""
        if self.data_validade:
            return self.data_validade < timezone.now().date()
        return False
    
    @property
    def file_extension(self):
        """Retorna a extensao do arquivo"""
        import os
        if self.arquivo:
            return os.path.splitext(self.arquivo.name)[1].lower()
        return ''
