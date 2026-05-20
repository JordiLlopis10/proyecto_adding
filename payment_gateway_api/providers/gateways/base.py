"""
Interfaz abstracta de pasarela de pago.

Toda pasarela concreta (Stripe, PayPal, Redsys...) debe heredar de
:class:`PaymentGateway` e implementar los métodos abstractos. Las vistas y
servicios trabajan contra esta interfaz, nunca contra una pasarela concreta.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class ChargeResult:
    """
    Resultado normalizado de una operación contra una pasarela.

    Attributes:
        external_id: Identificador del cargo en la pasarela.
        status: Estado mapeado a la máquina de estados interna
            (``pending``, ``processing``, ``completed``, ``failed``,
            ``cancelled``, ``refunded``).
        raw_response: Respuesta cruda recibida (para auditoría).
        error_message: Mensaje de error si la operación ha fallado.
    """

    external_id: str
    status: str
    raw_response: dict = field(default_factory=dict)
    error_message: Optional[str] = None


class PaymentGateway(ABC):
    """
    Interfaz común para todas las pasarelas de pago.

    Las implementaciones concretas reciben en su constructor la instancia de
    :class:`providers.models.Provider` con sus credenciales y entorno.

    Args:
        provider: Registro del proveedor con ``api_key`` y ``environment``.
    """

    #: Código único que identifica a la pasarela (debe coincidir con
    #: el campo ``code`` del modelo :class:`Provider`).
    code: str = ''

    def __init__(self, provider):
        """Inicializa la pasarela con su configuración de proveedor."""
        self.provider = provider

    @abstractmethod
    def create_charge(
        self,
        amount: Decimal,
        currency: str,
        description: str = '',
        metadata: Optional[dict] = None,
    ) -> ChargeResult:
        """
        Crea un nuevo cargo / intención de pago en la pasarela.

        Args:
            amount: Importe a cobrar.
            currency: Código ISO 4217 de la moneda.
            description: Descripción opcional para el cliente.
            metadata: Metadatos adicionales a almacenar en la pasarela.

        Returns:
            ChargeResult con el ``external_id`` y el estado inicial.
        """

    @abstractmethod
    def capture(self, external_id: str) -> ChargeResult:
        """
        Confirma/captura un cargo previamente autorizado.

        Args:
            external_id: Identificador del cargo en la pasarela.

        Returns:
            ChargeResult con el estado actualizado.
        """

    @abstractmethod
    def refund(
        self,
        external_id: str,
        amount: Optional[Decimal] = None,
    ) -> ChargeResult:
        """
        Solicita la devolución total o parcial de un cargo.

        Args:
            external_id: Identificador del cargo en la pasarela.
            amount: Importe a devolver. Si es ``None``, devolución total.

        Returns:
            ChargeResult con el estado tras la devolución.
        """

    @abstractmethod
    def cancel(self, external_id: str) -> ChargeResult:
        """
        Cancela un cargo aún no capturado.

        Args:
            external_id: Identificador del cargo en la pasarela.

        Returns:
            ChargeResult con el estado tras la cancelación.
        """

    @abstractmethod
    def retrieve(self, external_id: str) -> ChargeResult:
        """
        Recupera el estado actual de un cargo.

        Args:
            external_id: Identificador del cargo en la pasarela.

        Returns:
            ChargeResult con la última información disponible.
        """
