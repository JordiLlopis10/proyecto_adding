"""URLs raíz del proyecto. Las rutas de la API se añadirán en el Hito 3."""
from django.contrib import admin
from django.urls import path


urlpatterns = [
    path('admin/', admin.site.urls),
    # Las rutas de la API REST se implementarán en el Hito 3.
    # Ejemplo previsto:
    #   path('api/v1/', include('providers.urls')),
    #   path('api/v1/', include('transactions.urls')),
]
