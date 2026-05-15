"""Registro del modelo Provider en el panel de administración de Django."""
from django.contrib import admin

from .models import Provider


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    """Configuración del admin para el modelo Provider."""

    list_display = ('name', 'code', 'environment', 'is_active', 'created_at')
    list_filter = ('environment', 'is_active')
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')
