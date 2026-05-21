"""
Modelos para la app orders.

El modelo :class:`Order` representa un pedido que se paga mediante
redirección al portal de Stripe (Stripe Checkout). El flujo es:

1. Se crea el pedido en BD con estado ``pending``.
2. El backend solicita una Checkout Session a Stripe y guarda su ID.
3. El cliente se redirige a la URL de Stripe para pagar.
4. Stripe notifica el resultado al webhook y el estado pasa a ``paid``
   o ``failed``.
"""
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from providers.models import Provider


class Order(models.Model):
    """
    Representa un pedido pendiente de pago por redirección a Stripe Checkout.

    Attributes:
        reference: Identificador único interno (UUID).
        provider: Proveedor de pago utilizado (debe tener code='stripe').
        amount: Importe del pedido (positivo, hasta 2 decimales).
        currency: Código ISO 4217 (ej: ``EUR``).
        description: Descripción del pedido mostrada al cliente en Stripe.
        status: Estado del pedido (``pending``, ``paid``, ``failed``,
            ``expired``).
        stripe_session_id: ID de la Checkout Session de Stripe
            (ej: ``cs_test_...``). Se rellena al crear el pedido.
        stripe_payment_intent: ID del PaymentIntent asociado. Stripe lo
            incluye en el webhook una vez completado el pago.
        checkout_url: URL de Stripe a la que se redirige al cliente.
        created_at: Fecha de creación.
        updated_at: Fecha de la última modificación.
    """

    class Status(models.TextChoices):
        """Estados posibles del pedido."""

        PENDING = 'pending', 'Pendiente'
        PAID = 'paid', 'Pagado'
        FAILED = 'failed', 'Fallido'
        EXPIRED = 'expired', 'Expirado'

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name='Referencia',
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Proveedor',
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.50'))],
        verbose_name='Importe',
        help_text='Mínimo 0.50 (límite de Stripe).',
    )
    currency = models.CharField(
        max_length=3,
        default='EUR',
        verbose_name='Moneda',
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Descripción',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Estado',
        db_index=True,
    )
    stripe_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        verbose_name='Stripe Session ID',
    )
    stripe_payment_intent = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Stripe PaymentIntent ID',
    )
    checkout_url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name='URL de pago',
        help_text='URL de Stripe Checkout a la que se redirige al cliente.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        """Metadatos del modelo Order."""

        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-created_at']

    def __str__(self):
        """Representación legible del pedido."""
        return f'Pedido {self.reference} — {self.amount} {self.currency} ({self.status})'
