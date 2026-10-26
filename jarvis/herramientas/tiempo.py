"""Fecha y hora (local o de otra zona) y clima con Open-Meteo (gratis, sin llave)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, error, esquema_objeto, exito
from jarvis.herramientas.red import obtener_json
from jarvis.seguridad.lista_negra import normalizar_texto

URL_GEOCODIFICACION = "https://geocoding-api.open-meteo.com/v1/search"
URL_PRONOSTICO = "https://api.open-meteo.com/v1/forecast"

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]

# Códigos de tiempo WMO usados por Open-Meteo
_CLIMA = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "niebla", 48: "niebla con escarcha", 51: "llovizna ligera", 53: "llovizna", 55: "llovizna intensa",
    56: "llovizna helada", 57: "llovizna helada intensa", 61: "lluvia ligera", 63: "lluvia",
    65: "lluvia fuerte", 66: "lluvia helada", 67: "lluvia helada fuerte", 71: "nevada ligera",
    73: "nevada", 75: "nevada fuerte", 77: "granizo fino", 80: "chubascos ligeros", 81: "chubascos",
    82: "chubascos fuertes", 85: "chubascos de nieve", 86: "chubascos de nieve fuertes",
    95: "tormenta eléctrica", 96: "tormenta con granizo", 99: "tormenta fuerte con granizo",
}


def fecha_legible(momento: datetime) -> str:
    return (f"{_DIAS[momento.weekday()]} {momento.day} de {_MESES[momento.month - 1]} de "
            f"{momento.year}, {momento:%H:%M}")


def fecha_hora(ctx: Contexto, args: dict) -> Resultado:
    zona = (args.get("zona_horaria") or "").strip()
    if not zona:
        ahora = datetime.now().astimezone()
        return exito(f"Ahora es {fecha_legible(ahora)} (hora local, UTC{ahora:%z}).")
    try:
        ahora = datetime.now(ZoneInfo(zona))
    except (ZoneInfoNotFoundError, ValueError):
        return error(f"No conozco la zona horaria '{zona}'. Usa nombres IANA como "
                     "'America/Bogota', 'Europe/Madrid' o 'Asia/Tokyo'.")
    return exito(f"En {zona} es {fecha_legible(ahora)} (UTC{ahora:%z}).")


# ---------------------------------------------------------------------- #
def _buscar_lugares(nombre: str) -> list[dict]:
    datos = obtener_json(URL_GEOCODIFICACION, {"name": nombre, "count": 10, "language": "es", "format": "json"})
    return datos.get("results") or []


def _coincide_region(lugar: dict, region: str) -> bool:
    texto = normalizar_texto(f"{lugar.get('country', '')} {lugar.get('admin1', '')} {lugar.get('country_code', '')}")
    return normalizar_texto(region).strip() in texto


def _ubicar(ciudad: str) -> dict:
    """Busca la ciudad. Acepta 'Ciudad, Región o País' y también sin coma ('bucaramanga santander')."""
    if "," in ciudad:
        nombre, _, region = (p.strip() for p in ciudad.partition(","))
        intentos = [(nombre, region)]
    else:
        # Sin coma no se sabe dónde termina el nombre: se prueban los cortes posibles,
        # del nombre más largo al más corto, y se exige que el resto coincida con región o país.
        palabras = ciudad.split()
        intentos = [(" ".join(palabras[:i]), " ".join(palabras[i:])) for i in range(len(palabras) - 1, 0, -1)]
        intentos.append((ciudad, ""))
    primero = None
    for nombre, region in intentos:
        resultados = _buscar_lugares(nombre)
        if not resultados:
            continue
        if region:
            for lugar in resultados:
                if _coincide_region(lugar, region):
                    return lugar
            primero = primero or (resultados[0] if "," in ciudad else None)
        else:
            return resultados[0]  # vienen ordenados por población
    if primero:
        return primero
    raise LookupError(ciudad)


def consultar_clima(ctx: Contexto, args: dict) -> Resultado:
    ciudad = (args.get("ciudad") or ctx.config.ciudad or "").strip()
    if not ciudad:
        return error("No sé de qué ciudad quiere el clima. Pregúntale al usuario, o que configure "
                     "su ciudad en los ajustes de Jarvis.")
    dias = int(args.get("dias") or 1)
    try:
        lugar = _ubicar(ciudad)
    except LookupError:
        return error(f"No encontré la ciudad '{ciudad}'. Prueba con otro nombre o agrega el país.")

    datos = obtener_json(URL_PRONOSTICO, {
        "latitude": lugar["latitude"], "longitude": lugar["longitude"],
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto", "forecast_days": dias,
    })
    nombre = ", ".join(x for x in (lugar.get("name"), lugar.get("admin1"), lugar.get("country")) if x)
    actual = datos.get("current") or {}
    lineas = [f"Clima en {nombre}:"]
    if actual:
        lineas.append(
            f"Ahora: {_CLIMA.get(actual.get('weather_code'), 'condición desconocida')}, "
            f"{actual.get('temperature_2m')} °C (sensación {actual.get('apparent_temperature')} °C), "
            f"humedad {actual.get('relative_humidity_2m')} %, viento {actual.get('wind_speed_10m')} km/h, "
            f"precipitación {actual.get('precipitation')} mm."
        )
    diario = datos.get("daily") or {}
    for i, fecha in enumerate(diario.get("time") or []):
        try:
            dia = datetime.strptime(fecha, "%Y-%m-%d")
            etiqueta = "Hoy" if i == 0 else f"{_DIAS[dia.weekday()].capitalize()} {dia.day}"
            lineas.append(
                f"{etiqueta}: {_CLIMA.get(diario['weather_code'][i], '?')}, "
                f"mín {diario['temperature_2m_min'][i]} °C, máx {diario['temperature_2m_max'][i]} °C, "
                f"probabilidad de lluvia {diario['precipitation_probability_max'][i]} %."
            )
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return exito("\n".join(lineas))


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "fecha_hora",
            "Fecha y hora actual, local o de otra zona horaria.",
            esquema_objeto({
                "zona_horaria": {"type": "string", "maxLength": 60,
                                 "description": "IANA, ej.: 'Asia/Tokyo'"},
            }),
            fecha_hora,
        ),
        Herramienta(
            "consultar_clima",
            "Clima actual y pronóstico. Sin ciudad, usa la de los ajustes.",
            esquema_objeto({
                "ciudad": {"type": "string", "maxLength": 100, "description": "Ej.: 'Madrid, España'"},
                "dias": {"type": "integer", "minimum": 1, "maximum": 7},
            }),
            consultar_clima,
        ),
    ]
