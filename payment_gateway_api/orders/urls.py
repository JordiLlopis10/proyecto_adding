"""
URLs de la app orders.

"""
from django.urls import path

from .views import OrderCreateView, OrderStatusView
from .webhooks import payments_webhook

urlpatterns = [
    path('orders/create', OrderCreateView.as_view(), name='order-create'),
    path('orders/<int:pk>/status', OrderStatusView.as_view(), name='order-status'),
    path('payments/webhook', payments_webhook, name='payments-webhook'),
]
