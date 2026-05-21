"""
Vistas para la app orders.


"""
import logging

from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import (
    OrderCreateResponseSerializer,
    OrderCreateSerializer,
    OrderStatusSerializer,
)
from .services import OrderService

logger = logging.getLogger(__name__)


class OrderCreateView(APIView):
    """
    Crea un pedido y devuelve la URL de pago de Stripe Checkout.

    El cliente debe redirigir al usuario a ``checkout_url``.

    **Request (POST /orders/create):**
    ```json
    {
        "provider": 1,
        "amount": "49.90",
        "currency": "EUR",
        "description": "Pedido #1001"
    }
    ```

    **Response 201:**
    ```json
    {
        "id": 1,
        "reference": "uuid...",
        "amount": "49.90",
        "currency": "EUR",
        "status": "pending",
        "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
    }
    ```
    """

    def post(self, request):
        """Valida los datos, crea el pedido y la Checkout Session de Stripe."""
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Parámetros de redirección opcionales: el cliente puede enviar sus
        # propias URLs de éxito y cancelación.
        success_url = request.data.get('success_url', '')
        cancel_url = request.data.get('cancel_url', '')

        order = OrderService.create_order(
            **serializer.validated_data,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        response_serializer = OrderCreateResponseSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class OrderStatusView(RetrieveAPIView):
    """
    Consulta el estado actual de un pedido.

    **Request: GET /orders/{id}/status**

    **Response 200:**
    ```json
    {
        "id": 1,
        "reference": "uuid...",
        "amount": "49.90",
        "currency": "EUR",
        "status": "paid",
        "status_display": "Pagado",
        "stripe_payment_intent": "pi_...",
        "created_at": "...",
        "updated_at": "..."
    }
    ```
    """

    queryset = Order.objects.select_related('provider').all()
    serializer_class = OrderStatusSerializer
    # El endpoint es de solo lectura; no requiere permisos de escritura.
