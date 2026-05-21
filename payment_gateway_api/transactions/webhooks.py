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

    event_type = event.get('type')
    logger.info('Webhook de Stripe recibido: %s', event_type)

    obj = event['data']['object']
    # Para charge.refunded el id del PaymentIntent está en otro lugar.
    external_id = obj.get('payment_intent') or obj.get('id')

    try:
        tx = Transaction.objects.get(external_id=external_id)
    except Transaction.DoesNotExist:
        logger.warning('Webhook para transacción desconocida: %s', external_id)
        # Devolvemos 200 para que Stripe no reintente indefinidamente.
        return Response({'detail': 'Transacción no encontrada.'}, status=status.HTTP_200_OK)

    new_status = EVENT_TO_STATUS.get(event_type)
    if new_status is None:
        logger.info('Evento ignorado (no mapeado): %s', event_type)
        return Response({'detail': 'Evento ignorado.'}, status=status.HTTP_200_OK)

    if tx.can_transition_to(new_status):
        tx.gateway_response = json.loads(json.dumps(obj, default=str))
        tx.transition_to(new_status, save=False)
        tx.save()
        # Si el pago ha fallado registramos una incidencia automática.
        if new_status == Transaction.Status.FAILED:
            Incident.objects.create(
                transaction=tx,
                incident_type=Incident.IncidentType.UNPAID,
                description=(
                    f'Pago fallido reportado por Stripe: '
                    f'{obj.get("last_payment_error", {}).get("message", "sin detalle")}.'
                ),
            )
    else:
        logger.info(
            'Transición ignorada %s -> %s (transacción %s)',
            tx.status, new_status, tx.reference,
        )

    return Response({'detail': 'Procesado.'}, status=status.HTTP_200_OK)
