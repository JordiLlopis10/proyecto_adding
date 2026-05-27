"""
URLs raíz del proyecto.

"""
from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from .health import health_check


urlpatterns = [
    path('admin/', admin.site.urls),

    # Salud del servicio (público, sin auth)
    path('api/v1/health/', health_check, name='api-health'),

    # API v1
    path('api/v1/auth/token/', obtain_auth_token, name='api-token-auth'),
    path('api/v1/', include('providers.urls')),
    path('api/v1/', include('transactions.urls')),
    path('api/v1/', include('orders.urls')),

    # DRF login/logout para la interfaz navegable
    path('api-auth/', include('rest_framework.urls')),
]
