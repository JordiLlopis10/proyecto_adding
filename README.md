# Payment Gateway API

API REST desarrollada con Django REST Framework para gestionar pasarelas de pago de forma centralizada. Actualmente soporta Stripe como pasarela activa.

Proyecto Final Intermodular — CE Desarrollo de Aplicaciones en Lenguaje Python (Curso 2025–2026).

## Tecnologías
- Python 3.10+
- Django 5
- Django REST Framework
- django-filter
- Stripe (SDK oficial)
- SQLite
- python-decouple (variables de entorno)

## Funcionalidades
- Gestión de proveedores de pago (alta, baja, listado)
- Creación de pedidos con redirección a Stripe Checkout
- Recepción de webhooks de Stripe para confirmar pagos
- Consulta del estado de un pedido
- Registro de transacciones e incidencias
- Filtrado de historial por proveedor, fecha y estado
- Autenticación por Token (DRF)

## Endpoints principales

### Autenticación
- `POST /api/v1/auth/token/` — obtener token

### Proveedores
- `GET /api/v1/providers/` — listar
- `POST /api/v1/providers/` — crear (solo admin)
- `GET /api/v1/providers/{id}/` — detalle

### Pedidos (flujo de redirección)
- `POST /api/v1/orders/create` — crear pedido y obtener URL de pago de Stripe
- `GET /api/v1/orders/{id}/status` — consultar estado del pedido
- `POST /api/v1/payments/webhook` — webhook de Stripe (interno)

### Transacciones e incidencias
- `GET /api/v1/transactions/` — historial filtrable
- `GET /api/v1/incidents/` — incidencias registradas


## Autor
Jordi Llopis