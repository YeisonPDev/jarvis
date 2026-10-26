"""Voz de Windows (SAPI) sin internet: el texto nunca sale del equipo.

Incluye las voces "OneCore" (las más naturales de Windows 10/11, p. ej. Microsoft Raul)
además de las voces de escritorio clásicas.
"""

from __future__ import annotations

import math
import queue
import threading

from jarvis import registro
from jarvis.seguridad.lista_negra import normalizar_texto
from jarvis.voz.base import SalidaVoz
from jarvis.voz.texto import preparar_texto_para_voz

_CATEGORIAS = (
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices",
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices",
)
SVSF_ASINCRONO = 1
SVSF_PURGAR = 2
SVSF_NO_XML = 16  # el texto no se interpreta como marcado SSML/XML


# Idioma principal de cada LCID de Windows (los 10 bits bajos).
_LCID_PRINCIPAL = {
    "ar": 0x01, "ca": 0x03, "zh": 0x04, "cs": 0x05, "da": 0x06, "de": 0x07, "el": 0x08,
    "en": 0x09, "es": 0x0A, "fi": 0x0B, "fr": 0x0C, "hu": 0x0E, "it": 0x10, "ja": 0x11,
    "ko": 0x12, "nl": 0x13, "nb": 0x14, "no": 0x14, "pl": 0x15, "pt": 0x16, "ro": 0x18,
    "ru": 0x19, "sv": 0x1D, "tr": 0x1F, "uk": 0x22, "vi": 0x2A, "hi": 0x39,
}


def es_del_idioma(idioma_sapi: str, codigo: str = "es") -> bool:
    """El atributo 'Language' de SAPI es una lista de LCID en hexadecimal (p. ej. '80A')."""
    buscado = _LCID_PRINCIPAL.get(codigo[:2].lower())
    if buscado is None:
        return False
    for lcid in idioma_sapi.replace(";", " ").split():
        try:
            if int(lcid, 16) & 0x3FF == buscado:
                return True
        except ValueError:
            continue
    return False


def velocidad_a_rate(velocidad: float) -> int:
    """Convierte el multiplicador (0.5x–2x) a la escala de SAPI (-10 a 10, ~3x en los extremos)."""
    velocidad = max(0.3, min(3.0, float(velocidad)))
    return max(-10, min(10, round(10 * math.log(velocidad) / math.log(3))))


def elegir_voz(voces: list[tuple[str, str]], preferida: str, idioma: str = "es") -> int | None:
    """voces: lista de (descripción, idioma SAPI). Devuelve el índice elegido o None.

    Orden: la preferida por nombre → cualquiera del idioma → la primera.
    """
    if not voces:
        return None
    buscada = normalizar_texto(preferida or "").strip()
    if buscada:
        for i, (descripcion, _) in enumerate(voces):
            if buscada in normalizar_texto(descripcion):
                return i
    for i, (_, idioma_sapi) in enumerate(voces):
        if es_del_idioma(idioma_sapi, idioma):
            return i
    return 0


def _enumerar_fichas(cc) -> list[tuple[object, str, str]]:
    """(ficha, descripción, idioma) de las voces OneCore y de escritorio, sin repetir."""
    fichas, vistas = [], set()
    for categoria in _CATEGORIAS:
        try:
            cat = cc.CreateObject("SAPI.SpObjectTokenCategory", dynamic=True)
            cat.SetId(categoria, False)
            lista = cat.EnumerateTokens()
            for i in range(lista.Count):
                ficha = lista.Item(i)
                descripcion = ficha.GetDescription()
                if descripcion in vistas:
                    continue
                vistas.add(descripcion)
                try:
                    idioma = ficha.GetAttribute("Language")
                except Exception:  # noqa: BLE001
                    idioma = ""
                fichas.append((ficha, descripcion, idioma))
        except Exception:  # noqa: BLE001 - la categoría puede no existir
            continue
    return fichas


