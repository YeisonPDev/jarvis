"""Proveedor compatible con la API de OpenAI: Groq, Ollama y otros servicios similares."""

from __future__ import annotations

import re

import openai

from jarvis.cerebro.errores import (
    ErrorAutenticacion, ErrorConexion, ErrorConfiguracion, ErrorHerramientaMalFormada,
    ErrorLimiteUso, ErrorProveedor, ErrorTiempoAgotado,
)
from jarvis.cerebro.proveedores.base import (
    LlamadaHerramienta, Proveedor, RespuestaModelo, limpiar_pensamiento,
)


def _segundos_reintento(error: openai.APIStatusError) -> float | None:
    """Lee el tiempo de espera de la cabecera Retry-After o del mensaje ('try again in 7m12s')."""
    try:
        cabecera = error.response.headers.get("retry-after")
        if cabecera:
            return float(cabecera)
    except (AttributeError, ValueError):
        pass
    coincidencia = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", str(error))
    if coincidencia and any(coincidencia.groups()):
        h, m, s = coincidencia.groups()
        return int(h or 0) * 3600 + int(m or 0) * 60 + float(s or 0)
    return None


class ProveedorOpenAICompatible(Proveedor):
    def __init__(self, nombre: str, base_url: str, api_key: str, modelo: str,
                 esfuerzo_razonamiento: str = ""):
        self.nombre = nombre
        self.modelo = modelo
        self.esfuerzo_razonamiento = esfuerzo_razonamiento  # "low", "medium" o "high"
        self.base_url = base_url
        # max_retries=0: los reintentos los controla el agente (respeta cancelación y tiempo límite).
        self._cliente = openai.OpenAI(base_url=base_url, api_key=api_key or "sin-llave", max_retries=0)

    def completar(self, mensajes, herramientas, tiempo_limite) -> RespuestaModelo:
        tools = [
            {"type": "function", "function": {
                "name": h["nombre"], "description": h["descripcion"], "parameters": h["parametros"],
            }}
            for h in herramientas
        ]
        opciones: dict = {
            "model": self.modelo,
            "messages": mensajes,
            "temperature": 0.2,
            "timeout": max(1.0, tiempo_limite),
        }
        if tools:
            opciones["tools"] = tools
            opciones["tool_choice"] = "auto"
        if self.esfuerzo_razonamiento and "gpt-oss" in self.modelo:
            # Menos "pensamiento" = menos tokens por minuto y respuestas más rápidas.
            opciones["extra_body"] = {"reasoning_effort": self.esfuerzo_razonamiento}
        try:
            respuesta = self._cliente.chat.completions.create(**opciones)
        except openai.APITimeoutError:
            raise ErrorTiempoAgotado() from None
        except openai.APIConnectionError:
            raise ErrorConexion(self.nombre, self.base_url) from None
        except openai.RateLimitError as e:
            raise ErrorLimiteUso(self.nombre, _segundos_reintento(e)) from None
        except openai.AuthenticationError:
            raise ErrorAutenticacion(self.nombre) from None
        except openai.PermissionDeniedError:
            raise ErrorAutenticacion(self.nombre) from None
        except openai.NotFoundError:
            raise ErrorConfiguracion(
                f"El modelo '{self.modelo}' no existe en {self.nombre}. Revisa JARVIS_MODEL en .env."
            ) from None
        except openai.BadRequestError as e:
            cuerpo = e.body if isinstance(e.body, dict) else {}
            info = cuerpo.get("error", cuerpo) if isinstance(cuerpo, dict) else {}
            codigo = str(info.get("code", "")) if isinstance(info, dict) else ""
            if codigo == "tool_use_failed" or (isinstance(info, dict) and "failed_generation" in info):
                generado = str(info.get("failed_generation", ""))[:500] if isinstance(info, dict) else ""
                raise ErrorHerramientaMalFormada(generado) from None
            if "does not support tools" in str(e).lower():
                raise ErrorConfiguracion(
                    f"El modelo '{self.modelo}' no admite herramientas. Elige otro en JARVIS_MODEL."
                ) from None
            raise ErrorProveedor(f"{self.nombre} rechazó la solicitud (error 400).") from None
        except openai.APIStatusError as e:
            raise ErrorProveedor(
                f"{self.nombre} respondió con un error ({e.status_code}). Intenta de nuevo en un momento."
            ) from None

        if not respuesta.choices:
            raise ErrorProveedor(f"{self.nombre} devolvió una respuesta vacía.")
        mensaje = respuesta.choices[0].message
        llamadas = [
            LlamadaHerramienta(id=t.id, nombre=t.function.name, argumentos=t.function.arguments or "{}")
            for t in (mensaje.tool_calls or [])
            if getattr(t, "function", None)
        ]
        return RespuestaModelo(texto=limpiar_pensamiento(mensaje.content), llamadas=llamadas)
