"""Registro de los modelos de transacciones en el admin de Django."""
from django.contrib import admin

from .models import Incident, Transaction


class IncidentInline(admin.TabularInline):
    """Permite editar las incidencias en línea desde la transacción."""

    model = Incident
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Configuración del admin para Transaction."""

    list_display = (
        'reference',
        'provider',
        'amount',
        'currency',
        'status',
        'created_at',
    )
    list_filter = ('status', 'currency', 'provider')
    search_fields = ('reference', 'description')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    inlines = [IncidentInline]


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    """Configuración del admin para Incident."""

    list_display = ('transaction', 'incident_type', 'resolved', 'created_at')
    list_filter = ('incident_type', 'resolved')
    search_fields = ('description', 'transaction__reference')
    readonly_fields = ('created_at',)
