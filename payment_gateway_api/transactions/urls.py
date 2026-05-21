"""URLs de la app transactions."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IncidentViewSet, TransactionViewSet
from .webhooks import stripe_webhook

router = DefaultRouter()
router.register('transactions', TransactionViewSet, basename='transaction')
router.register('incidents', IncidentViewSet, basename='incident')

urlpatterns = [
    path('', include(router.urls)),
    path('webhooks/stripe/', stripe_webhook, name='stripe-webhook'),
]
