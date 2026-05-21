"""Tests del webhook de Stripe."""
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from providers.models import Provider
from transactions.models import Incident, Transaction


@override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
class StripeWebhookTests(APITestCase):
    """Tests del endpoint /api/v1/webhooks/stripe/."""

    def setUp(self):
        """Crea un proveedor y una transacción pendiente con external_id."""
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        self.tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('25'), currency='EUR',
            external_id='pi_TEST_WH', status=Transaction.Status.PENDING,
        )

    @patch('transactions.webhooks.stripe.Webhook.construct_event')
    def test_payment_succeeded_marks_completed(self, mock_construct):
        """payment_intent.succeeded marca la transacción como completed."""
        mock_construct.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_TEST_WH', 'status': 'succeeded'}},
        }
        response = self.client.post(
            '/api/v1/webhooks/stripe/',
            data=b'{}', content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=0,v1=fake',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.Status.COMPLETED)

    @patch('transactions.webhooks.stripe.Webhook.construct_event')
    def test_payment_failed_creates_incident(self, mock_construct):
        """payment_intent.payment_failed registra una incidencia 'unpaid'."""
        mock_construct.return_value = {
            'type': 'payment_intent.payment_failed',
            'data': {'object': {
                'id': 'pi_TEST_WH',
                'last_payment_error': {'message': 'tarjeta declinada'},
            }},
        }
        response = self.client.post(
            '/api/v1/webhooks/stripe/',
            data=b'{}', content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=0,v1=fake',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, Transaction.Status.FAILED)
        self.assertEqual(
            Incident.objects.filter(transaction=self.tx).count(), 1,
        )

    @patch('transactions.webhooks.stripe.Webhook.construct_event')
    def test_unknown_transaction_returns_200(self, mock_construct):
        """Un webhook para una tx desconocida no es un error (200)."""
        mock_construct.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_NO_EXISTE', 'status': 'succeeded'}},
        }
        response = self.client.post(
            '/api/v1/webhooks/stripe/',
            data=b'{}', content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=0,v1=fake',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_signature_returns_400(self):
        """Firma inválida devuelve 400."""
        response = self.client.post(
            '/api/v1/webhooks/stripe/',
            data=b'{}', content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
