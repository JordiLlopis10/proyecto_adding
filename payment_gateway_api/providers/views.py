"""Vistas (ViewSets) para la app providers."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .gateways import available_gateways
from .models import Provider
from .serializers import ProviderSerializer


class ProviderViewSet(viewsets.ModelViewSet):
    """
    Endpoint REST para gestionar pasarelas de pago.

    La creación, modificación y borrado están restringidos a usuarios staff
    (``IsAdminUser``), pues afectan a la configuración financiera del
    sistema. La lectura está disponible para cualquier usuario autenticado.

    Endpoints:

        GET    /providers/                Listado.
        POST   /providers/                Alta de un proveedor (staff).
        GET    /providers/{id}/           Detalle.
        PUT    /providers/{id}/           Edición completa (staff).
        PATCH  /providers/{id}/           Edición parcial (staff).
        DELETE /providers/{id}/           Baja (staff).
        GET    /providers/available/      Códigos de pasarela soportados.
    """

    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    filterset_fields = ['environment', 'is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_permissions(self):
        """Lectura para autenticados; escritura solo para admin."""
        if self.action in {'list', 'retrieve', 'available'}:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Devuelve la lista de pasarelas registradas en el sistema."""
        return Response({'available_gateways': available_gateways()})
