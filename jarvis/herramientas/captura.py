"""Captura de pantalla guardada en la carpeta de salida de Jarvis."""

from __future__ import annotations

import os
from datetime import datetime

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, esquema_objeto, exito
from jarvis.herramientas.creacion import preparar_carpeta_salida


def tomar_captura(ctx: Contexto, args: dict) -> Resultado:
    from PIL import ImageGrab

    carpeta = os.path.join(preparar_carpeta_salida(ctx), "Capturas")
    os.makedirs(carpeta, exist_ok=True)
    carpeta = ctx.validador.validar(carpeta, tipo="carpeta")

    imagen = ImageGrab.grab(all_screens=True)
    base = f"captura_{datetime.now():%Y%m%d_%H%M%S}"
    for i in range(1, 100):
        ruta = os.path.join(carpeta, f"{base}{'' if i == 1 else f'_{i}'}.png")
        try:
            with open(ruta, "xb") as f:  # nunca sobrescribe
                imagen.save(f, format="PNG")
            return exito(f"Captura guardada en {ruta}")
        except FileExistsError:
            continue
    return exito("No encontré un nombre libre para la captura.")


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "tomar_captura",
            "Toma una captura de toda la pantalla y la guarda en Documentos\\Jarvis\\Capturas.",
            esquema_objeto({}),
            tomar_captura,
        ),
    ]
