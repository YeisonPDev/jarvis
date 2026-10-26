"""Interfaces de voz.

El agente solo recibe y devuelve texto. La voz se conecta en la interfaz:
  - Salida (texto → voz): VentanaJarvis llama a hablar() con cada respuesta y a
    detener() al cancelar, escribir un pedido nuevo u ocultarse.
  - Entrada (voz → texto, futuro): implementar EntradaVoz (por ejemplo con Whisper de
    Groq: whisper-large-v3-turbo) y pasar el texto a VentanaJarvis.enviar_pedido(texto).
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable


class EntradaVoz(ABC):
    """Voz → texto."""

    @abstractmethod
    def escuchar(self, cancelar: threading.Event) -> str:
        """Graba hasta que el usuario deja de hablar y devuelve la transcripción."""


class SalidaVoz(ABC):
    """Texto → voz."""

    # Se llama (desde otro hilo) cuando termina de hablar. Recibe True si terminó
    # de forma natural y False si fue interrumpida.
    al_terminar: Callable[[bool], None] | None = None
    disponible: bool = False
    nombre_voz: str = ""

    @abstractmethod
    def hablar(self, texto: str) -> None:
        """No bloqueante. Si ya estaba hablando, corta lo anterior y empieza lo nuevo."""

    @abstractmethod
    def detener(self) -> None:
        """Corta la reproducción en curso."""

    @property
    def hablando(self) -> bool:
        return False

    def cerrar(self) -> None:
        """Libera recursos al salir de la aplicación."""
        self.detener()


class SalidaVozNula(SalidaVoz):
    """Implementación vacía, usada si la voz está desactivada o no hay voces instaladas."""

    def hablar(self, texto: str) -> None:
        pass

    def detener(self) -> None:
        pass
