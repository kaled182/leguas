"""
Modelos para autenticação customizada de motoristas.

Este módulo contém:
- DriverAccess: Modelo para acesso de motoristas
- DriverRoute: Utilitário para gerenciar rotas de motoristas
"""

from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password


class DriverAccess(models.Model):
    """
    Modelo para gerenciar acessos de motoristas ao sistema.
    
    Este modelo permite que gestores criem contas para motoristas
    acessarem suas rotas e pedidos sem usar o sistema de usuários do Django.
    """
    
    # Relacionamentos
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='drivers',
        verbose_name="Gestor Responsável",
        help_text="Gestor responsável por este motorista"
    )
    driver = models.ForeignKey(
        'ordersmanager_paack.Driver', 
        on_delete=models.CASCADE, 
        related_name='driver_accesses', 
        null=True, 
        blank=True,
        verbose_name="Motorista",
        help_text="Motorista do sistema de pedidos"
    )
    
    # Informações pessoais
    profile_picture = models.ImageField(upload_to='drivers/profile_pictures/', null=True, blank=True)

    first_name = models.CharField(
        max_length=100,
        verbose_name="Nome",
        help_text="Nome do motorista"
    )
    last_name = models.CharField(
        max_length=100,
        verbose_name="Sobrenome",
        help_text="Sobrenome do motorista"
    )
    phone = models.CharField(
        max_length=20,
        verbose_name="Telefone",
        help_text="Número de telefone do motorista"
    )
    nif = models.CharField(
        max_length=20,
        verbose_name="NIF",
        help_text="Número de identificação fiscal"
    )
    email = models.EmailField(
        unique=True,
        verbose_name="Email",
        help_text="Email único para login"
    )
    
    # Autenticação
    password = models.CharField(
        max_length=128,
        verbose_name="Senha",
        help_text="Hash da senha para autenticação"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Acesso de Motorista"
        verbose_name_plural = "Acessos de Motoristas"
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        """Retorna o nome completo do motorista."""
        return f"{self.first_name} {self.last_name}"

    def set_password(self, raw_password):
        """Define a senha do motorista usando hash seguro."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifica se a senha está correta."""
        return check_password(raw_password, self.password)

    def get_route(self, date=None):
        """Retorna o objeto DriverRoute para este motorista."""
        return DriverRoute(self.driver) if self.driver else None


class DriverRoute:
    """
    Classe utilitária para montar e gerenciar a rota de um motorista.
    
    Esta classe fornece métodos para acessar os pedidos atribuídos
    a um motorista específico, com filtros opcionais por data.
    """
    
    def __init__(self, driver):
        """
        Inicializa a rota para um Driver específico.
        
        Args:
            driver: Instância do modelo Driver
        """
        self.driver = driver

    def get_orders(self, date=None):
        """
        Retorna os pedidos atribuídos ao motorista.
        
        Args:
            date (date, optional): Data para filtrar pedidos
            
        Returns:
            QuerySet: Pedidos do motorista
        """
        if not self.driver:
            from ordersmanager_paack.models import Order
            return Order.objects.none()
            
        # Importação local para evitar import circular
        from ordersmanager_paack.models import Order  
        
        qs = Order.objects.filter(dispatch__driver=self.driver)
        
        if date:
            qs = qs.filter(intended_delivery_date=date)
            
        return qs.order_by('intended_delivery_date', 'created_at')

    def get_orders_count(self, date=None):
        """Retorna o número total de pedidos."""
        return self.get_orders(date).count()

    def get_delivered_count(self, date=None):
        """Retorna o número de pedidos entregues."""
        return self.get_orders(date).filter(is_delivered=True).count()

    def get_failed_count(self, date=None):
        """Retorna o número de pedidos falhados."""
        return self.get_orders(date).filter(is_failed=True).count()

    def get_pending_count(self, date=None):
        """Retorna o número de pedidos pendentes."""
        orders = self.get_orders(date)
        return orders.filter(is_delivered=False, is_failed=False).count()

    def as_dict(self, date=None):
        """
        Retorna a rota como uma lista de dicionários com informações dos pedidos.
        
        Args:
            date (date, optional): Data para filtrar pedidos
            
        Returns:
            list: Lista de dicionários com dados dos pedidos
        """
        orders = self.get_orders(date)
        return [
            {
                'order_id': order.order_id,
                'retailer': order.retailer,
                'client_address': order.client_address,
                'intended_delivery_date': order.intended_delivery_date,
                'actual_delivery_date': order.actual_delivery_date,
                'status': order.simplified_order_status,
                'is_delivered': order.is_delivered,
                'is_failed': order.is_failed,
            }
            for order in orders
        ]

