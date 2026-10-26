"""Abre la ventana de ajustes de Jarvis (voz, velocidad, idioma). Solo cuando el usuario lo pide."""

from __future__ import annotations

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, error, esquema_objeto, exito


def abrir_ajustes(ctx: Contexto, args: dict) -> Resultado:
    if ctx.interfaz is None or not hasattr(ctx.interfaz, "solicitar_ajustes"):
        return error("La ventana de ajustes no está disponible en este momento.")
    ctx.interfaz.solicitar_ajustes()  # señal hacia el hilo de la interfaz
    return exito("Abrí la ventana de ajustes. Ahí el usuario puede cambiar el motor de voz, "
                 "la voz, la velocidad y el idioma.")


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "abrir_ajustes",
            "Abre los ajustes de Jarvis (voz, velocidad, idioma, apariencia, ciudad, tiempo antes de ocultarse). Solo si el usuario lo pide.",
            esquema_objeto({}),
            abrir_ajustes,
        ),
    ]
