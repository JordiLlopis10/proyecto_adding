#!/usr/bin/env python
"""Utilidad de línea de comandos de Django para tareas administrativas."""
import os
import sys


def main():
    """Punto de entrada principal para ejecutar comandos administrativos."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se ha podido importar Django. ¿Está instalado y disponible en "
            "la variable de entorno PYTHONPATH? ¿Olvidaste activar el entorno "
            "virtual?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
