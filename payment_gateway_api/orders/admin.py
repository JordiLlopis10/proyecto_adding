"""Registro del modelo Order en el panel de administración."""
from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Configuración del admin para Order."""

    list_display = (
        'reference', 'provider', 'amount', 'currency',
        'status', 'created_at',
    )
    list_filter = ('status', 'currency', 'provider')
    search_fields = ('reference', 'stripe_session_id', 'stripe_payment_intent')
    readonly_fields = (
        'reference', 'stripe_session_id', 'stripe_payment_intent',
        'checkout_url', 'created_at', 'updated_at',
    )
