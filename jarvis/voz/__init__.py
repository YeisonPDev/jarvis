"""Entrada y salida de voz."""

import os

from jarvis import registro
from jarvis.voz.base import EntradaVoz, SalidaVoz, SalidaVozNula

__all__ = ["EntradaVoz", "SalidaVoz", "SalidaVozNula", "crear_salida_voz"]


def crear_salida_voz(config) -> SalidaVoz:
    """Crea la voz según config.voz.motor. La voz de Windows siempre queda como respaldo."""
    from jarvis.voz.windows import SalidaVozWindows

    voz = config.voz
    windows = SalidaVozWindows(
        voz_preferida=voz.nombre,
        velocidad=voz.velocidad,
        volumen=voz.volumen,
        max_caracteres=voz.max_caracteres,
        idioma=config.idioma_codigo,
    )
    respaldo = windows if windows.disponible else None
    temporal = os.path.join(config.carpeta_datos, "voz")
    motor = voz.motor.strip().lower()

    if motor == "piper":
        from jarvis.voz.piper_voz import SalidaVozPiper, esta_descargada

        if esta_descargada(config.carpeta_voces_piper, voz.piper_voz):
            return SalidaVozPiper(
                carpeta_voces=config.carpeta_voces_piper,
                clave=voz.piper_voz,
                carpeta_temporal=temporal,
                velocidad=voz.velocidad,
                max_caracteres=voz.max_caracteres,
                respaldo=respaldo,
            )
        registro.general().warning(
            "La voz de Piper '%s' no está descargada; uso la voz de Windows.", voz.piper_voz
        )

    elif motor == "openai":
        if config.tts_api_key:
            from jarvis.voz.openai_voz import SalidaVozOpenAI

            return SalidaVozOpenAI(
                api_key=config.tts_api_key,
                carpeta_temporal=temporal,
                modelo=voz.openai_modelo,
                voz=voz.openai_voz,
                instrucciones=config.instrucciones_voz(),
                base_url=config.tts_base_url,
                max_caracteres=voz.max_caracteres,
                respaldo=respaldo,
            )
        registro.general().warning("Falta JARVIS_TTS_API_KEY en .env; uso la voz de Windows.")

    return respaldo or SalidaVozNula()
