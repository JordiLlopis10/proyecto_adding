"""Serializadores para la app orders."""
from decimal import Decimal

from rest_framework import serializers

from .models import Order

ALLOWED_CURRENCIES = {'EUR', 'USD', 'GBP', 'JPY', 'CHF', 'MXN', 'ARS'}


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializador de entrada para ``POST /orders/create``.

    El cliente solo envía: proveedor, importe, moneda y descripción.
    El resto (estado, session_id, checkout_url) los asigna el servicio.
    """

    currency = serializers.CharField(max_length=3, default='EUR')

    class Meta:
        """Configuración del serializador."""

        model = Order
        fields = ['provider', 'amount', 'currency', 'description']

    def validate_amount(self, value):
        """Stripe exige un mínimo de 0.50 en cualquier moneda."""
        if value < Decimal('0.50'):
            raise serializers.ValidationError(
                'El importe mínimo es 0.50 (límite de Stripe Checkout).'
            )
        return value

    def validate_currency(self, value):
        """Normaliza y valida el código de moneda."""
        currency = value.upper().strip()
        if currency not in ALLOWED_CURRENCIES:
            raise serializers.ValidationError(
                f'Moneda no soportada. Permitidas: '
                f'{", ".join(sorted(ALLOWED_CURRENCIES))}.'
            )
        return currency

    def validate_provider(self, value):
        """Solo se aceptan proveedores Stripe activos."""
        if not value.is_active:
            raise serializers.ValidationError(
                f'El proveedor "{value.name}" no está activo.'
            )
        if value.code != 'stripe':
            raise serializers.ValidationError(
                'El modelo de redirección solo está disponible para Stripe.'
            )
        return value


class OrderStatusSerializer(serializers.ModelSerializer):
    """
    Serializador de salida para ``GET /orders/:id/status``.

    Devuelve solo los campos relevantes para conocer el estado del pedido.
    No expone el checkout_url (ya no sirve de nada una vez creado el pedido).
    """

    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        """Configuración del serializador."""

        model = Order
        fields = [
            'id',
            'reference',
            'amount',
            'currency',
            'description',
            'status',
            'status_display',
            'stripe_payment_intent',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class OrderCreateResponseSerializer(serializers.ModelSerializer):
    """
    Serializador de salida para la respuesta de ``POST /orders/create``.

    Incluye el ``checkout_url`` para que el cliente sepa a dónde redirigir.
    """

    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        """Configuración del serializador."""

        model = Order
        fields = [
            'id',
            'reference',
            'amount',
            'currency',
            'description',
            'status',
            'status_display',
            'checkout_url',
            'created_at',
        ]
        read_only_fields = fields
