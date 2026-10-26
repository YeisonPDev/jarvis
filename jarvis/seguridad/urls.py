"""Validación de URLs: solo http y https."""

from __future__ import annotations

import re
from urllib.parse import quote, urlsplit

from jarvis.seguridad.errores import ErrorSeguridad

ESQUEMAS_PERMITIDOS = {"http", "https"}


def validar_url(url: object) -> str:
    """Devuelve la URL limpia o lanza ErrorSeguridad."""
    if not isinstance(url, str) or not url.strip():
        raise ErrorSeguridad("La URL está vacía.")
    url = url.strip()
    if any(ord(c) < 33 or c in '"<>\\^`{|}' for c in url):
        raise ErrorSeguridad("La URL contiene espacios o caracteres no válidos.")
    if len(url) > 2000:
        raise ErrorSeguridad("La URL es demasiado larga.")

    # Si el usuario escribió "google.com" sin esquema, se asume https.
    if "://" not in url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", url):
        url = "https://" + url

    partes = urlsplit(url)
    esquema = partes.scheme.lower()
    if esquema not in ESQUEMAS_PERMITIDOS:
        raise ErrorSeguridad(
            f"Esquema '{esquema or '(ninguno)'}:' no permitido. Solo se abren direcciones http y https."
        )
    if not partes.hostname:
        raise ErrorSeguridad("La URL no tiene un dominio válido.")
    if partes.username or partes.password:
        raise ErrorSeguridad("No se permiten URLs con usuario o contraseña incluidos.")
    return url


def _forma_comparable(texto: str) -> str:
    t = texto.strip().lower()
    t = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", t)
    if t.startswith("www."):
        t = t[4:]
    return t.rstrip("/")


def url_escrita_por_usuario(url: str, pedido: str) -> bool:
    """True si la URL (sin esquema ni 'www.') aparece textualmente en el pedido del usuario."""
    objetivo = _forma_comparable(url)
    if not objetivo:
        return False
    texto = pedido.lower()
    texto = re.sub(r"[a-z][a-z0-9+.\-]*://", "", texto).replace("www.", "")
    return objetivo in texto


def codificar_consulta(consulta: str) -> str:
    return quote(consulta.strip(), safe="")
