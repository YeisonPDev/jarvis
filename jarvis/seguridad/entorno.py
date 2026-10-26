"""Comprobaciones del entorno de ejecución."""

import ctypes


def es_administrador() -> bool:
    """True si el proceso tiene permisos de administrador."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False
