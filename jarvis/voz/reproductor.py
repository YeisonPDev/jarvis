"""Reproductor común para motores que generan audio (Piper, OpenAI).

- Divide el texto en frases: mientras suena una, se genera la siguiente.
- Se puede cortar en cualquier momento (Esc, pedido nuevo, ocultar).
- Si el motor falla, el resto se lee con la voz de respaldo (Windows).
"""

from __future__ import annotations

import glob
import os
import queue
import re
import threading
import time
import uuid
import wave
import winsound
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TiempoFuturo

from jarvis import registro
from jarvis.voz.base import SalidaVoz
from jarvis.voz.texto import preparar_texto_para_voz

MAX_FRAGMENTO = 300


class Interrumpido(Exception):
    """La lectura se cortó porque llegó otro texto o se pidió detener."""


class ErrorPermanente(Exception):
    """Error que no se arregla reintentando (llave inválida, modelo inexistente...)."""


def dividir_en_fragmentos(texto: str, maximo: int = MAX_FRAGMENTO) -> list[str]:
    """Divide en frases completas; las frases muy largas se cortan en comas o espacios."""
    frases = re.split(r"(?<=[.!?…])\s+", texto.strip())
    fragmentos: list[str] = []
    actual = ""
    for numero, frase in enumerate(frases):
        if numero == 1 and actual:
            # La primera frase va sola: así empieza a sonar lo antes posible.
            fragmentos.append(actual)
            actual = ""
        while len(frase) > maximo:
            corte = max(frase.rfind(", ", 0, maximo), frase.rfind(" ", 0, maximo))
            corte = corte if corte > maximo // 3 else maximo
            if actual:
                fragmentos.append(actual)
                actual = ""
            fragmentos.append(frase[:corte + 1].strip())
            frase = frase[corte + 1:].strip()
        if not frase:
            continue
        if actual and len(actual) + 1 + len(frase) > maximo:
            fragmentos.append(actual)
            actual = frase
        else:
            actual = f"{actual} {frase}".strip()
    if actual:
        fragmentos.append(actual)
    return [f for f in fragmentos if f]


