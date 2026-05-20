"""
Excepciones específicas del dominio de pasarelas de pago.

Cada tipo de error se mapea a un código HTTP en
:mod:`config.exceptions`.
"""


class GatewayError(Exception):
    """Error genérico al interactuar con una pasarela de pago."""


class GatewayUnavailableError(GatewayError):
    """La pasarela no está disponible o no se ha podido contactar."""


class GatewayConfigurationError(GatewayError):
    """La pasarela no está correctamente configurada (falta API key, etc.)."""


class GatewayNotImplementedError(GatewayError):
    """Se ha solicitado una pasarela que aún no tiene implementación."""


class InvalidTransitionError(Exception):
    """La transición de estado solicitada no está permitida."""


class ProviderInactiveError(Exception):
    """Se ha intentado operar contra un proveedor inactivo."""
