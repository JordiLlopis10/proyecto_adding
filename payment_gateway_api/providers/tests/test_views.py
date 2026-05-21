"""Tests de los endpoints REST de la app providers."""
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from providers.models import Provider


class ProviderAPITests(APITestCase):
    """Tests del endpoint /api/v1/providers/."""

    def setUp(self):
        """Crea un usuario admin, uno normal y un proveedor de ejemplo."""
        self.admin = User.objects.create_superuser(
            username='admin', password='admin1234', email='a@a.com',
        )
        self.user = User.objects.create_user(
            username='alice', password='alice1234',
        )
        self.provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )

    def test_list_requires_authentication(self):
        """Sin autenticarse, no se puede listar proveedores."""
        response = self.client.get('/api/v1/providers/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_list(self):
        """Un usuario autenticado puede listar proveedores."""
        self.client.force_authenticate(self.user)
        response = self.client.get('/api/v1/providers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_normal_user_cannot_create(self):
        """Un usuario no admin no puede crear proveedores."""
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/v1/providers/', {
            'name': 'Nuevo', 'code': 'nuevo',
            'api_key': 'xxxxxxxxxx', 'environment': 'sandbox',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create(self):
        """Un admin puede crear proveedores."""
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/providers/', {
            'name': 'PayPal', 'code': 'paypal',
            'api_key': 'PP_TEST_xxxxxxxx', 'environment': 'sandbox',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Provider.objects.count(), 2)

    def test_available_endpoint_lists_gateways(self):
        """/providers/available/ devuelve los códigos registrados."""
        self.client.force_authenticate(self.user)
        response = self.client.get('/api/v1/providers/available/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('stripe', response.data['available_gateways'])

    def test_token_authentication_flow(self):
        """Se puede obtener un token y usarlo para listar."""
        response = self.client.post(reverse('api-token-auth'), {
            'username': 'alice', 'password': 'alice1234',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['token']

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get('/api/v1/providers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
