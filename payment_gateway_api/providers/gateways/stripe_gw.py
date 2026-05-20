"""
Implementación de la pasarela de pago Stripe.

Utiliza el SDK oficial ``stripe`` (https://github.com/stripe/stripe-python)
para comunicarse con la API. Todos los importes se convierten a la unidad
mínima de la moneda (céntimos para EUR/USD, etc.) antes de enviarse.
"""
import logging
from decimal import Decimal
from typing import Optional

import stripe
from django.conf import settings

from .base import ChargeResult, PaymentGateway
from .exceptions import (
    GatewayConfigurationError,
    GatewayError,
    GatewayUnavailableError,
)

logger = logging.getLogger(__name__)

# Monedas "zero-decimal" según Stripe: el importe se envía sin conversión.
# https://stripe.com/docs/currencies#zero-decimal
ZERO_DECIMAL_CURRENCIES = {
    'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA',
    'PYG', 'RWF', 'UGX', 'VND', 'VUV', 'XAF', 'XOF', 'XPF',
}

# Mapeo de estados de PaymentIntent de Stripe -> máquina de estados interna.
# https://stripe.com/docs/payments/intents#intent-statuses
STATUS_MAP = {
    'requires_payment_method': 'pending',
    'requires_confirmation': 'pending',
    'requires_action': 'pending',
    'processing': 'processing',
    'requires_capture': 'processing',
    'succeeded': 'completed',
    'canceled': 'cancelled',
}


class StripeGateway(PaymentGateway):
    """Pasarela de pago para Stripe."""

    code = 'stripe'

    def __init__(self, provider):
        """Configura el SDK de Stripe con la clave del proveedor."""
        super().__init__(provider)
        # Prioridad: api_key guardada en el modelo Provider. Si está vacía,
        # se cae a la variable de entorno ``STRIPE_API_KEY`` de Django.
        api_key = provider.api_key or settings.STRIPE_API_KEY
        if not api_key:
            raise GatewayConfigurationError(
                'No hay clave de API de Stripe configurada para este proveedor.'
            )
        # Se asigna la clave por instancia para soportar múltiples cuentas Stripe.
        self._api_key = api_key

    # --- Utilidades internas ---

    @staticmethod
    def _to_minor_units(amount: Decimal, currency: str) -> int:
        """
        Convierte un ``Decimal`` al entero en la unidad mínima de la moneda.

        Ej.: 12.34 EUR -> 1234 (céntimos); 1000 JPY -> 1000 (sin decimales).
        """
        if currency.upper() in ZERO_DECIMAL_CURRENCIES:
            return int(amount)
        return int((amount * 100).to_integral_value())

    @staticmethod
    def _from_minor_units(amount: int, currency: str) -> Decimal:
        """Operación inversa de :meth:`_to_minor_units`."""
        if currency.upper() in ZERO_DECIMAL_CURRENCIES:
            return Decimal(amount)
        return Decimal(amount) / Decimal(100)

    def _build_result(self, intent) -> ChargeResult:
        """Convierte un PaymentIntent de Stripe en un ``ChargeResult``."""
        return ChargeResult(
            external_id=intent['id'],
            status=STATUS_MAP.get(intent.get('status'), 'pending'),
            raw_response=dict(intent),
        )

    # --- Implementación de la interfaz PaymentGateway ---

    def create_charge(
        self,
        amount: Decimal,
        currency: str,
        description: str = '',
        metadata: Optional[dict] = None,
    ) -> ChargeResult:
        """Crea un PaymentIntent en Stripe."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=self._to_minor_units(amount, currency),
                currency=currency.lower(),
                description=description or None,
                metadata=metadata or {},
                # Configuración de captura automática (similar a Charges API).
                automatic_payment_methods={'enabled': True, 'allow_redirects': 'never'},
                api_key=self._api_key,
            )
        except stripe.error.AuthenticationError as exc:
            raise GatewayConfigurationError(
                f'Clave de API de Stripe inválida: {exc}'
            ) from exc
        except stripe.error.APIConnectionError as exc:
            raise GatewayUnavailableError(
                f'No se ha podido conectar con Stripe: {exc}'
            ) from exc
        except stripe.error.StripeError as exc:
            raise GatewayError(f'Error de Stripe: {exc}') from exc

        logger.info('Stripe PaymentIntent creado: %s', intent['id'])
        return self._build_result(intent)

    def capture(self, external_id: str) -> ChargeResult:
        """Captura un PaymentIntent en estado ``requires_capture``."""
        try:
            intent = stripe.PaymentIntent.capture(external_id, api_key=self._api_key)
        except stripe.error.StripeError as exc:
            raise GatewayError(f'Error al capturar el pago: {exc}') from exc
        return self._build_result(intent)

    def refund(
        self,
        external_id: str,
        amount: Optional[Decimal] = None,
    ) -> ChargeResult:
        """
        Crea una devolución sobre un PaymentIntent.

        Stripe devuelve un objeto ``Refund``, pero para mantener una
        respuesta consistente recargamos el PaymentIntent tras la devolución.
        """
        try:
            params = {'payment_intent': external_id, 'api_key': self._api_key}
            if amount is not None:
                # Necesitamos saber la moneda para convertir a unidades mínimas.
                intent = stripe.PaymentIntent.retrieve(external_id, api_key=self._api_key)
                params['amount'] = self._to_minor_units(amount, intent['currency'])
            stripe.Refund.create(**params)
            intent = stripe.PaymentIntent.retrieve(external_id, api_key=self._api_key)
        except stripe.error.StripeError as exc:
            raise GatewayError(f'Error al solicitar la devolución: {exc}') from exc

        result = self._build_result(intent)
        # Una vez creada la Refund, marcamos el estado como ``refunded``
        # aunque el PaymentIntent siga apareciendo como ``succeeded``.
        result.status = 'refunded'
        return result

    def cancel(self, external_id: str) -> ChargeResult:
        """Cancela un PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.cancel(external_id, api_key=self._api_key)
        except stripe.error.StripeError as exc:
            raise GatewayError(f'Error al cancelar el pago: {exc}') from exc
        return self._build_result(intent)

    def retrieve(self, external_id: str) -> ChargeResult:
        """Recupera el estado actual de un PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.retrieve(external_id, api_key=self._api_key)
        except stripe.error.StripeError as exc:
            raise GatewayError(f'Error al recuperar el pago: {exc}') from exc
        return self._build_result(intent)
