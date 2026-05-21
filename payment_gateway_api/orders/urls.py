"""
URLs de la app orders.

Rutas expuestas (tal y como aparecen en la presentación):

    POST  /orders/create          → crea pedido + Checkout Session
    GET   /orders/{id}/status     → estado actual del pedido
    POST  /payments/webhook       → eventos de Stripe (firma HMAC)
"""
from django.urls import path

from .views import OrderCreateView, OrderStatusView
from .webhooks import payments_webhook

urlpatterns = [
    path('orders/create', OrderCreateView.as_view(), name='order-create'),
    path('orders/<int:pk>/status', OrderStatusView.as_view(), name='order-status'),
    path('payments/webhook', payments_webhook, name='payments-webhook'),
]
