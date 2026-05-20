"""
Registro de pasarelas de pago.
Por ahora solo Stripe está implementado.
"""
from .base import PaymentGateway
from .exceptions import GatewayNotImplementedError, ProviderInactiveError
from .stripe_gw import StripeGateway

GATEWAY_REGISTRY = {
    StripeGateway.code: StripeGateway,
}


def get_gateway(provider) -> PaymentGateway:
    """
    Devuelve la pasarela correspondiente al proveedor.

    Args:
        provider: Instancia de Provider.

    Returns:
        Pasarela configurada y lista para usar.

    Raises:
        ProviderInactiveError: Si el proveedor está inactivo.
        GatewayNotImplementedError: Si no hay pasarela para ese código.
    """
    if not provider.is_active:
        raise ProviderInactiveError(
            f'El proveedor "{provider.name}" no está activo.'
        )
    gateway_cls = GATEWAY_REGISTRY.get(provider.code)
    if gateway_cls is None:
        raise GatewayNotImplementedError(
            f'No hay pasarela para el código "{provider.code}".'
        )
    return gateway_cls(provider)


def available_gateways() -> list[str]:
    """Devuelve los códigos de pasarela disponibles."""
    return sorted(GATEWAY_REGISTRY.keys())