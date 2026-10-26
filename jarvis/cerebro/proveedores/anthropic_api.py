"""Adaptador para la API de Anthropic (Claude). Se activa con JARVIS_PROVIDER=anthropic."""

from __future__ import annotations

import json

from jarvis.cerebro.errores import (
    ErrorAutenticacion, ErrorConexion, ErrorConfiguracion, ErrorLimiteUso, ErrorProveedor,
    ErrorTiempoAgotado,
)
from jarvis.cerebro.proveedores.base import LlamadaHerramienta, Proveedor, RespuestaModelo

MAX_TOKENS = 1024


def convertir_mensajes(mensajes: list[dict]) -> tuple[str, list[dict]]:
    """Convierte el formato interno al de Anthropic: (system, messages)."""
    sistema: list[str] = []
    salida: list[dict] = []

    def agregar(rol: str, bloques: list[dict]) -> None:
        # Anthropic exige alternar roles: se fusionan mensajes consecutivos del mismo rol.
        if salida and salida[-1]["role"] == rol:
            salida[-1]["content"].extend(bloques)
        else:
            salida.append({"role": rol, "content": list(bloques)})

    for m in mensajes:
        rol = m["role"]
        if rol == "system":
            sistema.append(m["content"])
        elif rol == "user":
            agregar("user", [{"type": "text", "text": m["content"]}])
        elif rol == "assistant":
            bloques: list[dict] = []
            if m.get("content"):
                bloques.append({"type": "text", "text": m["content"]})
            for t in m.get("tool_calls") or []:
                try:
                    entrada = json.loads(t["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    entrada = {}
                if not isinstance(entrada, dict):
                    entrada = {}
                bloques.append({"type": "tool_use", "id": t["id"], "name": t["function"]["name"], "input": entrada})
            if bloques:
                agregar("assistant", bloques)
        elif rol == "tool":
            agregar("user", [{"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}])
    return "\n\n".join(sistema), salida


class ProveedorAnthropic(Proveedor):
    def __init__(self, api_key: str, modelo: str, base_url: str = ""):
        try:
            import anthropic
        except ImportError as e:
            raise ErrorConfiguracion("Falta el paquete 'anthropic'. Instálalo con pip.") from e
        self._sdk = anthropic
        self.nombre = "Anthropic"
        self.modelo = modelo
        opciones = {"api_key": api_key, "max_retries": 0}
        if base_url:
            opciones["base_url"] = base_url
        self._cliente = anthropic.Anthropic(**opciones)

    def completar(self, mensajes, herramientas, tiempo_limite) -> RespuestaModelo:
        sdk = self._sdk
        sistema, convertidos = convertir_mensajes(mensajes)
        tools = [
            {"name": h["nombre"], "description": h["descripcion"], "input_schema": h["parametros"]}
            for h in herramientas
        ]
        try:
            respuesta = self._cliente.messages.create(
                model=self.modelo,
                max_tokens=MAX_TOKENS,
                system=sistema,
                messages=convertidos,
                tools=tools,
                timeout=max(1.0, tiempo_limite),
            )
        except sdk.APITimeoutError:
            raise ErrorTiempoAgotado() from None
        except sdk.APIConnectionError:
            raise ErrorConexion(self.nombre) from None
        except sdk.RateLimitError as e:
            espera = None
            try:
                espera = float(e.response.headers.get("retry-after"))
            except (AttributeError, TypeError, ValueError):
                pass
            raise ErrorLimiteUso(self.nombre, espera) from None
        except (sdk.AuthenticationError, sdk.PermissionDeniedError):
            raise ErrorAutenticacion(self.nombre) from None
        except sdk.NotFoundError:
            raise ErrorConfiguracion(f"El modelo '{self.modelo}' no existe en Anthropic.") from None
        except sdk.APIStatusError as e:
            raise ErrorProveedor(f"Anthropic respondió con un error ({e.status_code}).") from None

        textos, llamadas = [], []
        for bloque in respuesta.content:
            if bloque.type == "text":
                textos.append(bloque.text)
            elif bloque.type == "tool_use":
                llamadas.append(LlamadaHerramienta(bloque.id, bloque.name, json.dumps(bloque.input, ensure_ascii=False)))
        return RespuestaModelo(texto="\n".join(textos).strip(), llamadas=llamadas)
