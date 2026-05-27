"""
URLs de la app orders.

"""
from django.urls import path

from .views import OrderCreateView, OrderStatusView, OrderSuccessView, OrderCancelView
from .webhooks import payments_webhook

urlpatterns = [
    path('orders/create', OrderCreateView.as_view(), name='order-create'),
    path('orders/<int:pk>/status', OrderStatusView.as_view(), name='order-status'),
    path('orders/success/', OrderSuccessView.as_view(), name='order-success'),
    path('orders/cancel/', OrderCancelView.as_view(), name='order-cancel'),
    path('payments/webhook', payments_webhook, name='payments-webhook'),
]
