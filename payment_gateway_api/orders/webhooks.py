"""
Webhook de Stripe para el modelo de redirección (Checkout Sessions).

Stripe llama a este endpoint cuando el estado del pago cambia.
El evento más importante es ``checkout.session.completed``, que indica
que el usuario ha pagado correctamente.

Referencia: https://stripe.com/docs/payments/checkout/fulfill-orders
"""
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

from .models import Order

logger = logging.getLogger(__name__)

# Mapeo evento Stripe → estado interno de Order.
EVENT_STATUS_MAP = {
    'checkout.session.completed': Order.Status.PAID,
    'checkout.session.expired': Order.Status.EXPIRED,
}


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])   # Stripe no envía token; autentica por firma.
@permission_classes([])
def payments_webhook(request):
    """
    Recibe eventos de Stripe Checkout y actualiza el estado del pedido.

    Stripe reintentará el envío si devolvemos un código != 2xx,
    así que solo erramos cuando hay un problema real (firma inválida).
    Para eventos desconocidos o transacciones no encontradas devolvemos
    200 OK para que Stripe no siga reintentando.

    Seguridad: verificamos la firma HMAC con ``STRIPE_WEBHOOK_SECRET``
    antes de procesar cualquier evento.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    secret = settings.STRIPE_WEBHOOK_SECRET

    if not secret:
        logger.error('STRIPE_WEBHOOK_SECRET no configurado.')
        return Response(
            {'detail': 'Webhook no configurado en el servidor.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # --- Verificación de firma ---
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except ValueError:
        logger.warning('Webhook: payload inválido.')
        return Response(
            {'detail': 'Payload inválido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except stripe.error.SignatureVerificationError:
        logger.warning('Webhook: firma inválida.')
        return Response(
            {'detail': 'Firma inválida.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    event_type = event.get('type')
    session = event['data']['object']
    logger.info('Webhook recibido: %s (session=%s)', event_type, session.get('id'))

    # --- Localizar el pedido ---
    # Buscamos por stripe_session_id, que guardamos al crear la Checkout Session.
    session_id = session.get('id')
    try:
        order = Order.objects.get(stripe_session_id=session_id)
    except Order.DoesNotExist:
        logger.warning('Webhook: Order no encontrada para session %s', session_id)
        # 200 OK para que Stripe no reintente.
        return Response({'detail': 'Pedido no encontrado.'}, status=status.HTTP_200_OK)

    # --- Actualizar estado ---
    new_status = EVENT_STATUS_MAP.get(event_type)
    if new_status is None:
        logger.info('Evento ignorado (no mapeado): %s', event_type)
        return Response({'detail': 'Evento ignorado.'}, status=status.HTTP_200_OK)

    if order.status == Order.Status.PAID:
        # Ya estaba pagado (webhook duplicado). Devolvemos 200 sin hacer nada.
        logger.info('Order %s ya estaba pagada. Webhook ignorado.', order.reference)
        return Response({'detail': 'Ya procesado.'}, status=status.HTTP_200_OK)

    # En checkout.session.completed, Stripe incluye el payment_intent.
    if event_type == 'checkout.session.completed':
        order.stripe_payment_intent = session.get('payment_intent', '')

    order.status = new_status
    order.save(update_fields=['status', 'stripe_payment_intent', 'updated_at'])

    logger.info('Order %s actualizada a "%s"', order.reference, new_status)
    return Response({'detail': 'Procesado.'}, status=status.HTTP_200_OK)
