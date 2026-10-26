"""Ejecuta el agente en un hilo aparte y comunica todo a la interfaz mediante señales."""

from __future__ import annotations

import json
import threading

from PySide6.QtCore import QObject, Signal

from jarvis import registro
from jarvis.cerebro.errores import ErrorCancelado, ErrorJarvis


def _texto_argumentos(argumentos: dict) -> str:
    vista = {}
    for k, v in argumentos.items():
        if isinstance(v, str) and len(v) > 80:
            v = v[:80] + "…"
        vista[k] = v
    return json.dumps(vista, ensure_ascii=False)


class Trabajador(QObject):
    """Implementa el Observador del agente. Las señales cruzan de hilo de forma segura."""

    estado = Signal(str)
    herramienta = Signal(str, str)
    aviso = Signal(str)
    pedir_confirmacion = Signal(str)
    terminado = Signal(str)
    fallo = Signal(str)
    cancelado = Signal()

    def __init__(self, agente, pedido: str):
        super().__init__()
        self.agente = agente
        self.pedido = pedido
        self.cancelar = threading.Event()
        self._evento_confirmacion = threading.Event()
        self._respuesta_confirmacion = False

    def iniciar(self) -> None:
        threading.Thread(target=self._ejecutar, daemon=True, name="jarvis-agente").start()

    def detener(self) -> None:
        self.cancelar.set()
        self._evento_confirmacion.set()

    def _ejecutar(self) -> None:
        try:
            texto = self.agente.procesar(self.pedido, self, self.cancelar)
            if self.cancelar.is_set():
                self.cancelado.emit()
            else:
                self.terminado.emit(texto)
        except ErrorCancelado:
            self.cancelado.emit()
        except ErrorJarvis as e:
            self.fallo.emit(e.mensaje_usuario)
        except Exception as e:  # noqa: BLE001
            registro.general().error("Error inesperado en el agente: %s", type(e).__name__)
            self.fallo.emit("Ocurrió un error inesperado. Revisa el registro de Jarvis.")

    # --- Observador ---------------------------------------------------- #
    def al_cambiar_estado(self, estado: str) -> None:
        self.estado.emit(estado)

    def al_usar_herramienta(self, nombre: str, argumentos: dict) -> None:
        self.herramienta.emit(nombre, _texto_argumentos(argumentos))

    def al_informar(self, texto: str) -> None:
        self.aviso.emit(texto)

    def confirmar(self, pregunta: str) -> bool:
        self._respuesta_confirmacion = False
        self._evento_confirmacion.clear()
        self.pedir_confirmacion.emit(pregunta)
        while not self._evento_confirmacion.wait(0.1):
            if self.cancelar.is_set():
                return False
        return self._respuesta_confirmacion and not self.cancelar.is_set()

    def responder_confirmacion(self, aprobado: bool) -> None:
        self._respuesta_confirmacion = aprobado
        self._evento_confirmacion.set()
