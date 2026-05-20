"""URLs de la app providers."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProviderViewSet

router = DefaultRouter()
router.register('providers', ProviderViewSet, basename='provider')

urlpatterns = [
    path('', include(router.urls)),
]
