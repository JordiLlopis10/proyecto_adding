"""
Manejador global de excepciones para la API.

Convierte las excepciones de dominio (errores de pasarela, transiciones de
estado inválidas) en respuestas HTTP coherentes para los clientes.
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Manejador de excepciones extendido.

    Primero delega en el manejador por defecto de DRF para excepciones
    conocidas (ValidationError, NotFound, etc.). Si no hay respuesta,
    captura excepciones específicas del dominio.

    Args:
        exc: La excepción lanzada.
        context: Contexto con información de la vista y la petición.

    Returns:
        ``Response`` con el error formateado, o ``None`` si DRF debe
        gestionar la excepción por defecto.
    """
    # Importación local para evitar problemas de carga circular al iniciar.
    from providers.gateways.exceptions import (
        GatewayError,
        InvalidTransitionError,
        ProviderInactiveError,
    )

    response = exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, InvalidTransitionError):
        logger.warning('Transición de estado inválida: %s', exc)
        return Response(
            {'detail': str(exc), 'error': 'invalid_state_transition'},
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, ProviderInactiveError):
        return Response(
            {'detail': str(exc), 'error': 'provider_inactive'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, GatewayError):
        logger.error('Error de pasarela: %s', exc, exc_info=True)
        return Response(
            {'detail': str(exc), 'error': 'gateway_error'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return None
