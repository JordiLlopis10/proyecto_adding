"""
Serializadores para la app providers.

Convierten instancias de :class:`Provider` a JSON (y viceversa) y aplican
las validaciones de negocio iniciales requeridas por el Hito 2.
"""
from rest_framework import serializers

from .models import Provider


class ProviderSerializer(serializers.ModelSerializer):
    """
    Serializador del modelo Provider.

    Expone los campos de un proveedor de pago y oculta la clave de API
    en las respuestas (``write_only``) por motivos de seguridad. Incluye
    validaciones para asegurar nombres y códigos correctos.
    """

    class Meta:
        """Configuración del serializador."""

        model = Provider
        fields = [
            'id',
            'name',
            'code',
            'api_key',
            'environment',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            # La clave de API nunca se devuelve en las respuestas.
            'api_key': {'write_only': True},
        }

    def validate_name(self, value):
        """
        Valida que el nombre del proveedor tenga al menos 2 caracteres.

        Args:
            value: Nombre del proveedor.

        Returns:
            El nombre validado y sin espacios redundantes.

        Raises:
            serializers.ValidationError: Si el nombre es demasiado corto.
        """
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(
                'El nombre debe tener al menos 2 caracteres.'
            )
        return cleaned

    def validate_code(self, value):
        """
        Valida y normaliza el código del proveedor.

        Convierte el código a minúsculas para asegurar la unicidad y
        consistencia (``Stripe`` y ``stripe`` serían el mismo proveedor).

        Args:
            value: Código del proveedor.

        Returns:
            El código en minúsculas.
        """
        return value.lower().strip()

    def validate_api_key(self, value):
        """
        Valida que la clave de API no esté vacía y tenga longitud mínima.

        Args:
            value: Clave de API.

        Returns:
            La clave de API validada.

        Raises:
            serializers.ValidationError: Si la clave es demasiado corta.
        """
        if len(value.strip()) < 8:
            raise serializers.ValidationError(
                'La clave de API debe tener al menos 8 caracteres.'
            )
        return value.strip()
