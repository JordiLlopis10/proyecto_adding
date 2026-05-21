"""
Modelos para la app transactions.

Define dos modelos principales:

* :class:`Transaction`: representa un intento de pago a través de un proveedor.
* :class:`Incident`: representa una incidencia técnica o financiera asociada
  a una transacción (impago, error de conexión, devolución, etc.).
"""
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from providers.models import Provider


class Transaction(models.Model):
    """
    Representa un intento de pago realizado a través de una pasarela.

    Implementa una máquina de estados explícita mediante el método
    :meth:`transition_to`, que valida si la transición solicitada es
    legal antes de aplicarla.

    Attributes:
        reference: Identificador único interno (UUID).
        external_id: Identificador devuelto por la pasarela (ej. PaymentIntent
            de Stripe). Se rellena tras la primera llamada a la pasarela.
        provider: Pasarela utilizada para procesar el pago.
        amount: Importe (estrictamente positivo, hasta 2 decimales).
        currency: Código ISO 4217 de la moneda (3 letras mayúsculas).
        status: Estado actual del pago según la máquina de estados.
        description: Descripción opcional del pago.
        gateway_response: Respuesta cruda más reciente de la pasarela.
        created_at: Fecha de creación.
        updated_at: Fecha de última modificación.
    """

    class Status(models.TextChoices):
        """Estados posibles de una transacción."""

        PENDING = 'pending', 'Pendiente'
        PROCESSING = 'processing', 'Procesando'
        COMPLETED = 'completed', 'Completada'
        FAILED = 'failed', 'Fallida'
        CANCELLED = 'cancelled', 'Cancelada'
        REFUNDED = 'refunded', 'Devuelta'

    # Transiciones válidas: clave = estado origen, valor = estados destino.
    # Los estados COMPLETED -> REFUNDED, y los terminales (FAILED, CANCELLED,
    # REFUNDED) no admiten más cambios.
    VALID_TRANSITIONS = {
        Status.PENDING: {
            Status.PROCESSING,
            Status.COMPLETED,
            Status.FAILED,
            Status.CANCELLED,
        },
        Status.PROCESSING: {
            Status.COMPLETED,
            Status.FAILED,
            Status.CANCELLED,
        },
        Status.COMPLETED: {Status.REFUNDED},
        Status.FAILED: set(),
        Status.CANCELLED: set(),
        Status.REFUNDED: set(),
    }

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='Referencia',
        help_text='Identificador único interno de la transacción.',
    )
    external_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name='ID externo',
        help_text='Identificador asignado por la pasarela (PaymentIntent, etc.).',
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
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Respuesta de la pasarela',
        help_text='Último payload recibido de la pasarela.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

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

    # --- Máquina de estados ---

    def can_transition_to(self, new_status):
        """
        Indica si la transacción puede pasar al estado ``new_status``.

        Args:
            new_status: Estado destino.

        Returns:
            bool: True si la transición es legal.
        """
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status, save=True):
        """
        Cambia el estado de la transacción si la transición es válida.

        Args:
            new_status: Estado destino.
            save: Si ``True`` (por defecto), persiste el cambio en BD.

        Raises:
            ValidationError: Si la transición no está permitida.
        """
        if new_status == self.status:
            return
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f'No se puede pasar de "{self.status}" a "{new_status}".'
            )
        self.status = new_status
        if save:
            self.save(update_fields=['status', 'updated_at'])

    @property
    def is_terminal(self):
        """Indica si el estado actual es terminal (no admite transiciones)."""
        return not self.VALID_TRANSITIONS.get(self.status)

    @property
    def can_be_refunded(self):
        """True si la transacción puede devolverse."""
        return self.status == self.Status.COMPLETED


class Incident(models.Model):
    """
    Representa una incidencia asociada a una transacción.

    Documenta problemas detectados durante el procesado del pago, tales como
    impagos, errores de conexión con la pasarela o devoluciones.

    Attributes:
        transaction: Transacción afectada.
        incident_type: Tipo de incidencia.
        description: Detalle de la incidencia.
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
    resolved = models.BooleanField(default=False, verbose_name='Resuelta')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro')

    class Meta:
        """Metadatos del modelo Incident."""

        verbose_name = 'Incidencia'
        verbose_name_plural = 'Incidencias'
        ordering = ['-created_at']

    def __str__(self):
        """Representación legible de la incidencia."""
        return f'{self.get_incident_type_display()} - Tx {self.transaction.reference}'
