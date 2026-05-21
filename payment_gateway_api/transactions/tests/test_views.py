"""
Tests de integración de los endpoints de transacciones.

Verifican el flujo completo HTTP -> view -> service -> gateway (mockeada).
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from providers.gateways.base import ChargeResult
from providers.models import Provider
from transactions.models import Incident, Transaction


class TransactionEndpointTests(APITestCase):
    """Tests del endpoint /api/v1/transactions/."""

    def setUp(self):
        """Crea usuario autenticado y proveedor Stripe."""
        self.user = User.objects.create_user(username='bob', password='bob12345')
        self.client.force_authenticate(self.user)
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )

    @patch('providers.gateways.stripe_gw.StripeGateway.create_charge')
    def test_create_transaction_returns_201(self, mock_create):
        """POST /transactions/ crea la transacción y llama a la pasarela."""
        mock_create.return_value = ChargeResult(
            external_id='pi_NEW', status='pending', raw_response={'id': 'pi_NEW'},
        )
        response = self.client.post('/api/v1/transactions/', {
            'provider': self.provider.id,
            'amount': '49.90',
            'currency': 'EUR',
            'description': 'Pedido #1001',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['external_id'], 'pi_NEW')
        self.assertEqual(response.data['status'], 'pending')
        mock_create.assert_called_once()

    def test_create_with_negative_amount_returns_400(self):
        """Importe negativo se rechaza con 400."""
        response = self.client.post('/api/v1/transactions/', {
            'provider': self.provider.id, 'amount': '-1', 'currency': 'EUR',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_inactive_provider_returns_400(self):
        """Proveedor inactivo se rechaza en validación."""
        self.provider.is_active = False
        self.provider.save()
        response = self.client.post('/api/v1/transactions/', {
            'provider': self.provider.id, 'amount': '10', 'currency': 'EUR',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('providers.gateways.stripe_gw.StripeGateway.refund')
    def test_refund_action(self, mock_refund):
        """POST /transactions/{id}/refund/ procesa la devolución."""
        mock_refund.return_value = ChargeResult(
            external_id='pi_X', status='refunded', raw_response={},
        )
        tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('50'), currency='EUR',
            external_id='pi_X', status=Transaction.Status.COMPLETED,
        )
        response = self.client.post(f'/api/v1/transactions/{tx.id}/refund/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'refunded')

    @patch('providers.gateways.stripe_gw.StripeGateway.refund')
    def test_refund_pending_returns_409(self, mock_refund):
        """No se puede devolver una transacción que no esté completada."""
        tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('50'), currency='EUR',
            external_id='pi_Y', status=Transaction.Status.PENDING,
        )
        response = self.client.post(f'/api/v1/transactions/{tx.id}/refund/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        mock_refund.assert_not_called()

    def test_filter_by_status(self):
        """Se puede filtrar el historial por estado."""
        Transaction.objects.create(
            provider=self.provider, amount=Decimal('1'), currency='EUR',
            status=Transaction.Status.COMPLETED,
        )
        Transaction.objects.create(
            provider=self.provider, amount=Decimal('2'), currency='EUR',
            status=Transaction.Status.PENDING,
        )
        response = self.client.get('/api/v1/transactions/?status=completed')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_by_provider_code(self):
        """Se puede filtrar por código de proveedor."""
        Transaction.objects.create(
            provider=self.provider, amount=Decimal('1'), currency='EUR',
        )
        response = self.client.get('/api/v1/transactions/?provider_code=stripe')
        self.assertEqual(response.data['count'], 1)

    def test_add_incident_to_transaction(self):
        """POST /transactions/{id}/incidents/ registra una incidencia."""
        tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('10'), currency='EUR',
        )
        response = self.client.post(
            f'/api/v1/transactions/{tx.id}/incidents/',
            {
                'incident_type': 'unpaid',
                'description': 'El cliente no ha realizado el pago.',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Incident.objects.count(), 1)

    def test_anonymous_user_is_rejected(self):
        """Sin autenticación se devuelve 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/transactions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
