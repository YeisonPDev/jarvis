"""Voz de OpenAI (por ejemplo "onyx"). Requiere JARVIS_TTS_API_KEY y conexión a internet."""

from __future__ import annotations

import openai

from jarvis.voz.base import SalidaVoz
from jarvis.voz.reproductor import ErrorPermanente, Interrumpido, SalidaVozFragmentada

FRECUENCIA = 24000  # el formato "pcm" de OpenAI es 24 kHz, 16 bits, mono
VOCES_OPENAI = ["onyx", "ash", "echo", "fable", "alloy", "ballad", "cedar", "coral", "marin",
                "nova", "sage", "shimmer", "verse"]


class SalidaVozOpenAI(SalidaVozFragmentada):
    nombre_motor = "OpenAI"

    def __init__(self, api_key: str, carpeta_temporal: str, modelo: str = "gpt-4o-mini-tts",
                 voz: str = "onyx", instrucciones: str = "", base_url: str = "",
                 max_caracteres: int = 1500, respaldo: SalidaVoz | None = None):
        self.modelo = modelo
        self.voz = voz
        self.instrucciones = instrucciones
        self.nombre_voz = f"OpenAI {voz}" + (f" (respaldo: {respaldo.nombre_voz})" if respaldo else "")
        opciones = {"api_key": api_key, "max_retries": 1}
        if base_url:
            opciones["base_url"] = base_url
        self._cliente = openai.OpenAI(**opciones)
        super().__init__(carpeta_temporal, max_caracteres, respaldo)

    def sintetizar(self, texto: str, generacion: int) -> tuple[bytes, int]:
        datos = bytearray()
        try:
            with self._cliente.audio.speech.with_streaming_response.create(
                model=self.modelo,
                voice=self.voz,
                input=texto,
                instructions=self.instrucciones or openai.omit,
                response_format="pcm",
                timeout=30,
            ) as respuesta:
                for trozo in respuesta.iter_bytes(16384):
                    if generacion != self._generacion:
                        raise Interrumpido()
                    datos += trozo
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise ErrorPermanente("la llave JARVIS_TTS_API_KEY no es válida") from e
        except openai.NotFoundError as e:
            raise ErrorPermanente(f"el modelo '{self.modelo}' no existe o fue retirado") from e
        except openai.BadRequestError as e:
            raise ErrorPermanente(f"OpenAI rechazó la configuración de voz ({self.voz}/{self.modelo})") from e
        return bytes(datos), FRECUENCIA
