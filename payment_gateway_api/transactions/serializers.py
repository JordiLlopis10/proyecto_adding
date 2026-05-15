"""
Serializadores para la app transactions.

Convierten instancias de :class:`Transaction` e :class:`Incident` a JSON
y aplican las validaciones de negocio iniciales requeridas por el Hito 2.
"""
from decimal import Decimal

from rest_framework import serializers

from .models import Incident, Transaction


# Conjunto de monedas aceptadas en el sistema (puede ampliarse en el futuro).
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
        """
        Valida que la descripción tenga contenido suficiente.

        Args:
            value: Descripción de la incidencia.

        Returns:
            La descripción validada.

        Raises:
            serializers.ValidationError: Si la descripción es muy corta.
        """
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                'La descripción debe tener al menos 10 caracteres.'
            )
        return value.strip()


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializador del modelo Transaction.

    Expone los datos de la transacción y permite consultar las incidencias
    asociadas en modo lectura. Aplica validaciones de importe, moneda y
    estado del proveedor.
    """

    provider_name = serializers.CharField(
        source='provider.name',
        read_only=True,
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
    )
    # Se redefine el campo currency sin el RegexValidator del modelo
    # para que la normalización a mayúsculas se aplique antes de validar.
    currency = serializers.CharField(max_length=3)
    incidents = IncidentSerializer(many=True, read_only=True)

    class Meta:
        """Configuración del serializador."""

        model = Transaction
        fields = [
            'id',
            'reference',
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
        read_only_fields = ['id', 'reference', 'created_at', 'updated_at']

    def validate_amount(self, value):
        """
        Valida que el importe sea estrictamente positivo.

        Args:
            value: Importe de la transacción.

        Returns:
            El importe validado.

        Raises:
            serializers.ValidationError: Si el importe es menor o igual a 0.
        """
        if value <= Decimal('0'):
            raise serializers.ValidationError(
                'El importe debe ser mayor que cero.'
            )
        return value

    def validate_currency(self, value):
        """
        Valida que la moneda esté en el conjunto de monedas aceptadas.

        Args:
            value: Código de moneda ISO 4217.

        Returns:
            La moneda en mayúsculas.

        Raises:
            serializers.ValidationError: Si la moneda no está soportada.
        """
        currency = value.upper().strip()
        if currency not in ALLOWED_CURRENCIES:
            raise serializers.ValidationError(
                f'Moneda no soportada. Permitidas: '
                f'{", ".join(sorted(ALLOWED_CURRENCIES))}.'
            )
        return currency

    def validate_provider(self, value):
        """
        Valida que el proveedor esté activo.

        No se permite crear transacciones contra proveedores inactivos.

        Args:
            value: Instancia del proveedor.

        Returns:
            El proveedor validado.

        Raises:
            serializers.ValidationError: Si el proveedor está inactivo.
        """
        if not value.is_active:
            raise serializers.ValidationError(
                f'El proveedor "{value.name}" no está activo.'
            )
        return value
