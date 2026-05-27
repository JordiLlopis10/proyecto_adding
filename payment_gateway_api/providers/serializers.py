"""
Serializadores para la app providers.


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
            # Se permite vacía: en ese caso el sistema cae a settings.STRIPE_API_KEY
            # (variable de entorno), útil para no duplicar credenciales en BD.
            'api_key': {'write_only': True, 'required': False, 'allow_blank': True},
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
        Valida la clave de API.

        Se permite cadena vacía: en ese caso el sistema usará la clave
        configurada en ``settings.STRIPE_API_KEY`` (variable de entorno).
        Si se proporciona, debe tener al menos 8 caracteres.

        Args:
            value: Clave de API.

        Returns:
            La clave de API validada (o cadena vacía).

        Raises:
            serializers.ValidationError: Si la clave es demasiado corta.
        """
        cleaned = value.strip()
        if cleaned and len(cleaned) < 8:
            raise serializers.ValidationError(
                'La clave de API debe tener al menos 8 caracteres '
                '(o dejarse vacía para usar la del entorno).'
            )
        return cleaned
