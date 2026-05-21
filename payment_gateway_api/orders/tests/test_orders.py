"""
Tests para la app orders.

Cubren el flujo completo de redirección:
1. POST /orders/create → crea Order + Checkout Session (mockeada).
2. POST /payments/webhook → actualiza estado con eventos de Stripe.
3. GET /orders/{id}/status → devuelve el estado actual.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order
from providers.models import Provider


def _mock_session(session_id='cs_test_ABC', url='https://checkout.stripe.com/pay/cs_test_ABC'):
    """Devuelve un dict que simula una Stripe Checkout Session."""
    return MagicMock(**{
        '__getitem__.side_effect': lambda k: {
            'id': session_id,
            'url': url,
            'payment_intent': 'pi_TEST_123',
        }[k],
        'get.side_effect': lambda k, d=None: {
            'id': session_id,
            'url': url,
            'payment_intent': 'pi_TEST_123',
        }.get(k, d),
    })


class OrderCreateViewTests(APITestCase):
    """Tests del endpoint POST /api/v1/orders/create."""

    def setUp(self):
        """Crea un usuario autenticado y un proveedor Stripe activo."""
        self.user = User.objects.create_user(username='tester', password='pass1234')
        self.client.force_authenticate(self.user)
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )

    @patch('orders.services.stripe.checkout.Session.create')
    def test_create_order_returns_201_and_checkout_url(self, mock_create):
        """Un pedido válido devuelve 201 con la checkout_url de Stripe."""
        mock_create.return_value = _mock_session()
        response = self.client.post('/api/v1/orders/create', {
            'provider': self.provider.id,
            'amount': '49.90',
            'currency': 'EUR',
            'description': 'Pedido de prueba',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn('checkout_url', response.data)
        self.assertEqual(response.data['checkout_url'], 'https://checkout.stripe.com/pay/cs_test_ABC')
        self.assertEqual(response.data['status'], 'pending')
        mock_create.assert_called_once()

    @patch('orders.services.stripe.checkout.Session.create')
    def test_create_order_saves_session_id(self, mock_create):
        """El stripe_session_id se guarda en BD para poder localizarlo en el webhook."""
        mock_create.return_value = _mock_session(session_id='cs_test_XYZ')
        self.client.post('/api/v1/orders/create', {
            'provider': self.provider.id,
            'amount': '10.00',
            'currency': 'EUR',
        }, format='json')

        order = Order.objects.get()
        self.assertEqual(order.stripe_session_id, 'cs_test_XYZ')

    def test_amount_below_minimum_is_rejected(self):
        """Importes por debajo de 0.50 no son válidos (límite de Stripe)."""
        response = self.client.post('/api/v1/orders/create', {
            'provider': self.provider.id,
            'amount': '0.10',
            'currency': 'EUR',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', response.data)

    def test_inactive_provider_is_rejected(self):
        """Un proveedor inactivo se rechaza con 400."""
        self.provider.is_active = False
        self.provider.save()
        response = self.client.post('/api/v1/orders/create', {
            'provider': self.provider.id,
            'amount': '20.00',
            'currency': 'EUR',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_stripe_provider_is_rejected(self):
        """El modelo de redirección solo acepta proveedores Stripe."""
        paypal = Provider.objects.create(
            name='PayPal', code='paypal', api_key='pp_test_xxxxxxxx',
        )
        response = self.client.post('/api/v1/orders/create', {
            'provider': paypal.id,
            'amount': '20.00',
            'currency': 'EUR',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_is_rejected(self):
        """Sin autenticar se devuelve 401."""
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/v1/orders/create', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class OrderStatusViewTests(APITestCase):
    """Tests del endpoint GET /api/v1/orders/{id}/status."""

    def setUp(self):
        """Crea usuario, proveedor y un pedido de ejemplo."""
        self.user = User.objects.create_user(username='tester', password='pass1234')
        self.client.force_authenticate(self.user)
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        self.order = Order.objects.create(
            provider=self.provider,
            amount=Decimal('25.00'),
            currency='EUR',
            stripe_session_id='cs_test_STATUS',
            status=Order.Status.PENDING,
        )

    def test_status_returns_200_with_current_status(self):
        """GET /orders/{id}/status devuelve el estado actual del pedido."""
        response = self.client.get(f'/api/v1/orders/{self.order.id}/status')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['id'], self.order.id)

    def test_status_shows_paid_after_webhook(self):
        """Si el pedido está pagado, el endpoint lo refleja."""
        self.order.status = Order.Status.PAID
        self.order.stripe_payment_intent = 'pi_PAID_123'
        self.order.save()

        response = self.client.get(f'/api/v1/orders/{self.order.id}/status')
        self.assertEqual(response.data['status'], 'paid')
        self.assertEqual(response.data['stripe_payment_intent'], 'pi_PAID_123')

    def test_nonexistent_order_returns_404(self):
        """Un ID inexistente devuelve 404."""
        response = self.client.get('/api/v1/orders/9999/status')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(STRIPE_WEBHOOK_SECRET='whsec_test_secret')
class PaymentsWebhookTests(APITestCase):
    """Tests del endpoint POST /api/v1/payments/webhook."""

    def setUp(self):
        """Crea proveedor y pedido pendiente con session_id conocido."""
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        self.order = Order.objects.create(
            provider=self.provider,
            amount=Decimal('49.90'),
            currency='EUR',
            stripe_session_id='cs_test_WEBHOOK',
            status=Order.Status.PENDING,
        )

    @patch('orders.webhooks.stripe.Webhook.construct_event')
    def test_checkout_completed_marks_order_as_paid(self, mock_event):
        """checkout.session.completed actualiza el pedido a 'paid'."""
        mock_event.return_value = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'id': 'cs_test_WEBHOOK',
                'payment_intent': 'pi_PAID_999',
            }},
        }
        response = self.client.post(
            '/api/v1/payments/webhook',
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=0,v1=fake',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.stripe_payment_intent, 'pi_PAID_999')

    @patch('orders.webhooks.stripe.Webhook.construct_event')
    def test_session_expired_marks_order_as_expired(self, mock_event):
        """checkout.session.expired actualiza el pedido a 'expired'."""
        mock_event.return_value = {
            'type': 'checkout.session.expired',
            'data': {'object': {'id': 'cs_test_WEBHOOK'}},
        }
        self.client.post(
            '/api/v1/payments/webhook',
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=0,v1=fake',
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.EXPIRED)

    @patch('orders.webhooks.stripe.Webhook.construct_event')
    def test_duplicate_webhook_is_idempotent(self, mock_event):
        """Un webhook duplicado no cambia un pedido ya pagado."""
        self.order.status = Order.Status.PAID
        self.order.save()

        mock_event.return_value = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'id': 'cs_test_WEBHOOK',
                'payment_intent': 'pi_OTRO',
            }},
        }
        response = self.client.post(
            '/api/v1/payments/webhook',
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='t=0,v1=fake',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # El estado no debe cambiar.
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_invalid_signature_returns_400(self):
        """Firma inválida se rechaza con 400."""
        response = self.client.post(
            '/api/v1/payments/webhook',
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='firma_inventada',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
