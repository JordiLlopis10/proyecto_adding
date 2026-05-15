"""Configuración de la app transactions."""
from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    """Configuración de la aplicación de transacciones e incidencias."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'transactions'
    verbose_name = 'Transacciones e incidencias'
