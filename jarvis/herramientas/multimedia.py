"""Música (teclas multimedia), volumen (pycaw) y brillo (screen-brightness-control)."""

from __future__ import annotations

import ctypes
import time

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, error, esquema_objeto, exito

_VK = {"play_pausa": 0xB3, "siguiente": 0xB0, "anterior": 0xB1}
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002
PASO_POR_DEFECTO = 10


def _pulsar_tecla(vk: int) -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY, 0)
    time.sleep(0.03)
    user32.keybd_event(vk, 0, _KEYEVENTF_EXTENDEDKEY | _KEYEVENTF_KEYUP, 0)


def control_musica(ctx: Contexto, args: dict) -> Resultado:
    accion = args["accion"]
    _pulsar_tecla(_VK[accion])
    textos = {"play_pausa": "Reproducir/pausar enviado.", "siguiente": "Siguiente canción.", "anterior": "Canción anterior."}
    return exito(textos[accion])


# ---------------------------------------------------------------------- #
def _con_volumen(funcion):
    """Ejecuta 'funcion(endpoint)' con COM inicializado en este hilo."""
    import comtypes
    from pycaw.pycaw import AudioUtilities

    comtypes.CoInitialize()
    try:
        dispositivo = AudioUtilities.GetSpeakers()
        endpoint = getattr(dispositivo, "EndpointVolume", None)
        if endpoint is None:  # versiones antiguas de pycaw
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import IAudioEndpointVolume

            interfaz = dispositivo.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            endpoint = cast(interfaz, POINTER(IAudioEndpointVolume))
        try:
            return funcion(endpoint)
        finally:
            del endpoint, dispositivo
    finally:
        comtypes.CoUninitialize()


def volumen(ctx: Contexto, args: dict) -> Resultado:
    accion = args["accion"]
    valor = args.get("valor_opcional")
    if accion == "establecer" and valor is None:
        return error("Para 'establecer' indica valor_opcional entre 0 y 100.")

    def operar(ep) -> str:
        actual = round(ep.GetMasterVolumeLevelScalar() * 100)
        if accion == "consultar":
            silencio = " (silenciado)" if ep.GetMute() else ""
            return f"El volumen está en {actual}%{silencio}."
        if accion == "silenciar":
            ep.SetMute(1, None)
            return "Sonido silenciado."
        if accion == "activar":
            ep.SetMute(0, None)
            return f"Sonido activado ({actual}%)."
        paso = PASO_POR_DEFECTO if valor is None else valor
        nuevo = {"subir": actual + paso, "bajar": actual - paso, "establecer": valor}[accion]
        nuevo = max(0, min(100, int(nuevo)))
        ep.SetMasterVolumeLevelScalar(nuevo / 100, None)
        if nuevo > 0 and ep.GetMute():
            ep.SetMute(0, None)
        return f"Volumen en {nuevo}%."

    try:
        return exito(_con_volumen(operar))
    except OSError:
        return error("No encontré un dispositivo de audio activo.")


# ---------------------------------------------------------------------- #
def brillo(ctx: Contexto, args: dict) -> Resultado:
    accion = args["accion"]
    valor = args.get("valor_opcional")
    if accion == "establecer" and valor is None:
        return error("Para 'establecer' indica valor_opcional entre 0 y 100.")
    try:
        import screen_brightness_control as sbc

        lecturas = sbc.get_brightness(display=0)
        actual = int(lecturas[0] if isinstance(lecturas, list) else lecturas)
        if accion == "consultar":
            return exito(f"El brillo está en {actual}%.")
        paso = PASO_POR_DEFECTO if valor is None else valor
        nuevo = {"subir": actual + paso, "bajar": actual - paso, "establecer": valor}[accion]
        nuevo = max(0, min(100, int(nuevo)))
        sbc.set_brightness(nuevo, display=0)
        return exito(f"Brillo en {nuevo}%.")
    except Exception:  # noqa: BLE001 - muchos monitores externos no lo permiten
        return error(
            "Este monitor no permite controlar el brillo desde Windows "
            "(es común en monitores externos). Úsalo desde los botones del monitor."
        )


# ---------------------------------------------------------------------- #
def herramientas() -> list[Herramienta]:
    valor = {"type": "integer", "minimum": 0, "maximum": 100, "description": "% o paso (10 por defecto)"}
    return [
        Herramienta(
            "control_musica",
            "Controla la música que se esté reproduciendo con las teclas multimedia.",
            esquema_objeto({
                "accion": {"type": "string", "enum": ["play_pausa", "siguiente", "anterior"]},
            }, ["accion"]),
            control_musica,
        ),
        Herramienta(
            "volumen",
            "Consulta o cambia el volumen del sistema.",
            esquema_objeto({
                "accion": {"type": "string", "enum": ["subir", "bajar", "establecer", "silenciar", "activar", "consultar"]},
                "valor_opcional": valor,
            }, ["accion"]),
            volumen,
        ),
        Herramienta(
            "brillo",
            "Consulta o cambia el brillo de la pantalla principal.",
            esquema_objeto({
                "accion": {"type": "string", "enum": ["subir", "bajar", "establecer", "consultar"]},
                "valor_opcional": valor,
            }, ["accion"]),
            brillo,
        ),
    ]
