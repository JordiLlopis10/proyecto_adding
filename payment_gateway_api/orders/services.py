"""
Servicio de creación de pedidos con Stripe Checkout (modelo de redirección).

El flujo es:
1. Se crea el :class:`~orders.models.Order` en BD con estado ``pending``.
2. Se crea una ``checkout.Session`` en Stripe con modo ``payment``.
3. Se guarda el ``session_id`` y la ``checkout_url`` en el pedido.
4. El controlador devuelve el pedido al cliente (que redirige al usuario).
"""
import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction as db_transaction

from providers.models import Provider

from .models import Order

logger = logging.getLogger(__name__)

# Monedas sin decimales (Stripe espera el importe sin multiplicar por 100).
ZERO_DECIMAL_CURRENCIES = {
    'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA',
    'PYG', 'RWF', 'UGX', 'VND', 'VUV', 'XAF', 'XOF', 'XPF',
}


def _to_minor_units(amount: Decimal, currency: str) -> int:
    """
    Convierte el importe a la unidad mínima que espera Stripe.

    Args:
        amount: Importe en unidades mayores (ej: 49.90 EUR).
        currency: Código ISO 4217.

    Returns:
        Entero en unidades menores (ej: 4990 céntimos).
    """
    if currency.upper() in ZERO_DECIMAL_CURRENCIES:
        return int(amount)
    return int((amount * 100).to_integral_value())


class OrderService:
    """Servicio para gestionar el ciclo de vida de un pedido."""

    @staticmethod
    @db_transaction.atomic
    def create_order(
        provider: Provider,
        amount: Decimal,
        currency: str,
        description: str = '',
        success_url: str = '',
        cancel_url: str = '',
    ) -> Order:
        """
        Crea un pedido en BD y una Checkout Session en Stripe.

        Args:
            provider: Proveedor Stripe con su ``api_key``.
            amount: Importe.
            currency: Código ISO 4217.
            description: Descripción del pedido (visible en Stripe).
            success_url: URL a la que Stripe redirige tras el pago.
            cancel_url: URL a la que Stripe redirige si el usuario cancela.

        Returns:
            El :class:`Order` creado con ``stripe_session_id`` y
            ``checkout_url`` ya rellenos.

        Raises:
            stripe.error.StripeError: Si Stripe devuelve un error.
        """
        api_key = provider.api_key or settings.STRIPE_API_KEY

        # URLs de retorno: si el llamador no las proporciona se usan
        # los valores configurados en settings.SITE_BASE_URL.
        base_url = settings.SITE_BASE_URL
        success_url = success_url or f'{base_url}/orders/success/?session_id={{CHECKOUT_SESSION_ID}}'
        cancel_url = cancel_url or f'{base_url}/orders/cancel/'

        # Creamos el pedido en BD primero (estado pending).
        order = Order.objects.create(
            provider=provider,
            amount=amount,
            currency=currency,
            description=description,
            status=Order.Status.PENDING,
        )
        logger.info('Order creada en BD: %s', order.reference)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='payment',
                line_items=[{
                    'price_data': {
                        'currency': currency.lower(),
                        'unit_amount': _to_minor_units(amount, currency),
                        'product_data': {
                            'name': description or f'Pedido {order.reference}',
                        },
                    },
                    'quantity': 1,
                }],
                # Stripe sustituirá {CHECKOUT_SESSION_ID} con el ID real.
                success_url=success_url,
                cancel_url=cancel_url,
                # Guardamos la referencia interna para localizarla en el webhook.
                metadata={'order_reference': str(order.reference)},
                api_key=api_key,
            )
        except stripe.error.StripeError as exc:
            # Si Stripe falla, marcamos el pedido como fallido para que quede
            # registrado en el historial (trazabilidad).
            order.status = Order.Status.FAILED
            order.save(update_fields=['status', 'updated_at'])
            logger.error('Error al crear Checkout Session: %s', exc)
            raise

        # Guardamos el session_id y la URL de checkout.
        order.stripe_session_id = session['id']
        order.checkout_url = session['url']
        order.save(update_fields=['stripe_session_id', 'checkout_url', 'updated_at'])

        logger.info(
            'Checkout Session creada: %s → %s',
            order.reference, session['id'],
        )
        return order
