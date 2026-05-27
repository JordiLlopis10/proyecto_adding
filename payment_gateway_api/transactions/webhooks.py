"""
Endpoint para recibir webhooks de Stripe.

Stripe envía eventos (pagos completados, fallidos, devueltos...) a una URL
que registramos en su panel. Aquí verificamos la firma del webhook y
actualizamos el estado de la transacción correspondiente.

Referencia: https://stripe.com/docs/webhooks
"""
import json
import logging

import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response

from .models import Incident, Transaction

logger = logging.getLogger(__name__)


# Mapeo evento Stripe -> estado interno de la transacción.
EVENT_TO_STATUS = {
    'payment_intent.succeeded': Transaction.Status.COMPLETED,
    'payment_intent.payment_failed': Transaction.Status.FAILED,
    'payment_intent.canceled': Transaction.Status.CANCELLED,
    'charge.refunded': Transaction.Status.REFUNDED,
}


def _get(obj, key, default=None):
    """
    Accede a un campo de un StripeObject o dict de forma segura.

    Compatible con todas las versiones del SDK de Stripe: algunas exponen
    `.get()` (herencia de dict), otras solo soportan acceso por ``[]``.
    """
    try:
        return obj[key]
    except (KeyError, TypeError):
        return default


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])  # Stripe no envía nuestro token; valida por firma.
@permission_classes([])
def stripe_webhook(request):
    """
    Recibe y procesa eventos de Stripe.

    Verifica la firma del webhook contra ``STRIPE_WEBHOOK_SECRET`` antes de
    actuar. Si el evento no se reconoce, responde 200 OK (Stripe reintentará
    si devolvemos un error, así que solo erramos cuando realmente conviene).
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    secret = settings.STRIPE_WEBHOOK_SECRET

    if not secret:
        logger.error('STRIPE_WEBHOOK_SECRET no configurado.')
        return Response(
            {'detail': 'Webhook no configurado.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except ValueError:
        logger.warning('Webhook con payload inválido.')
        return Response({'detail': 'Payload inválido.'}, status=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError:
        logger.warning('Webhook con firma inválida.')
        return Response({'detail': 'Firma inválida.'}, status=status.HTTP_400_BAD_REQUEST)

    # Usamos [] en vez de .get() porque StripeObject no siempre expone .get()
    event_type = event['type']
    logger.info('Webhook de Stripe recibido: %s', event_type)

    # Filtrado temprano: si no nos interesa el evento, 200 OK sin tocar BD.
    if event_type not in EVENT_TO_STATUS:
        logger.info('Evento ignorado (no mapeado): %s', event_type)
        return Response({'detail': 'Evento ignorado.'}, status=status.HTTP_200_OK)

    obj = event['data']['object']
    # Para charge.refunded el id del PaymentIntent está en otro lugar.
    external_id = _get(obj, 'payment_intent') or _get(obj, 'id')

    try:
        tx = Transaction.objects.get(external_id=external_id)
    except Transaction.DoesNotExist:
        logger.warning('Webhook para transacción desconocida: %s', external_id)
        # Devolvemos 200 para que Stripe no reintente indefinidamente.
        return Response({'detail': 'Transacción no encontrada.'}, status=status.HTTP_200_OK)
    except Exception as exc:  # noqa: BLE001
        logger.exception('Error inesperado al buscar Transaction: %s', exc)
        return Response(
            {'detail': f'Error interno al consultar la BD: {exc}',
             'hint': 'Asegúrate de haber ejecutado "python manage.py migrate".'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    new_status = EVENT_TO_STATUS[event_type]

    if tx.can_transition_to(new_status):
        tx.gateway_response = json.loads(json.dumps(dict(obj), default=str))
        tx.transition_to(new_status, save=False)
        tx.save()
        # Si el pago ha fallado registramos una incidencia automática.
        if new_status == Transaction.Status.FAILED:
            last_error = _get(obj, 'last_payment_error') or {}
            error_msg = _get(last_error, 'message', 'sin detalle') or 'sin detalle'
            Incident.objects.create(
                transaction=tx,
                incident_type=Incident.IncidentType.UNPAID,
                description=f'Pago fallido reportado por Stripe: {error_msg}.',
            )
    else:
        logger.info(
            'Transición ignorada %s -> %s (transacción %s)',
            tx.status, new_status, tx.reference,
        )

    return Response({'detail': 'Procesado.'}, status=status.HTTP_200_OK)
