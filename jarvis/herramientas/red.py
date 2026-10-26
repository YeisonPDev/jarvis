"""Peticiones HTTP de solo lectura a servicios fijos (clima). Con límite de tiempo y de tamaño."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jarvis.seguridad.errores import ErrorSeguridad

MAX_BYTES = 2_000_000
AGENTE = "Jarvis/0.1 (asistente de escritorio)"


def obtener_json(url_base: str, parametros: dict, timeout: float = 12) -> dict:
    """GET a una URL https fija del código. Lanza ErrorSeguridad con un mensaje claro si falla."""
    if not url_base.startswith("https://"):
        raise ErrorSeguridad("Solo se permiten servicios https.")
    url = url_base + "?" + urlencode(parametros)
    try:
        with urlopen(Request(url, headers={"User-Agent": AGENTE}), timeout=timeout) as r:  # noqa: S310
            datos = r.read(MAX_BYTES + 1)
    except HTTPError as e:
        raise ErrorSeguridad(f"El servicio respondió con un error ({e.code}).") from None
    except (URLError, TimeoutError, OSError):
        raise ErrorSeguridad("No hay conexión a internet o el servicio no responde.") from None
    if len(datos) > MAX_BYTES:
        raise ErrorSeguridad("La respuesta del servicio es demasiado grande.")
    try:
        resultado = json.loads(datos)
    except ValueError:
        raise ErrorSeguridad("El servicio devolvió datos no válidos.") from None
    if not isinstance(resultado, dict):
        raise ErrorSeguridad("El servicio devolvió datos no válidos.")
    return resultado
