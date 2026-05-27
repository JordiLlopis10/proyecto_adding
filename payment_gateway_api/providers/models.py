"""
Modelos para la app providers.

Define el modelo Provider, que representa una pasarela de pago
(Stripe, PayPal, Redsys, etc.) con sus parámetros de configuración.
"""
from django.db import models


class Provider(models.Model):
    """
    Representa una pasarela de pago integrada en el sistema.

    Cada proveedor (Stripe, PayPal, Redsys...) almacena su clave de API,
    el entorno en el que opera (pruebas o producción) y un indicador
    de actividad que permite habilitarlo o deshabilitarlo sin necesidad
    de eliminar el registro.

    Attributes:
        name: Nombre comercial del proveedor.
        code: Identificador único en formato slug (ej: ``stripe``).
        api_key: Clave de API para autenticarse contra el proveedor.
        environment: Entorno de trabajo (``sandbox`` o ``production``).
        is_active: Indica si el proveedor está disponible para operar.
        created_at: Fecha de alta del registro.
        updated_at: Fecha de la última modificación.
    """

    class Environment(models.TextChoices):
        """Entornos posibles de un proveedor de pago."""

        SANDBOX = 'sandbox', 'Pruebas (sandbox)'
        PRODUCTION = 'production', 'Producción'

    name = models.CharField(
        max_length=100,
        verbose_name='Nombre',
        help_text='Nombre comercial del proveedor (ej: Stripe, PayPal).',
    )
    code = models.SlugField(
        max_length=50,
        unique=True,
        verbose_name='Código',
        help_text='Identificador único en formato slug (ej: stripe).',
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Clave de API',
        help_text=(
            'Clave de API proporcionada por el proveedor. '
            'Si se deja vacía, se usará la del entorno (STRIPE_API_KEY).'
        ),
    )
    environment = models.CharField(
        max_length=20,
        choices=Environment.choices,
        default=Environment.SANDBOX,
        verbose_name='Entorno',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Indica si el proveedor está disponible para procesar pagos.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creación',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Fecha de actualización',
    )

    class Meta:
        """Metadatos del modelo Provider."""

        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']

    def __str__(self):
        """Devuelve una representación legible del proveedor."""
        return f'{self.name} ({self.get_environment_display()})'
