"""Interfaz común de proveedores.

Formato interno de mensajes (estilo OpenAI, cada adaptador lo convierte):
  {"role": "system" | "user", "content": str}
  {"role": "assistant", "content": str | None, "tool_calls": [{"id", "type": "function",
                                                              "function": {"name", "arguments"}}]}
  {"role": "tool", "tool_call_id": str, "content": str}

Herramientas: lista de {"nombre", "descripcion", "parametros" (JSON Schema)}.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LlamadaHerramienta:
    id: str
    nombre: str
    argumentos: str  # JSON en texto, tal como lo generó el modelo


@dataclass
class RespuestaModelo:
    texto: str = ""
    llamadas: list[LlamadaHerramienta] = field(default_factory=list)


def limpiar_pensamiento(texto: str | None) -> str:
    """Quita bloques <think>...</think> que algunos modelos (qwen3) incluyen en la respuesta."""
    if not texto:
        return ""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    texto = re.sub(r"^.*?</think>", "", texto, flags=re.DOTALL)  # bloque sin apertura
    return texto.strip()


class Proveedor(ABC):
    nombre: str = "proveedor"
    modelo: str = ""

    @abstractmethod
    def completar(self, mensajes: list[dict], herramientas: list[dict], tiempo_limite: float) -> RespuestaModelo:
        """Envía la conversación y devuelve texto o llamadas a herramientas.

        Debe traducir los errores del SDK a las excepciones de jarvis.cerebro.errores.
        """
