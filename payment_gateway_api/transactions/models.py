"""
Modelos para la app transactions.

Define dos modelos:

* :class:`Transaction`: representa un intento de pago a través de un proveedor.
* :class:`Incident`: representa una incidencia técnica o financiera asociada
  a una transacción (impago, error de conexión, devolución, etc.).
"""
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from providers.models import Provider


class Transaction(models.Model):
    """
    Representa un intento de pago realizado a través de una pasarela.

    Cada transacción está vinculada a un :class:`Provider` y guarda
    el importe, la moneda (código ISO 4217), una referencia única y
    el estado actual del pago.

    Attributes:
        reference: Identificador único de la transacción (UUID).
        provider: Proveedor a través del cual se procesa el pago.
        amount: Importe de la transacción (siempre positivo).
        currency: Código de moneda ISO 4217 (ej: ``EUR``, ``USD``).
        status: Estado actual del pago.
        description: Descripción opcional del pago.
        created_at: Fecha de creación.
        updated_at: Fecha de la última modificación.
    """

    class Status(models.TextChoices):
        """Estados posibles de una transacción."""

        PENDING = 'pending', 'Pendiente'
        COMPLETED = 'completed', 'Completada'
        FAILED = 'failed', 'Fallida'
        REFUNDED = 'refunded', 'Devuelta'

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='Referencia',
        help_text='Identificador único de la transacción.',
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name='Proveedor',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Importe',
        help_text='Importe de la transacción (debe ser positivo).',
    )
    currency = models.CharField(
        max_length=3,
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{3}$',
                message='La moneda debe ser un código ISO 4217 de 3 letras '
                        'en mayúsculas (ej: EUR, USD).',
            ),
        ],
        verbose_name='Moneda',
        help_text='Código ISO 4217 (EUR, USD, GBP...).',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Estado',
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Descripción',
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
        """Metadatos del modelo Transaction."""

        verbose_name = 'Transacción'
        verbose_name_plural = 'Transacciones'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        """Representación legible de la transacción."""
        return f'{self.reference} - {self.amount} {self.currency} ({self.status})'


class Incident(models.Model):
    """
    Representa una incidencia asociada a una transacción.

    Permite documentar problemas concretos detectados durante el procesado
    del pago, tales como impagos, errores de conexión con la pasarela o
    devoluciones solicitadas por el cliente.

    Attributes:
        transaction: Transacción afectada por la incidencia.
        incident_type: Tipo de incidencia (impago, error de conexión, devolución).
        description: Descripción detallada de la incidencia.
        resolved: Indica si la incidencia ha sido resuelta.
        created_at: Fecha de registro.
    """

    class IncidentType(models.TextChoices):
        """Tipos de incidencia previstos."""

        UNPAID = 'unpaid', 'Impago'
        CONNECTION_ERROR = 'connection_error', 'Error de conexión'
        REFUND = 'refund', 'Devolución'
        OTHER = 'other', 'Otro'

    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='incidents',
        verbose_name='Transacción',
    )
    incident_type = models.CharField(
        max_length=30,
        choices=IncidentType.choices,
        verbose_name='Tipo de incidencia',
    )
    description = models.TextField(
        verbose_name='Descripción',
        help_text='Detalle de la incidencia detectada.',
    )
    resolved = models.BooleanField(
        default=False,
        verbose_name='Resuelta',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de registro',
    )

    class Meta:
        """Metadatos del modelo Incident."""

        verbose_name = 'Incidencia'
        verbose_name_plural = 'Incidencias'
        ordering = ['-created_at']

    def __str__(self):
        """Representación legible de la incidencia."""
        return f'{self.get_incident_type_display()} - Tx {self.transaction.reference}'
