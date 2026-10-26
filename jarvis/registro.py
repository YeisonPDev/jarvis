"""Logs locales con rotación diaria y borrado automático a los 30 días.

Se guarda solo: fecha, pedido, herramienta, argumentos y éxito.
Nunca el contenido de archivos leídos ni la API key.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

DIAS_RETENCION = 30
MAX_LARGO_ARGUMENTO = 200

_registro_acciones = logging.getLogger("jarvis.acciones")
_registro_general = logging.getLogger("jarvis")
_secretos: list[str] = []


class _FiltroSecretos(logging.Filter):
    """Reemplaza cualquier secreto conocido (API key) por asteriscos."""

    def filter(self, record: logging.LogRecord) -> bool:
        if _secretos:
            mensaje = record.getMessage()
            for s in _secretos:
                if s and s in mensaje:
                    mensaje = mensaje.replace(s, "****")
            record.msg, record.args = mensaje, None
        return True


def limpiar_logs_antiguos(carpeta: str, dias: int = DIAS_RETENCION) -> int:
    """Borra archivos de log con más de 'dias' de antigüedad. Devuelve cuántos borró."""
    if not os.path.isdir(carpeta):
        return 0
    limite = time.time() - dias * 86400
    borrados = 0
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        if nombre.startswith(("acciones.log", "jarvis.log")) and os.path.isfile(ruta):
            try:
                if os.path.getmtime(ruta) < limite:
                    os.remove(ruta)
                    borrados += 1
            except OSError:
                pass
    return borrados


def configurar(carpeta_datos: str, secretos: list[str] | None = None) -> str:
    carpeta = os.path.join(carpeta_datos, "logs")
    os.makedirs(carpeta, exist_ok=True)
    _secretos[:] = [s for s in (secretos or []) if s]
    limpiar_logs_antiguos(carpeta)

    filtro = _FiltroSecretos()
    for logger, archivo, formato in (
        (_registro_acciones, "acciones.log", "%(message)s"),
        (_registro_general, "jarvis.log", "%(asctime)s %(levelname)s %(name)s: %(message)s"),
    ):
        manejador = TimedRotatingFileHandler(
            os.path.join(carpeta, archivo), when="midnight",
            backupCount=DIAS_RETENCION, encoding="utf-8",
        )
        manejador.setFormatter(logging.Formatter(formato))
        manejador.addFilter(filtro)
        logger.handlers.clear()
        logger.addHandler(manejador)
        logger.setLevel(logging.INFO)
    _registro_acciones.propagate = False
    return carpeta


def _recortar(valor):
    if isinstance(valor, str) and len(valor) > MAX_LARGO_ARGUMENTO:
        return valor[:MAX_LARGO_ARGUMENTO] + f"… ({len(valor)} caracteres)"
    return valor


def registrar_accion(pedido: str, herramienta: str, argumentos: object, exito: bool) -> None:
    if isinstance(argumentos, dict):
        argumentos = {k: _recortar(v) for k, v in argumentos.items()}
    else:
        argumentos = _recortar(str(argumentos))
    _registro_acciones.info(json.dumps({
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "pedido": _recortar(pedido),
        "herramienta": herramienta,
        "argumentos": argumentos,
        "exito": bool(exito),
    }, ensure_ascii=False))


def general() -> logging.Logger:
    return _registro_general