class SalidaVozFragmentada(SalidaVoz):
    """Base para motores que devuelven audio PCM de 16 bits mono."""

    nombre_motor = "motor"

    def __init__(self, carpeta_temporal: str, max_caracteres: int = 1500,
                 respaldo: SalidaVoz | None = None):
        self.max_caracteres = int(max_caracteres)
        self.respaldo = respaldo
        self.al_terminar = None
        self.disponible = True
        self._motor_habilitado = True

        self._carpeta = carpeta_temporal
        os.makedirs(self._carpeta, exist_ok=True)
        for viejo in glob.glob(os.path.join(self._carpeta, "voz_*.wav")):
            try:
                os.remove(viejo)
            except OSError:
                pass

        if respaldo is not None:
            respaldo.al_terminar = self._reenviar_fin
        self._cola: queue.Queue = queue.Queue()
        self._generacion = 0
        self._hablando = False
        threading.Thread(target=self._bucle, daemon=True, name=f"jarvis-voz-{self.nombre_motor}").start()

    # --- Lo que implementa cada motor ---------------------------------- #
    def preparar(self) -> None:
        """Se ejecuta una vez en el hilo de voz antes de hablar (p. ej. cargar el modelo)."""

    @abstractmethod
    def sintetizar(self, texto: str, generacion: int) -> tuple[bytes, int]:
        """Devuelve (audio PCM 16 bits mono, frecuencia de muestreo).

        Debe lanzar Interrumpido si generacion != self._generacion durante el proceso,
        y ErrorPermanente si el problema no se arregla reintentando.
        """

    # --- Interfaz SalidaVoz -------------------------------------------- #
    @property
    def hablando(self) -> bool:
        return self._hablando or bool(self.respaldo and self.respaldo.hablando)

    def hablar(self, texto: str) -> None:
        texto = preparar_texto_para_voz(texto, self.max_caracteres)
        if not texto:
            return
        self.detener()
        if not self._motor_habilitado:
            if self.respaldo:
                self.respaldo.hablar(texto)
            return
        self._cola.put((self._generacion, texto))

    def detener(self) -> None:
        try:
            while True:
                self._cola.get_nowait()
        except queue.Empty:
            pass
        self._generacion += 1
        try:
            winsound.PlaySound(None, 0)  # corta el audio en curso
        except RuntimeError:
            pass
        if self.respaldo:
            self.respaldo.detener()

    def cerrar(self) -> None:
        self.detener()
        self._cola.put(None)
        if self.respaldo:
            self.respaldo.cerrar()

    def _reenviar_fin(self, natural: bool) -> None:
        if self.al_terminar:
            self.al_terminar(natural)

    # --- Hilo de voz ---------------------------------------------------- #
    def _bucle(self) -> None:
        try:
            self.preparar()
        except Exception as e:  # noqa: BLE001
            self._desactivar(e)
        while True:
            elemento = self._cola.get()
            if elemento is None:
                break
            generacion, texto = elemento
            if generacion != self._generacion:
                continue
            if not self._motor_habilitado:
                self._usar_respaldo(texto)
                continue
            self._hablando = True
            try:
                natural = self._reproducir(generacion, texto)
            except Exception as e:  # noqa: BLE001
                registro.general().warning("Error en la voz %s: %s", self.nombre_motor, type(e).__name__)
                natural = False
            finally:
                self._hablando = False
            # None: el respaldo tomó el control y avisará él al terminar.
            if natural is not None and self.al_terminar and self._cola.empty():
                try:
                    self.al_terminar(natural)
                except Exception:  # noqa: BLE001
                    pass

    def _reproducir(self, generacion: int, texto: str) -> bool | None:
        fragmentos = dividir_en_fragmentos(texto)
        ejecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"jarvis-{self.nombre_motor}")
        try:
            futuro = ejecutor.submit(self.sintetizar, fragmentos[0], generacion)
            for i in range(len(fragmentos)):
                try:
                    audio, frecuencia = self._esperar(futuro, generacion)
                except Interrumpido:
                    return False
                except Exception as e:  # noqa: BLE001 - cualquier falla: pasar al respaldo
                    if isinstance(e, ErrorPermanente):
                        self._desactivar(e)
                    else:
                        registro.general().warning("Voz %s no disponible (%s); uso la de respaldo.",
                                                   self.nombre_motor, type(e).__name__)
                    return self._usar_respaldo(" ".join(fragmentos[i:]))
                if i + 1 < len(fragmentos):
                    futuro = ejecutor.submit(self.sintetizar, fragmentos[i + 1], generacion)
                if not self._tocar(audio, frecuencia, generacion):
                    return False
            return True
        finally:
            ejecutor.shutdown(wait=False, cancel_futures=True)

    def _desactivar(self, error: Exception) -> None:
        self._motor_habilitado = False  # no insistir en esta sesión
        registro.general().warning("Voz %s desactivada en esta sesión: %s", self.nombre_motor, error)

    def _usar_respaldo(self, texto: str) -> bool | None:
        if self.respaldo and self.respaldo.disponible:
            self.respaldo.hablar(texto)
            return None
        return False

    def _esperar(self, futuro, generacion: int):
        while True:
            if generacion != self._generacion:
                raise Interrumpido()
            try:
                return futuro.result(timeout=0.1)
            except TiempoFuturo:
                continue

    def _tocar(self, pcm: bytes, frecuencia: int, generacion: int) -> bool:
        if not pcm:
            return True
        ruta = os.path.join(self._carpeta, f"voz_{uuid.uuid4().hex}.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(frecuencia)
            w.writeframes(pcm)
        duracion = len(pcm) / (frecuencia * 2)
        try:
            winsound.PlaySound(ruta, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            fin = time.monotonic() + duracion + 0.1
            while time.monotonic() < fin:
                if generacion != self._generacion:
                    winsound.PlaySound(None, 0)
                    return False
                time.sleep(0.04)
            return True
        finally:
            try:
                os.remove(ruta)
            except OSError:
                pass  # se limpia al próximo inicio
