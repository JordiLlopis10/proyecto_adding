"""
Tests de la capa de servicios.

Mockean la pasarela para verificar la orquestación: estado de la
transacción, persistencia y creación automática de incidencias.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from providers.gateways.base import ChargeResult
from providers.gateways.exceptions import (
    GatewayError,
    InvalidTransitionError,
)
from providers.models import Provider
from transactions.models import Incident, Transaction
from transactions.services import TransactionService


class TransactionServiceTests(TestCase):
    """Tests de :class:`TransactionService`."""

    def setUp(self):
        """Crea un proveedor Stripe activo."""
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe',
            api_key='sk_test_xxxxxxxx', is_active=True,
        )

    @patch('providers.gateways.stripe_gw.StripeGateway.create_charge')
    def test_create_charge_persists_transaction(self, mock_create):
        """Al crear un cargo se persiste una transacción con external_id."""
        mock_create.return_value = ChargeResult(
            external_id='pi_TEST1', status='pending',
            raw_response={'id': 'pi_TEST1'},
        )
        tx = TransactionService.create_charge(
            provider=self.provider, amount=Decimal('100'), currency='EUR',
            description='Test',
        )
        self.assertEqual(tx.external_id, 'pi_TEST1')
        self.assertEqual(tx.status, Transaction.Status.PENDING)
        self.assertEqual(Transaction.objects.count(), 1)

    @patch('providers.gateways.stripe_gw.StripeGateway.create_charge')
    def test_create_charge_failure_records_incident(self, mock_create):
        """Si la pasarela falla se crea un registro y una incidencia."""
        mock_create.side_effect = GatewayError('Stripe caído')

        with self.assertRaises(GatewayError):
            TransactionService.create_charge(
                provider=self.provider, amount=Decimal('100'), currency='EUR',
            )

        # La transacción se persiste con estado failed.
        tx = Transaction.objects.get()
        self.assertEqual(tx.status, Transaction.Status.FAILED)
        # Se ha creado una incidencia de tipo connection_error.
        incident = Incident.objects.get()
        self.assertEqual(incident.incident_type, Incident.IncidentType.CONNECTION_ERROR)

    @patch('providers.gateways.stripe_gw.StripeGateway.refund')
    def test_refund_creates_incident_and_updates_status(self, mock_refund):
        """La devolución actualiza el estado y registra una incidencia."""
        mock_refund.return_value = ChargeResult(
            external_id='pi_TEST1', status='refunded', raw_response={},
        )
        tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('50'), currency='EUR',
            external_id='pi_TEST1', status=Transaction.Status.COMPLETED,
        )
        tx = TransactionService.refund(tx)
        self.assertEqual(tx.status, Transaction.Status.REFUNDED)
        self.assertEqual(Incident.objects.filter(transaction=tx).count(), 1)
        incident = Incident.objects.get(transaction=tx)
        self.assertEqual(incident.incident_type, Incident.IncidentType.REFUND)

    def test_refund_pending_transaction_raises(self):
        """Solo se pueden devolver transacciones completadas."""
        tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('50'), currency='EUR',
            status=Transaction.Status.PENDING,
        )
        with self.assertRaises(InvalidTransitionError):
            TransactionService.refund(tx)

    @patch('providers.gateways.stripe_gw.StripeGateway.cancel')
    def test_cancel_pending_transaction(self, mock_cancel):
        """Las transacciones pendientes se pueden cancelar."""
        mock_cancel.return_value = ChargeResult(
            external_id='pi_TEST1', status='cancelled', raw_response={},
        )
        tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('50'), currency='EUR',
            external_id='pi_TEST1', status=Transaction.Status.PENDING,
        )
        tx = TransactionService.cancel(tx)
        self.assertEqual(tx.status, Transaction.Status.CANCELLED)
