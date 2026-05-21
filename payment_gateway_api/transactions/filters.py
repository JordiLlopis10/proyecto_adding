"""
Filtros para la app transactions.

Permite consultar el historial de transacciones aplicando filtros por
proveedor, fecha y estado, tal y como exige el requisito funcional
"Historial parametrizado" del proyecto.
"""
import django_filters

from .models import Incident, Transaction


class TransactionFilter(django_filters.FilterSet):
    """
    Filtros expuestos en ``GET /api/v1/transactions/``.

    Ejemplos:

        /api/v1/transactions/?status=completed
        /api/v1/transactions/?provider=1&status=pending
        /api/v1/transactions/?date_from=2025-01-01&date_to=2025-12-31
        /api/v1/transactions/?provider_code=stripe&min_amount=100
    """

    date_from = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='Fecha mínima (YYYY-MM-DD).',
    )
    date_to = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='Fecha máxima (YYYY-MM-DD).',
    )
    min_amount = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='gte',
    )
    max_amount = django_filters.NumberFilter(
        field_name='amount',
        lookup_expr='lte',
    )
    provider_code = django_filters.CharFilter(
        field_name='provider__code',
        lookup_expr='iexact',
    )

    class Meta:
        """Configuración del filtro."""

        model = Transaction
        fields = ['provider', 'provider_code', 'status', 'currency']


class IncidentFilter(django_filters.FilterSet):
    """Filtros expuestos en ``GET /api/v1/incidents/``."""

    date_from = django_filters.DateFilter(
        field_name='created_at', lookup_expr='gte'
    )
    date_to = django_filters.DateFilter(
        field_name='created_at', lookup_expr='lte'
    )

    class Meta:
        """Configuración del filtro."""

        model = Incident
        fields = ['transaction', 'incident_type', 'resolved']
