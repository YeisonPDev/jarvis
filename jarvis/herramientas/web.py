"""Internet: solo abre direcciones en el navegador predeterminado. No descarga ni lee páginas."""

from __future__ import annotations

import os
import webbrowser
import winreg

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, esquema_objeto, exito
from jarvis.seguridad.errores import ErrorSeguridad
from jarvis.seguridad.urls import codificar_consulta, url_escrita_por_usuario, validar_url

MAX_CONSULTA = 300


def _abrir_en_navegador(url: str) -> None:
    url = validar_url(url)  # doble verificación justo antes de abrir
    webbrowser.open(url, new=2)


def _consulta_valida(consulta: str) -> str:
    consulta = consulta.strip()
    if not consulta:
        raise ErrorSeguridad("La búsqueda está vacía.")
    return consulta


def buscar_en_web(ctx: Contexto, args: dict) -> Resultado:
    consulta = _consulta_valida(args["consulta"])
    _abrir_en_navegador(ctx.config.motor_busqueda + codificar_consulta(consulta))
    return exito(f"Abrí la búsqueda de '{consulta}' en el navegador.")


def abrir_pagina(ctx: Contexto, args: dict) -> Resultado:
    url = validar_url(args["url"])
    _abrir_en_navegador(url)
    return exito(f"Abrí {url} en el navegador.")


def _confirmar_pagina(ctx: Contexto, args: dict) -> str | None:
    try:
        url = validar_url(args["url"])
    except ErrorSeguridad:
        return None
    if url_escrita_por_usuario(url, ctx.pedido):
        return None
    return f"¿Abrir esta dirección? No la escribiste en tu pedido:\n{url}"


def spotify_instalado() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "spotify"):
            return True
    except OSError:
        return False


def buscar_musica(ctx: Contexto, args: dict) -> Resultado:
    consulta = _consulta_valida(args["consulta"])
    codificada = codificar_consulta(consulta)
    if spotify_instalado():
        os.startfile(f"spotify:search:{codificada}")  # noqa: S606 - esquema fijo de Spotify
        return exito(f"Busqué '{consulta}' en Spotify.")
    _abrir_en_navegador(f"https://www.youtube.com/results?search_query={codificada}")
    return exito(f"Spotify no está instalado; abrí la búsqueda de '{consulta}' en YouTube.")


def herramientas() -> list[Herramienta]:
    consulta = {"type": "string", "description": "Texto a buscar.", "maxLength": MAX_CONSULTA}
    return [
        Herramienta(
            "buscar_en_web",
            "Abre en el navegador una búsqueda web. No lee los resultados.",
            esquema_objeto({"consulta": consulta}, ["consulta"]),
            buscar_en_web,
        ),
        Herramienta(
            "abrir_pagina",
            "Abre una dirección http o https en el navegador. No lee su contenido.",
            esquema_objeto({"url": {"type": "string", "maxLength": 2000}}, ["url"]),
            abrir_pagina,
            confirmacion=_confirmar_pagina,
        ),
        Herramienta(
            "buscar_musica",
            "Busca una canción, artista o álbum en Spotify (si está instalado) o en YouTube.",
            esquema_objeto({"consulta": consulta}, ["consulta"]),
            buscar_musica,
        ),
    ]
