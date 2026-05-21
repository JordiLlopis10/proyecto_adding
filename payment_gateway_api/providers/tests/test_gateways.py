"""
Tests de la pasarela Stripe.

El SDK de Stripe se mockea por completo: los tests nunca llaman a la red.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from providers.gateways import get_gateway
from providers.gateways.exceptions import (
    GatewayConfigurationError,
    GatewayNotImplementedError,
    ProviderInactiveError,
)
from providers.gateways.stripe_gw import StripeGateway
from providers.models import Provider


def _fake_payment_intent(status='requires_payment_method', id_='pi_TEST123'):
    """Crea un dict similar al que devuelve Stripe para un PaymentIntent."""
    return {
        'id': id_,
        'status': status,
        'amount': 4990,
        'currency': 'eur',
        'object': 'payment_intent',
    }


class StripeGatewayTests(TestCase):
    """Tests para :class:`StripeGateway` con el SDK mockeado."""

    def setUp(self):
        """Crea un proveedor Stripe activo y configurado para las pruebas."""
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe',
            api_key='sk_test_xxxxxxxx', is_active=True,
        )
        self.gateway = StripeGateway(self.provider)

    # --- create_charge ---

    @patch('providers.gateways.stripe_gw.stripe.PaymentIntent.create')
    def test_create_charge_returns_pending_status(self, mock_create):
        """Tras crear un PaymentIntent se obtiene un estado mapeado."""
        mock_create.return_value = _fake_payment_intent()
        result = self.gateway.create_charge(Decimal('49.90'), 'EUR', description='Pedido #1')
        self.assertEqual(result.external_id, 'pi_TEST123')
        self.assertEqual(result.status, 'pending')

    @patch('providers.gateways.stripe_gw.stripe.PaymentIntent.create')
    def test_create_charge_converts_to_minor_units(self, mock_create):
        """49.90 EUR se envía como 4990 céntimos."""
        mock_create.return_value = _fake_payment_intent()
        self.gateway.create_charge(Decimal('49.90'), 'EUR')
        args, kwargs = mock_create.call_args
        self.assertEqual(kwargs['amount'], 4990)
        self.assertEqual(kwargs['currency'], 'eur')

    @patch('providers.gateways.stripe_gw.stripe.PaymentIntent.create')
    def test_create_charge_zero_decimal_currency(self, mock_create):
        """En JPY el importe se envía sin convertir a céntimos."""
        mock_create.return_value = _fake_payment_intent()
        self.gateway.create_charge(Decimal('1000'), 'JPY')
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['amount'], 1000)

    # --- capture / refund / cancel / retrieve ---

    @patch('providers.gateways.stripe_gw.stripe.PaymentIntent.capture')
    def test_capture_returns_completed(self, mock_capture):
        """Una captura exitosa devuelve estado 'completed'."""
        mock_capture.return_value = _fake_payment_intent(status='succeeded')
        result = self.gateway.capture('pi_TEST123')
        self.assertEqual(result.status, 'completed')

    @patch('providers.gateways.stripe_gw.stripe.PaymentIntent.retrieve')
    @patch('providers.gateways.stripe_gw.stripe.Refund.create')
    def test_refund_returns_refunded(self, mock_refund, mock_retrieve):
        """Una devolución exitosa devuelve estado 'refunded'."""
        mock_refund.return_value = {'id': 're_TEST'}
        mock_retrieve.return_value = _fake_payment_intent(status='succeeded')
        result = self.gateway.refund('pi_TEST123')
        self.assertEqual(result.status, 'refunded')

    @patch('providers.gateways.stripe_gw.stripe.PaymentIntent.cancel')
    def test_cancel_returns_cancelled(self, mock_cancel):
        """Una cancelación exitosa devuelve estado 'cancelled'."""
        mock_cancel.return_value = _fake_payment_intent(status='canceled')
        result = self.gateway.cancel('pi_TEST123')
        self.assertEqual(result.status, 'cancelled')

    # --- Configuración / registro ---

    def test_missing_api_key_raises_configuration_error(self):
        """Sin clave de API debe lanzar GatewayConfigurationError."""
        provider = Provider.objects.create(
            name='SinClave', code='stripe-2', api_key='', is_active=True,
        )
        with self.settings(STRIPE_API_KEY=''):
            with self.assertRaises(GatewayConfigurationError):
                StripeGateway(provider)


class RegistryTests(TestCase):
    """Tests del registro/factory de pasarelas."""

    def test_get_gateway_returns_stripe_for_stripe_code(self):
        """``get_gateway`` devuelve StripeGateway para code='stripe'."""
        provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        self.assertIsInstance(get_gateway(provider), StripeGateway)

    def test_inactive_provider_raises(self):
        """Un proveedor inactivo no puede obtener gateway."""
        provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
            is_active=False,
        )
        with self.assertRaises(ProviderInactiveError):
            get_gateway(provider)

    def test_unknown_code_raises_not_implemented(self):
        """Un código no registrado lanza GatewayNotImplementedError."""
        provider = Provider.objects.create(
            name='Desconocido', code='unknown-gateway',
            api_key='xxxxxxxxxx',
        )
        with self.assertRaises(GatewayNotImplementedError):
            get_gateway(provider)
