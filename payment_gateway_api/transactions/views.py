"""
Vistas (ViewSets) para la app transactions.

Implementa los endpoints REST para gestionar transacciones e incidencias.
La lógica de negocio se delega en :mod:`transactions.services`.
"""
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import IncidentFilter, TransactionFilter
from .models import Incident, Transaction
from .serializers import (
    IncidentSerializer,
    RefundRequestSerializer,
    TransactionCreateSerializer,
    TransactionSerializer,
)
from .services import TransactionService


class TransactionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Endpoint REST para gestionar transacciones.

    Las transacciones no se pueden eliminar ni actualizar libremente desde la
    API: para cambiar de estado deben usarse las acciones específicas
    (``capture``, ``refund``, ``cancel``) que aplican la lógica de la pasarela.

    Endpoints:

        GET    /transactions/                  Listado paginado y filtrable.
        POST   /transactions/                  Crea un cargo en la pasarela.
        GET    /transactions/{id}/             Detalle de una transacción.
        POST   /transactions/{id}/capture/     Captura/confirma el cargo.
        POST   /transactions/{id}/refund/      Solicita la devolución.
        POST   /transactions/{id}/cancel/      Cancela un cargo pendiente.
        POST   /transactions/{id}/incidents/   Registra una incidencia.
    """

    queryset = (
        Transaction.objects
        .select_related('provider')
        .prefetch_related('incidents')
        .all()
    )
    filterset_class = TransactionFilter
    search_fields = ['reference', 'external_id', 'description']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Selecciona el serializador en función de la acción."""
        if self.action == 'create':
            return TransactionCreateSerializer
        return TransactionSerializer

    def create(self, request, *args, **kwargs):
        """Crea una transacción a través del servicio (no por el ORM directo)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tx = TransactionService.create_charge(**serializer.validated_data)
        output = TransactionSerializer(tx, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def capture(self, request, pk=None):
        """Captura/confirma una transacción autorizada."""
        tx = self.get_object()
        tx = TransactionService.capture(tx)
        return Response(TransactionSerializer(tx).data)

    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Solicita la devolución de la transacción."""
        tx = self.get_object()
        payload = RefundRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        tx = TransactionService.refund(tx, amount=payload.validated_data.get('amount'))
        return Response(TransactionSerializer(tx).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancela una transacción pendiente."""
        tx = self.get_object()
        tx = TransactionService.cancel(tx)
        return Response(TransactionSerializer(tx).data)

    @action(detail=True, methods=['post'], url_path='incidents')
    def add_incident(self, request, pk=None):
        """Registra una incidencia asociada a una transacción concreta."""
        tx = self.get_object()
        # Forzamos la transacción del path: el cliente no puede sobrescribirla.
        payload = {
            'transaction': tx.pk,
            'incident_type': request.data.get('incident_type'),
            'description': request.data.get('description', ''),
            'resolved': request.data.get('resolved', False),
        }
        serializer = IncidentSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IncidentViewSet(viewsets.ModelViewSet):
    """
    Endpoint REST para gestionar incidencias de forma autónoma.

    Las incidencias también pueden registrarse en el contexto de una
    transacción concreta vía ``/transactions/{id}/incidents/``.
    """

    queryset = Incident.objects.select_related('transaction').all()
    serializer_class = IncidentSerializer
    filterset_class = IncidentFilter
    search_fields = ['description']
    ordering_fields = ['created_at', 'incident_type']
    ordering = ['-created_at']