def listar_voces_windows() -> list[tuple[str, str]]:
    """Voces de Windows instaladas: lista de (descripción, idioma SAPI)."""
    import comtypes
    import comtypes.client as cc

    comtypes.CoInitialize()
    try:
        return [(d, i) for _, d, i in _enumerar_fichas(cc)]
    except Exception:  # noqa: BLE001
        return []
    finally:
        comtypes.CoUninitialize()


class SalidaVozWindows(SalidaVoz):
    def __init__(self, voz_preferida: str = "Raul", velocidad: float = 1.0, volumen: int = 100,
                 max_caracteres: int = 1500, idioma: str = "es"):
        self.voz_preferida = voz_preferida
        self.idioma = idioma
        self.velocidad = velocidad_a_rate(velocidad)
        self.volumen = max(0, min(100, int(volumen)))
        self.max_caracteres = int(max_caracteres)
        self.al_terminar = None
        self.disponible = False
        self.nombre_voz = ""

        self._cola: queue.Queue = queue.Queue()
        self._generacion = 0
        self._hablando = False
        self._listo = threading.Event()
        self._hilo = threading.Thread(target=self._bucle, daemon=True, name="jarvis-voz")
        self._hilo.start()
        self._listo.wait(8)

    @property
    def hablando(self) -> bool:
        return self._hablando

    def hablar(self, texto: str) -> None:
        texto = preparar_texto_para_voz(texto, self.max_caracteres)
        if not texto or not self.disponible:
            return
        self._vaciar_cola()
        self._generacion += 1  # interrumpe lo que esté sonando
        self._cola.put((self._generacion, texto))

    def detener(self) -> None:
        self._vaciar_cola()
        self._generacion += 1

    def cerrar(self) -> None:
        self.detener()
        self._cola.put(None)

    def _vaciar_cola(self) -> None:
        try:
            while True:
                self._cola.get_nowait()
        except queue.Empty:
            pass

    # ------------------------------------------------------------------ #
    def _crear_voz(self):
        import comtypes.client as cc

        voz = cc.CreateObject("SAPI.SpVoice", dynamic=True)
        fichas = _enumerar_fichas(cc)
        indice = elegir_voz([(d, i) for _, d, i in fichas], self.voz_preferida, self.idioma)
        if indice is not None:
            try:
                voz.Voice = fichas[indice][0]
            except Exception:  # noqa: BLE001 - si falla, queda la voz predeterminada
                pass
        voz.Rate = self.velocidad
        voz.Volume = self.volumen
        self.nombre_voz = voz.Voice.GetDescription()
        return voz

    def _bucle(self) -> None:
        import comtypes

        comtypes.CoInitialize()  # COM debe inicializarse en el hilo que lo usa
        try:
            try:
                voz = self._crear_voz()
                self.disponible = True
            except Exception as e:  # noqa: BLE001
                registro.general().warning("Voz no disponible: %s", type(e).__name__)
                return
            finally:
                self._listo.set()

            while True:
                elemento = self._cola.get()
                if elemento is None:
                    break
                generacion, texto = elemento
                if generacion != self._generacion:
                    continue
                self._hablando = True
                natural = True
                try:
                    voz.Speak(texto, SVSF_ASINCRONO | SVSF_PURGAR | SVSF_NO_XML)
                    while not voz.WaitUntilDone(80):
                        if generacion != self._generacion:
                            voz.Speak("", SVSF_ASINCRONO | SVSF_PURGAR)  # corta en seco
                            natural = False
                            break
                except Exception as e:  # noqa: BLE001
                    natural = False
                    registro.general().warning("Error al hablar: %s", type(e).__name__)
                finally:
                    self._hablando = False
                if self.al_terminar and self._cola.empty():
                    try:
                        self.al_terminar(natural)
                    except Exception:  # noqa: BLE001
                        pass
        finally:
            comtypes.CoUninitialize()
