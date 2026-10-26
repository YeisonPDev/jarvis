"""Búsqueda de información en internet con la herramienta integrada "browser_search" de Groq.

La búsqueda la hace Groq en sus servidores: Jarvis no navega ni descarga páginas.
El texto obtenido de la web se entrega al modelo principal marcado como DATOS NO
CONFIABLES (puede contener instrucciones escondidas).
"""

from __future__ import annotations

import re
from datetime import datetime

import openai

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, error, esquema_objeto, exito

URL_GROQ = "https://api.groq.com/openai/v1"
MAX_CONSULTA = 300
MAX_FUENTES = 5
_INSTRUCCIONES = (
    "Hoy es {fecha}. Investiga en la web y responde en {idioma} con los datos MÁS RECIENTES que "
    "encuentres (no supongas años de memoria), en un máximo de 8 frases. Incluye fechas o cifras "
    "cuando importen. Si no encuentras algo, dilo."
)


def limpiar_citas(texto: str) -> str:
    """Quita marcas de cita como 【1†L18-L20】."""
    return re.sub(r"\s*【[^】]*】", "", texto or "").strip()


def extraer_fuentes(herramientas_ejecutadas) -> list[str]:
    fuentes: list[str] = []
    for h in herramientas_ejecutadas or []:
        salida = h.get("output", "") if isinstance(h, dict) else ""
        for url in re.findall(r"URL:\s*(https?://\S+)", salida or ""):
            url = url.rstrip(").,]")
            if "exa.ai/search" in url or url in fuentes:
                continue
            fuentes.append(url)
    return fuentes[:MAX_FUENTES]


def buscar_informacion(ctx: Contexto, args: dict) -> Resultado:
    consulta = args["consulta"].strip()
    llave = ctx.config.busqueda_api_key
    if not llave:
        return error("Para buscar información en internet hace falta una llave de Groq "
                     "(JARVIS_API_KEY con el proveedor groq, o JARVIS_GROQ_API_KEY en .env).")
    cliente = openai.OpenAI(base_url=URL_GROQ, api_key=llave, max_retries=1)
    try:
        respuesta = cliente.chat.completions.create(
            model=ctx.config.busqueda_modelo,
            messages=[
                {"role": "system", "content": _INSTRUCCIONES.format(
                    idioma=ctx.config.idioma_nombre, fecha=datetime.now().strftime("%d/%m/%Y"))},
                {"role": "user", "content": consulta},
            ],
            tools=[{"type": "browser_search"}],
            tool_choice="required",
            temperature=0.3,
            max_completion_tokens=1200,
            extra_body={"reasoning_effort": "low"},
            timeout=40,
        )
    except openai.RateLimitError:
        return error("Se alcanzó el límite de búsquedas gratuitas de Groq. Intenta en unos minutos "
                     "o usa buscar_en_web para abrir la búsqueda en el navegador.")
    except (openai.AuthenticationError, openai.PermissionDeniedError):
        return error("La llave de Groq para búsquedas no es válida.")
    except openai.APITimeoutError:
        return error("La búsqueda en internet tardó demasiado.")
    except openai.APIConnectionError:
        return error("No hay conexión a internet.")
    except openai.APIStatusError as e:
        return error(f"El servicio de búsqueda respondió con un error ({e.status_code}).")

    if not respuesta.choices:
        return error("La búsqueda no devolvió resultados.")
    mensaje = respuesta.choices[0].message
    texto = limpiar_citas(mensaje.content)
    if not texto:
        return error("La búsqueda no devolvió resultados.")
    fuentes = extraer_fuentes((mensaje.model_extra or {}).get("executed_tools"))
    if fuentes:
        texto += "\nFuentes: " + ", ".join(fuentes)
    return exito(f"Resultado de buscar en internet: '{consulta}'.", texto, origen="búsqueda web")


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "buscar_informacion",
            "Busca información actual en internet (noticias, datos, precios, resultados) y devuelve "
            "un resumen con fuentes.",
            esquema_objeto({
                "consulta": {"type": "string", "maxLength": MAX_CONSULTA},
            }, ["consulta"]),
            buscar_informacion,
            lee_externo=True,
        ),
    ]
