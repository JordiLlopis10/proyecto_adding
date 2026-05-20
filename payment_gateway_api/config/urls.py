"""
URLs raíz del proyecto.

"""
from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token


urlpatterns = [
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/auth/token/', obtain_auth_token, name='api-token-auth'),
    path('api/v1/', include('providers.urls')),
    path('api/v1/', include('transactions.urls')),
    path('api/v1/', include('orders.urls')),

    # DRF login/logout para la interfaz navegable
    path('api-auth/', include('rest_framework.urls')),
]
