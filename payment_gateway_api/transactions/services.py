"""
Capa de servicios para la app transactions.

Concentra la lógica de negocio relacionada con el ciclo de vida de un pago:
creación, captura, devolución y cancelación. Las vistas (capa HTTP) se
limitan a llamar a estos servicios.

El uso de :func:`django.db.transaction.atomic` garantiza que la persistencia
en BD y las llamadas a la pasarela se sincronicen correctamente.
"""
import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction as db_transaction

from providers.gateways import get_gateway
from providers.gateways.exceptions import InvalidTransitionError
from providers.models import Provider

from .models import Incident, Transaction

logger = logging.getLogger(__name__)


class TransactionService:
    """
    Orquesta las operaciones del ciclo de vida de una transacción.

    Cada método estático encapsula un caso de uso (crear, capturar, devolver,
    cancelar). La capa de vistas debe llamar a estos métodos en lugar de
    manipular el modelo directamente.
    """

    @staticmethod
    def create_charge(
        provider: Provider,
        amount: Decimal,
        currency: str,
        description: str = '',
        metadata: Optional[dict] = None,
    ) -> Transaction:
        """
        Crea una transacción en BD y solicita el cargo en la pasarela.

        Si la pasarela responde con un error, la transacción se persiste con
        estado ``failed`` y se registra una incidencia automática del tipo
        ``connection_error``, para conservar la trazabilidad del intento.

        Args:
            provider: Proveedor a través del que se procesa el pago.
            amount: Importe.
            currency: Moneda ISO 4217.
            description: Descripción opcional.
            metadata: Metadatos adicionales para la pasarela.

        Returns:
            La instancia de :class:`Transaction` persistida.
        """
        gateway = get_gateway(provider)
        try:
            result = gateway.create_charge(
                amount=amount,
                currency=currency,
                description=description,
                metadata=metadata or {},
            )
        except Exception as exc:
            # IMPORTANTE: persistimos el intento fallido FUERA de cualquier
            # bloque atómico para que el rollback de la llamada a la pasarela
            # no arrastre también este registro.
            logger.exception('Fallo al crear cargo en %s', provider.code)
            with db_transaction.atomic():
                tx = Transaction.objects.create(
                    provider=provider,
                    amount=amount,
                    currency=currency,
                    description=description,
                    status=Transaction.Status.FAILED,
                    gateway_response={'error': str(exc)},
                )
                Incident.objects.create(
                    transaction=tx,
                    incident_type=Incident.IncidentType.CONNECTION_ERROR,
                    description=f'Error al contactar con {provider.name}: {exc}',
                )
            raise

        with db_transaction.atomic():
            tx = Transaction.objects.create(
                provider=provider,
                amount=amount,
                currency=currency,
                description=description,
                external_id=result.external_id,
                status=result.status,
                gateway_response=result.raw_response,
            )
        logger.info('Transacción creada: %s (external=%s)', tx.reference, tx.external_id)
        return tx

    @staticmethod
    @db_transaction.atomic
    def capture(tx: Transaction) -> Transaction:
        """
        Captura/confirma una transacción autorizada.

        Args:
            tx: Transacción a capturar.

        Returns:
            La transacción actualizada.
        """
        if tx.status not in {
            Transaction.Status.PENDING,
            Transaction.Status.PROCESSING,
        }:
            raise InvalidTransitionError(
                f'No se puede capturar una transacción en estado "{tx.status}".'
            )

        gateway = get_gateway(tx.provider)
        result = gateway.capture(tx.external_id)
        tx.gateway_response = result.raw_response
        tx.transition_to(result.status)
        return tx

    @staticmethod
    @db_transaction.atomic
    def refund(tx: Transaction, amount: Optional[Decimal] = None) -> Transaction:
        """
        Solicita la devolución de una transacción.

        Registra automáticamente una incidencia del tipo "devolución".

        Args:
            tx: Transacción a devolver. Debe estar en estado ``completed``.
            amount: Importe a devolver (None = devolución total).

        Returns:
            La transacción actualizada.
        """
        if not tx.can_be_refunded:
            raise InvalidTransitionError(
                'Solo se pueden devolver transacciones completadas.'
            )

        gateway = get_gateway(tx.provider)
        result = gateway.refund(tx.external_id, amount=amount)
        tx.gateway_response = result.raw_response
        tx.transition_to(Transaction.Status.REFUNDED)

        # Registramos una incidencia de tipo devolución (trazabilidad).
        refund_amount = amount if amount is not None else tx.amount
        Incident.objects.create(
            transaction=tx,
            incident_type=Incident.IncidentType.REFUND,
            description=(
                f'Devolución de {refund_amount} {tx.currency} '
                f'procesada por {tx.provider.name}.'
            ),
            resolved=True,
        )
        return tx

    @staticmethod
    @db_transaction.atomic
    def cancel(tx: Transaction) -> Transaction:
        """
        Cancela una transacción pendiente.

        Args:
            tx: Transacción a cancelar.

        Returns:
            La transacción actualizada.
        """
        if tx.status not in {
            Transaction.Status.PENDING,
            Transaction.Status.PROCESSING,
        }:
            raise InvalidTransitionError(
                f'No se puede cancelar una transacción en estado "{tx.status}".'
            )

        gateway = get_gateway(tx.provider)
        result = gateway.cancel(tx.external_id)
        tx.gateway_response = result.raw_response
        tx.transition_to(Transaction.Status.CANCELLED)
        return tx
