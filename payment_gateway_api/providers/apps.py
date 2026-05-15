"""Configuración de la app providers."""
from django.apps import AppConfig


class ProvidersConfig(AppConfig):
    """Configuración de la aplicación de proveedores de pago."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'providers'
    verbose_name = 'Proveedores de pago'
