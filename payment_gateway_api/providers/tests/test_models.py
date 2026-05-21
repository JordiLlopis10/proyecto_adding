"""Tests para los modelos y serializadores de la app providers."""
from django.test import TestCase

from providers.models import Provider
from providers.serializers import ProviderSerializer


class ProviderModelTests(TestCase):
    """Tests sobre el modelo Provider."""

    def test_str_includes_environment(self):
        """El __str__ debe incluir nombre y entorno."""
        provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        self.assertIn('Stripe', str(provider))
        self.assertIn('sandbox', str(provider).lower())

    def test_code_must_be_unique(self):
        """No se permiten dos proveedores con el mismo código."""
        Provider.objects.create(name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx')
        with self.assertRaises(Exception):
            Provider.objects.create(name='Otro', code='stripe', api_key='sk_test_yyyyyyyy')


class ProviderSerializerTests(TestCase):
    """Tests de validación del serializador."""

    def test_code_normalized_to_lowercase(self):
        """El código se normaliza a minúsculas."""
        s = ProviderSerializer(data={
            'name': 'Stripe', 'code': 'STRIPE',
            'api_key': 'sk_test_xxxxxxxx', 'environment': 'sandbox',
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['code'], 'stripe')

    def test_short_api_key_is_rejected(self):
        """Las claves de menos de 8 caracteres no son válidas."""
        s = ProviderSerializer(data={
            'name': 'Stripe', 'code': 'stripe',
            'api_key': 'short', 'environment': 'sandbox',
        })
        self.assertFalse(s.is_valid())
        self.assertIn('api_key', s.errors)

    def test_short_name_is_rejected(self):
        """Nombres de menos de 2 caracteres no son válidos."""
        s = ProviderSerializer(data={
            'name': 'A', 'code': 'stripe',
            'api_key': 'sk_test_xxxxxxxx', 'environment': 'sandbox',
        })
        self.assertFalse(s.is_valid())
        self.assertIn('name', s.errors)

    def test_api_key_is_write_only(self):
        """La API key no debe aparecer en la representación serializada."""
        provider = Provider.objects.create(
            name='Stripe', code='stripe', api_key='sk_test_xxxxxxxx',
        )
        data = ProviderSerializer(provider).data
        self.assertNotIn('api_key', data)
