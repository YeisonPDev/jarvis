"""Crea el proveedor según JARVIS_PROVIDER, con valores por defecto para cada uno."""

from __future__ import annotations

import os

from jarvis.cerebro.errores import ErrorConfiguracion
from jarvis.cerebro.proveedores.base import Proveedor

VALORES_POR_DEFECTO = {
    # Modelo estable (producción) de Groq con soporte de herramientas.
    "groq": {"base_url": "https://api.groq.com/openai/v1", "modelo": "openai/gpt-oss-120b", "nombre": "Groq"},
    "ollama": {"base_url": "http://localhost:11434/v1", "modelo": "qwen3:4b", "nombre": "Ollama"},
    "anthropic": {"base_url": "", "modelo": "claude-sonnet-5-5", "nombre": "Anthropic"},
    "openai": {"base_url": "https://api.openai.com/v1", "modelo": "", "nombre": "OpenAI"},
}


def crear_proveedor(config) -> Proveedor:
    clave = config.proveedor
    if clave not in VALORES_POR_DEFECTO:
        raise ErrorConfiguracion(
            f"Proveedor '{clave}' desconocido. Usa: {', '.join(VALORES_POR_DEFECTO)}."
        )
    defecto = VALORES_POR_DEFECTO[clave]
    modelo = config.modelo or defecto["modelo"]
    base_url = config.base_url or defecto["base_url"]
    if not modelo:
        raise ErrorConfiguracion("Falta JARVIS_MODEL en el archivo .env.")

    if clave == "anthropic":
        if not config.api_key:
            raise ErrorConfiguracion("Falta JARVIS_API_KEY en el archivo .env para usar Anthropic.")
        from jarvis.cerebro.proveedores.anthropic_api import ProveedorAnthropic

        return ProveedorAnthropic(config.api_key, modelo, config.base_url)

    if clave != "ollama" and not config.api_key:
        raise ErrorConfiguracion(
            f"Falta JARVIS_API_KEY en el archivo .env para usar {defecto['nombre']}."
        )
    from jarvis.cerebro.proveedores.openai_compat import ProveedorOpenAICompatible

    esfuerzo = os.getenv("JARVIS_REASONING_EFFORT", "low").strip().lower()
    if esfuerzo not in ("low", "medium", "high"):
        esfuerzo = "low"
    return ProveedorOpenAICompatible(
        defecto["nombre"], base_url, config.api_key or "ollama", modelo,
        esfuerzo_razonamiento=esfuerzo if clave == "groq" else "",
    )
