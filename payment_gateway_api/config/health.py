"""
Endpoint de salud (health-check) de la API.

Útil para monitores externos (Uptime Robot, Healthchecks.io, etc.) y para
comprobar rápidamente desde Postman que el servidor responde antes de
empezar a depurar problemas más complejos.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response


@api_view(['GET'])
@authentication_classes([])
@permission_classes([])
def health_check(request):
    """
    Devuelve el estado del servicio y la configuración de pasarelas.

    No expone secretos: solo indica si las variables están configuradas.
    """
    return Response(
        {
            'status': 'ok',
            'service': 'payment-gateway-api',
            'stripe': {
                'api_key_configured': bool(settings.STRIPE_API_KEY),
                'webhook_secret_configured': bool(settings.STRIPE_WEBHOOK_SECRET),
            },
        },
        status=status.HTTP_200_OK,
    )
