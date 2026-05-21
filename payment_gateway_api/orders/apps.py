"""Configuración de la app orders."""
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """App que gestiona pedidos y el flujo de pago por redirección."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'
    verbose_name = 'Pedidos'
