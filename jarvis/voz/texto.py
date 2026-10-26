"""Prepara el texto de las respuestas para que suene natural al leerlo en voz alta."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

AVISO_RECORTE = " El resto está en pantalla."

_URL = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
# Rutas de Windows como C:\Users\Ana\Mis Documentos\informe.docx: las carpetas pueden
# tener espacios (terminan en "\"); el nombre final termina en el primer espacio.
_RUTA = re.compile(r"[A-Za-z]:\\(?:[^\\\n\"<>|?*:]+\\)*[^\\\s\"<>|?*:,;]*")
_EMOJIS = re.compile("[\u2600-\u27BF\U0001F000-\U0001FAFF\uFE0F]")


def _dominio(coincidencia: re.Match) -> str:
    try:
        host = urlsplit(coincidencia.group(0)).hostname or "el enlace"
    except ValueError:
        return "el enlace"
    return host[4:] if host.startswith("www.") else host


def _nombre_final(coincidencia: re.Match) -> str:
    ruta = coincidencia.group(0).rstrip("\\")
    nombre = ruta.rsplit("\\", 1)[-1]
    return nombre or ruta


def preparar_texto_para_voz(texto: str, max_caracteres: int = 1500) -> str:
    """Quita símbolos que suenan mal, acorta rutas y URLs, y limita la longitud."""
    if not texto:
        return ""
    t = _URL.sub(_dominio, texto)
    t = _RUTA.sub(_nombre_final, t)
    t = _EMOJIS.sub("", t)
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL)  # bloques de código
    t = re.sub(r"[*_`#>|~]+", " ", t)  # marcas de Markdown
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.MULTILINE)  # viñetas
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", ". ", t.strip())  # cada línea, una pausa
    t = re.sub(r"([.!?:;])\s*\.(\s|$)", r"\1\2", t)  # evita ".." por saltos de línea
    t = re.sub(r"\s+", " ", t).strip()

    if max_caracteres and len(t) > max_caracteres:
        corte = t[:max_caracteres]
        fin_frase = max(corte.rfind(". "), corte.rfind("? "), corte.rfind("! "))
        if fin_frase > max_caracteres * 0.5:
            corte = corte[: fin_frase + 1]
        t = corte.rstrip() + AVISO_RECORTE
    return t
