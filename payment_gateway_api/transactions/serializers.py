"""
Serializadores para la app transactions.

Convierten las instancias de :class:`Transaction` e :class:`Incident` a JSON
(y viceversa) y aplican las validaciones de negocio.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import Incident, Transaction


# Monedas aceptadas por el sistema (ISO 4217).
ALLOWED_CURRENCIES = {'EUR', 'USD', 'GBP', 'JPY', 'CHF', 'MXN', 'ARS'}


class IncidentSerializer(serializers.ModelSerializer):
    """Serializador del modelo Incident."""

    incident_type_display = serializers.CharField(
        source='get_incident_type_display',
        read_only=True,
    )

    class Meta:
        """Configuración del serializador."""

        model = Incident
        fields = [
            'id',
            'transaction',
            'incident_type',
            'incident_type_display',
            'description',
            'resolved',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_description(self, value):
        """Valida que la descripción tenga al menos 10 caracteres."""
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                'La descripción debe tener al menos 10 caracteres.'
            )
        return value.strip()


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializador del modelo Transaction (lectura).

    Para la creación se utiliza :class:`TransactionCreateSerializer`, que
    expone solo los campos editables por el cliente.
    """

    provider_name = serializers.CharField(source='provider.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    incidents = IncidentSerializer(many=True, read_only=True)

    class Meta:
        """Configuración del serializador."""

        model = Transaction
        fields = [
            'id',
            'reference',
            'external_id',
            'provider',
            'provider_name',
            'amount',
            'currency',
            'status',
            'status_display',
            'description',
            'incidents',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'external_id', 'status', 'status_display',
            'incidents', 'created_at', 'updated_at',
        ]


class TransactionCreateSerializer(serializers.ModelSerializer):
    """
    Serializador para crear transacciones (POST /transactions/).

    Solo permite enviar los campos editables. El estado, la referencia y el
    external_id se asignan en el servicio.
    """

    currency = serializers.CharField(max_length=3)

    class Meta:
        """Configuración del serializador."""

        model = Transaction
        fields = ['provider', 'amount', 'currency', 'description']

    def validate_amount(self, value):
        """Valida que el importe sea estrictamente positivo."""
        if value <= Decimal('0'):
            raise serializers.ValidationError('El importe debe ser mayor que cero.')
        return value

    def validate_currency(self, value):
        """Normaliza y valida la moneda."""
        currency = value.upper().strip()
        if currency not in ALLOWED_CURRENCIES:
            raise serializers.ValidationError(
                f'Moneda no soportada. Permitidas: '
                f'{", ".join(sorted(ALLOWED_CURRENCIES))}.'
            )
        return currency

    def validate_provider(self, value):
        """Verifica que el proveedor esté activo."""
        if not value.is_active:
            raise serializers.ValidationError(
                f'El proveedor "{value.name}" no está activo.'
            )
        return value


class RefundRequestSerializer(serializers.Serializer):
    """Payload de entrada para el endpoint de devolución."""

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text='Importe a devolver. Si se omite, devolución total.',
    )

    def validate_amount(self, value):
        """El importe a devolver debe ser positivo si se proporciona."""
        if value is not None and value <= Decimal('0'):
            raise serializers.ValidationError(
                'El importe de devolución debe ser mayor que cero.'
            )
        return value
