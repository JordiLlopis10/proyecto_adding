"""Tests del modelo Transaction y la máquina de estados."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from providers.models import Provider
from transactions.models import Incident, Transaction


class TransactionStateMachineTests(TestCase):
    """Tests sobre la máquina de estados de Transaction."""

    def setUp(self):
        """Crea un proveedor activo y una transacción pendiente."""
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        self.tx = Transaction.objects.create(
            provider=self.provider, amount=Decimal('50.00'), currency='EUR',
        )

    def test_pending_can_go_to_completed(self):
        """pending → completed es una transición válida."""
        self.assertTrue(self.tx.can_transition_to(Transaction.Status.COMPLETED))

    def test_completed_can_go_to_refunded(self):
        """completed → refunded es válida."""
        self.tx.transition_to(Transaction.Status.COMPLETED)
        self.assertTrue(self.tx.can_transition_to(Transaction.Status.REFUNDED))

    def test_completed_cannot_go_back_to_pending(self):
        """No se puede volver de completed a pending."""
        self.tx.transition_to(Transaction.Status.COMPLETED)
        self.assertFalse(self.tx.can_transition_to(Transaction.Status.PENDING))

    def test_invalid_transition_raises(self):
        """Una transición ilegal lanza ValidationError."""
        self.tx.transition_to(Transaction.Status.FAILED)
        with self.assertRaises(ValidationError):
            self.tx.transition_to(Transaction.Status.COMPLETED)

    def test_refunded_is_terminal(self):
        """Una transacción devuelta no admite más transiciones."""
        self.tx.transition_to(Transaction.Status.COMPLETED)
        self.tx.transition_to(Transaction.Status.REFUNDED)
        self.assertTrue(self.tx.is_terminal)

    def test_can_be_refunded_only_when_completed(self):
        """can_be_refunded solo es True para transacciones completadas."""
        self.assertFalse(self.tx.can_be_refunded)
        self.tx.transition_to(Transaction.Status.COMPLETED)
        self.assertTrue(self.tx.can_be_refunded)


class IncidentModelTests(TestCase):
    """Tests del modelo Incident."""

    def test_incident_cascades_on_transaction_delete(self):
        """Al borrar la transacción se borran sus incidencias (CASCADE)."""
        provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        tx = Transaction.objects.create(
            provider=provider, amount=Decimal('10.00'), currency='EUR',
        )
        Incident.objects.create(
            transaction=tx, incident_type=Incident.IncidentType.UNPAID,
            description='Pago impagado por el cliente.',
        )
        tx.delete()
        self.assertEqual(Incident.objects.count(), 0)
