"""
Script de prueba end-to-end del flujo de compra con Stripe Checkout.

Uso:
    1. Arranca el servidor en otra terminal: python manage.py runserver
    2. (Opcional, para webhooks) Arranca Stripe CLI en otra terminal:
       stripe listen --forward-to localhost:8000/api/v1/payments/webhook
    3. Ejecuta este script:
       python scripts/smoke_test.py

El script:
    - Comprueba el endpoint de salud.
    - Obtiene un token de autenticación para el usuario indicado.
    - Lista los proveedores y elige el de Stripe.
    - Crea un pedido y muestra la URL de checkout que devuelve Stripe.
    - Consulta el estado del pedido.

NO requiere claves de prueba especiales: usa las del .env.
"""
import argparse
import json
import sys

import requests

DEFAULT_BASE_URL = 'http://localhost:8000'
DEFAULT_USERNAME = 'jordi'


def colored(text, color):
    """Devuelve el texto con códigos ANSI de color."""
    codes = {'red': 31, 'green': 32, 'yellow': 33, 'blue': 34, 'cyan': 36}
    return f'\033[{codes.get(color, 0)}m{text}\033[0m'


def step(title):
    """Imprime un encabezado de paso."""
    print(f'\n{colored("▶", "cyan")} {colored(title, "blue")}')


def ok(msg):
    """Imprime un mensaje de éxito."""
    print(f'  {colored("✓", "green")} {msg}')


def fail(msg):
    """Imprime un mensaje de error y sale con código 1."""
    print(f'  {colored("✗", "red")} {msg}')
    sys.exit(1)


def main():
    """Ejecuta el flujo de prueba completo."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help=f'URL base de la API (default: {DEFAULT_BASE_URL})')
    parser.add_argument('--username', default=DEFAULT_USERNAME,
                        help=f'Usuario (default: {DEFAULT_USERNAME})')
    parser.add_argument('--password', required=True,
                        help='Contraseña del usuario')
    parser.add_argument('--amount', default='49.90',
                        help='Importe del pedido (default: 49.90)')
    parser.add_argument('--currency', default='EUR',
                        help='Moneda (default: EUR)')
    args = parser.parse_args()

    # === 1. Health check ===
    step('Comprobando que la API responde...')
    r = requests.get(f'{args.base_url}/api/v1/health/', timeout=5)
    if r.status_code != 200:
        fail(f'/health/ devolvió {r.status_code}')
    data = r.json()
    ok(f'API viva (status={data["status"]})')
    if not data['stripe']['api_key_configured']:
        fail('STRIPE_API_KEY no configurada en el .env')
    ok('STRIPE_API_KEY configurada')
    if not data['stripe']['webhook_secret_configured']:
        print(f'  {colored("!", "yellow")} STRIPE_WEBHOOK_SECRET no configurado '
              f'(el webhook fallará hasta que lo configures)')
    else:
        ok('STRIPE_WEBHOOK_SECRET configurado')

    # === 2. Token de autenticación ===
    step('Obteniendo token de autenticación...')
    r = requests.post(
        f'{args.base_url}/api/v1/auth/token/',
        data={'username': args.username, 'password': args.password},
        timeout=5,
    )
    if r.status_code != 200:
        fail(f'No se pudo obtener token: {r.status_code} {r.text}')
    token = r.json()['token']
    headers = {'Authorization': f'Token {token}'}
    ok(f'Token obtenido: {token[:12]}...')

    # === 3. Listar proveedores ===
    step('Buscando proveedor Stripe...')
    r = requests.get(f'{args.base_url}/api/v1/providers/', headers=headers, timeout=5)
    if r.status_code != 200:
        fail(f'No se pudieron listar proveedores: {r.status_code}')
    providers = r.json()['results']
    stripe_provider = next(
        (p for p in providers if p['code'] == 'stripe' and p['is_active']),
        None,
    )
    if not stripe_provider:
        fail('No hay ningún Provider activo con code="stripe"')
    ok(f'Proveedor encontrado: id={stripe_provider["id"]} '
       f'env={stripe_provider["environment"]}')

    # === 4. Crear pedido ===
    step(f'Creando pedido de {args.amount} {args.currency}...')
    payload = {
        'provider': stripe_provider['id'],
        'amount': args.amount,
        'currency': args.currency,
        'description': 'Pedido de prueba (smoke_test.py)',
    }
    r = requests.post(
        f'{args.base_url}/api/v1/orders/create',
        headers=headers,
        json=payload,
        timeout=15,
    )
    if r.status_code != 201:
        fail(f'No se pudo crear el pedido: {r.status_code}\n{json.dumps(r.json(), indent=2)}')
    order = r.json()
    ok(f'Pedido creado: id={order["id"]} reference={order["reference"]}')
    ok(f'Estado inicial: {order["status"]}')
    print(f'\n  {colored("URL de pago de Stripe:", "yellow")}')
    print(f'  {colored(order["checkout_url"], "cyan")}\n')
    print('  Ábrela en tu navegador y paga con tarjeta de test:')
    print('    4242 4242 4242 4242  /  cualquier CVC  /  cualquier fecha futura')

    # === 5. Consultar estado ===
    step('Consultando estado del pedido...')
    r = requests.get(
        f'{args.base_url}/api/v1/orders/{order["id"]}/status',
        headers=headers,
        timeout=5,
    )
    if r.status_code != 200:
        fail(f'No se pudo consultar el estado: {r.status_code}')
    status_data = r.json()
    ok(f'Estado actual: {status_data["status"]} ({status_data["status_display"]})')

    print(f'\n{colored("✔ Smoke test OK", "green")}')
    print('Para confirmar el pago como pagado:')
    print('  1. Visita la checkout_url anterior y completa el pago.')
    print(f'  2. Vuelve a llamar a GET /api/v1/orders/{order["id"]}/status')
    print('  3. El estado debe pasar de "pending" a "paid" tras el webhook.')


if __name__ == '__main__':
    main()
