"""Ventana de Jarvis con estilo "isla dinámica": una píldora de vidrio esmerilado arriba al
centro con el cubo Rubik y el campo de comando. Crece hacia abajo para mostrar respuestas y
confirmaciones, y se desvanece sola tras un tiempo sin actividad.
"""

from __future__ import annotations

import ctypes

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPalette, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout,
    QWidget,
)

from jarvis.interfaz.cubo import CuboRubik
from jarvis.interfaz.vidrio import FondoVidrio
from jarvis.interfaz.trabajador import Trabajador
from jarvis.voz.base import SalidaVoz, SalidaVozNula

ANCHO = 400
ALTO_PILDORA = 42
RADIO = 21
MARGEN_SUPERIOR = 8
ALTO_MAX_RESPUESTA = 110  # más que esto, se desplaza con la rueda
ALTO_MAX_ISLA = 330  # zona que se captura para el vidrio
DURACION_APARECER = 320
DURACION_DESVANECER = 450
DURACION_REDIMENSION = 200

ESTILO = """
#isla { background: transparent; border: none; }
QLineEdit {
    background: transparent;
    color: #ffffff;
    border: none;
    font-size: 14px;
    padding: 0 2px;
    selection-background-color: #0a84ff;
}
QTextBrowser {
    background: transparent;
    color: #f2f2f7;
    border: none;
    font-size: 12px;
}
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 60); border-radius: 3px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
#herramienta { color: #64d2ff; font-size: 10px; font-family: Consolas, monospace; }
#aviso { color: #a1a1a6; font-size: 10px; }
#pregunta { color: #ffffff; font-size: 12px; }
QPushButton {
    color: #ffffff; border: none; border-radius: 13px; font-size: 12px;
    background-color: transparent; min-width: 26px; min-height: 26px; padding: 0 6px;
}
QPushButton:hover { background-color: rgba(255, 255, 255, 30); }
QPushButton#si { background-color: #0a84ff; padding: 0 14px; }
QPushButton#si:hover { background-color: #3a9bff; }
QPushButton#no { background-color: rgba(60, 60, 62, 200); padding: 0 14px; }
QPushButton#no:hover { background-color: #3a3a3c; }
QPushButton#cancelar { color: #ff6b6b; font-size: 14px; }
"""


class VentanaJarvis(QWidget):
    voz_terminada = Signal(bool)  # emitida desde el hilo de voz; Qt la entrega en el hilo principal
    voz_cambiada = Signal(bool)  # para sincronizar el menú de la bandeja

    def __init__(self, agente, config, salida_voz: SalidaVoz | None = None):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,  # Tool: sin barra de tareas
        )
        self.agente = agente
        self.config = config
        self.salida_voz = salida_voz or SalidaVozNula()
        self.voz_activada = bool(config.voz.activada and self.salida_voz.disponible)
        self._trabajador: Trabajador | None = None
        self._ocultando = False

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Jarvis")
        self.setStyleSheet(ESTILO)
        self.vidrio = FondoVidrio(
            self, RADIO, opacidad=config.opacidad_fondo, desenfoque=config.desenfoque,
            zona_captura=self._zona_vidrio,
        )
        self._construir()

        # Animaciones: tamaño (geometría) y opacidad
        self._anim_geometria = QPropertyAnimation(self, b"geometry", self)
        self._anim_opacidad = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim_opacidad.finished.connect(self._al_terminar_opacidad)

        # Se desvanece sola tras un tiempo sin actividad
        self._inactividad = QTimer(self)
        self._inactividad.setSingleShot(True)
        self._inactividad.timeout.connect(self._al_inactividad)
        self._temporizador_estado = QTimer(self)
        self._temporizador_estado.setSingleShot(True)
        self._temporizador_estado.timeout.connect(lambda: self.circulo.establecer_estado("espera"))

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._al_presionar_esc)

        self.salida_voz.al_terminar = self.voz_terminada.emit
        self.voz_terminada.connect(self._al_terminar_voz)
        self._actualizar_boton_voz()

    # ------------------------------------------------------------------ #
    def _construir(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSizeConstraint(QLayout.SetNoConstraint)  # el tamaño lo controlan las animaciones

        self.isla = QFrame(objectName="isla")
        caja = QVBoxLayout(self.isla)
        caja.setContentsMargins(9, 7, 10, 7)
        caja.setSpacing(4)

        # Fila principal: ícono azul + campo de comando + botones
        fila = QHBoxLayout()
        fila.setSpacing(6)
        self.circulo = CuboRubik(tamano=24)  # logo: cubo Rubik
        fila.addWidget(self.circulo)

        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Pregúntale a Jarvis…")
        self.entrada.setMaxLength(2000)
        paleta = self.entrada.palette()
        paleta.setColor(QPalette.PlaceholderText, QColor(142, 142, 147))
        self.entrada.setPalette(paleta)
        self.entrada.returnPressed.connect(self._enviar_desde_caja)
        self.entrada.textEdited.connect(lambda _: self._reiniciar_inactividad())
        fila.addWidget(self.entrada, 1)

        self.boton_voz = QPushButton(objectName="voz")
        self.boton_voz.setFocusPolicy(Qt.NoFocus)
        self.boton_voz.clicked.connect(lambda: self.establecer_voz(not self.voz_activada))
        fila.addWidget(self.boton_voz)

        self.boton_cancelar = QPushButton("✕", objectName="cancelar")
        self.boton_cancelar.setToolTip("Cancelar el pedido (Esc)")
        self.boton_cancelar.setFocusPolicy(Qt.NoFocus)
        self.boton_cancelar.clicked.connect(self.cancelar)
        self.boton_cancelar.hide()
        fila.addWidget(self.boton_cancelar)
        caja.addLayout(fila)

        # Cuerpo expandible: herramienta, respuesta, confirmación y avisos
        self.cuerpo = QWidget()
        cuerpo = QVBoxLayout(self.cuerpo)
        cuerpo.setContentsMargins(8, 0, 4, 4)
        cuerpo.setSpacing(4)

        self.etiqueta_herramienta = QLabel(objectName="herramienta")
        self.etiqueta_herramienta.hide()
        cuerpo.addWidget(self.etiqueta_herramienta)

        self.respuesta = QTextBrowser()
        self.respuesta.setOpenLinks(False)
        self.respuesta.setOpenExternalLinks(False)
        self.respuesta.setFocusPolicy(Qt.NoFocus)
        self.respuesta.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.respuesta.document().setDocumentMargin(2)
        self.respuesta.hide()
        cuerpo.addWidget(self.respuesta)

        self.confirmacion = QWidget()
        conf = QVBoxLayout(self.confirmacion)
        conf.setContentsMargins(0, 2, 0, 0)
        conf.setSpacing(8)
        self.pregunta = QLabel(objectName="pregunta")
        self.pregunta.setWordWrap(True)
        conf.addWidget(self.pregunta)
        botones = QHBoxLayout()
        botones.addStretch(1)
        self.boton_no = QPushButton("No", objectName="no")
        self.boton_si = QPushButton("Sí", objectName="si")
        self.boton_no.clicked.connect(lambda: self._responder_confirmacion(False))
        self.boton_si.clicked.connect(lambda: self._responder_confirmacion(True))
        botones.addWidget(self.boton_no)
        botones.addWidget(self.boton_si)
        conf.addLayout(botones)
        self.confirmacion.hide()
        cuerpo.addWidget(self.confirmacion)

        self.aviso = QLabel(objectName="aviso")
        self.aviso.hide()
        cuerpo.addWidget(self.aviso)

        self.cuerpo.hide()
        caja.addWidget(self.cuerpo)
        raiz.addWidget(self.isla)

    # ------------------------------------------------------------------ #
    # Geometría
    # ------------------------------------------------------------------ #
    def _area(self) -> QRect:
        pantalla = QGuiApplication.primaryScreen()
        return pantalla.availableGeometry() if pantalla else QRect(0, 0, 1280, 720)

    def _alto_objetivo(self) -> int:
        visibles = [w for w in (self.etiqueta_herramienta, self.respuesta, self.confirmacion, self.aviso)
                    if not w.isHidden()]
        self.cuerpo.setVisible(bool(visibles))
        if not visibles:
            return ALTO_PILDORA
        # Se suma a mano: el sizeHint de QTextBrowser ignora su altura fija e inflaría la isla.
        caja = self.isla.layout().contentsMargins()
        cuerpo = self.cuerpo.layout()
        margenes = cuerpo.contentsMargins()
        ancho_util = ANCHO - caja.left() - caja.right() - margenes.left() - margenes.right()
        alto = margenes.top() + margenes.bottom() + cuerpo.spacing() * (len(visibles) - 1)
        for w in visibles:
            if w is self.respuesta:
                doc = self.respuesta.document()
                doc.setTextWidth(ancho_util - 8)  # deja lugar a la barra de desplazamiento
                h = max(20, min(int(doc.size().height()) + 4, ALTO_MAX_RESPUESTA))
                self.respuesta.setFixedHeight(h)
            elif w.layout() is not None and w.layout().hasHeightForWidth():
                h = w.layout().heightForWidth(ancho_util)
            elif w.hasHeightForWidth():
                h = w.heightForWidth(ancho_util)
            else:
                h = w.sizeHint().height()
            alto += h
        return ALTO_PILDORA + self.isla.layout().spacing() + alto

    def _rect_objetivo(self, ancho: int | None = None, alto: int | None = None) -> QRect:
        area = self._area()
        ancho = ancho or ANCHO
        alto = alto or self._alto_objetivo()
        x = area.x() + (area.width() - ancho) // 2
        return QRect(x, area.y() + MARGEN_SUPERIOR, ancho, alto)

    def _animar_geometria(self, destino: QRect, duracion: int, curva: QEasingCurve.Type) -> None:
        self._anim_geometria.stop()
        self._anim_geometria.setDuration(duracion)
        self._anim_geometria.setEasingCurve(curva)
        self._anim_geometria.setStartValue(self.geometry())
        self._anim_geometria.setEndValue(destino)
        self._anim_geometria.start()

    def _ajustar_tamano(self) -> None:
        if not self.isVisible() or self._ocultando:
            return
        destino = self._rect_objetivo()
        if destino != self.geometry():
            self._animar_geometria(destino, DURACION_REDIMENSION, QEasingCurve.OutCubic)

    # ------------------------------------------------------------------ #
    # Mostrar / ocultar
    # ------------------------------------------------------------------ #
    def alternar(self) -> None:
        if self.isVisible() and not self._ocultando:
            self.ocultar()
        else:
            self.mostrar()

    def mostrar(self) -> None:
        aparecer = not self.isVisible() or self._ocultando
        self._ocultando = False
        if not self.isVisible():
            # Empieza como una píldora pequeña y se expande, como una isla dinámica.
            self.setWindowOpacity(0.0)
            self.setGeometry(self._rect_objetivo(ancho=ALTO_PILDORA * 2, alto=ALTO_PILDORA))
            self.show()
        self.raise_()
        self.activateWindow()
        try:
            # El proceso recibió la tecla, así que Windows le permite pasar al frente.
            ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
        except (AttributeError, OSError):
            pass
        self.entrada.setFocus()
        if aparecer:
            curva = QEasingCurve(QEasingCurve.OutBack)
            curva.setOvershoot(0.9)
            self._anim_geometria.stop()
            self._anim_geometria.setDuration(DURACION_APARECER)
            self._anim_geometria.setEasingCurve(curva)
            self._anim_geometria.setStartValue(self.geometry())
            self._anim_geometria.setEndValue(self._rect_objetivo())
            self._anim_geometria.start()
            self._animar_opacidad(1.0, DURACION_APARECER // 2)
        self._reiniciar_inactividad()

    def ocultar(self) -> None:
        if not self.isVisible() or self._ocultando:
            return
        if self._trabajador is not None:
            self.cancelar(silencioso=True)
        self._inactividad.stop()
        self.salida_voz.detener()
        self._ocultando = True
        # Se encoge hacia una píldora pequeña mientras se desvanece.
        self._animar_geometria(
            self._rect_objetivo(ancho=ALTO_PILDORA * 2, alto=ALTO_PILDORA),
            DURACION_DESVANECER, QEasingCurve.InCubic,
        )
        self._animar_opacidad(0.0, DURACION_DESVANECER)

    def _animar_opacidad(self, destino: float, duracion: int) -> None:
        self._anim_opacidad.stop()
        self._anim_opacidad.setDuration(duracion)
        self._anim_opacidad.setStartValue(self.windowOpacity())
        self._anim_opacidad.setEndValue(destino)
        self._anim_opacidad.start()

    def _al_terminar_opacidad(self) -> None:
        if not self._ocultando:
            return
        self._ocultando = False
        self.hide()  # oculta de verdad: no recibe clics ni teclado
        self._limpiar()
        self.agente.reiniciar()  # la conversación se reinicia al ocultarse

    def _limpiar(self) -> None:
        self.entrada.clear()
        self.entrada.setEnabled(True)
        self.respuesta.clear()
        for w in (self.respuesta, self.etiqueta_herramienta, self.confirmacion, self.aviso,
                  self.boton_cancelar, self.cuerpo):
            w.hide()
        self.circulo.establecer_estado("espera")

    def _reiniciar_inactividad(self) -> None:
        segundos = float(self.config.ocultar_tras_inactividad_s)
        if segundos > 0:
            self._inactividad.start(int(segundos * 1000))
        else:
            self._inactividad.stop()  # 0 = nunca se oculta sola

    def _al_inactividad(self) -> None:
        ocupado = (self._trabajador is not None or self.salida_voz.hablando
                   or self.underMouse() or not self.confirmacion.isHidden())
        if ocupado:
            self._reiniciar_inactividad()
        else:
            self.ocultar()

    def _al_presionar_esc(self) -> None:
        if self._trabajador is not None:
            self.cancelar()
        elif self.salida_voz.hablando:
            self.salida_voz.detener()  # primer Esc: calla; el siguiente oculta
        else:
            self.ocultar()

    # ------------------------------------------------------------------ #
    # Voz
    # ------------------------------------------------------------------ #
    def establecer_voz(self, activada: bool) -> None:
        if activada and not self.salida_voz.disponible:
            self._mostrar_aviso("No hay voz disponible.")
            activada = False
        self.voz_activada = activada
        if not activada:
            self.salida_voz.detener()
        self._actualizar_boton_voz()
        self.voz_cambiada.emit(activada)

    def cambiar_salida_voz(self, nueva: SalidaVoz) -> None:
        """Reemplaza el motor de voz (al guardar los ajustes) sin reiniciar Jarvis."""
        anterior = self.salida_voz
        anterior.al_terminar = None
        anterior.cerrar()
        self.salida_voz = nueva
        nueva.al_terminar = self.voz_terminada.emit
        self.voz_activada = bool(self.config.voz.activada and nueva.disponible)
        self._actualizar_boton_voz()
        self.voz_cambiada.emit(self.voz_activada)

    def _actualizar_boton_voz(self) -> None:
        self.boton_voz.setText("🔊" if self.voz_activada else "🔇")
        nombre = self.salida_voz.nombre_voz or "sin voz"
        self.boton_voz.setToolTip(
            f"Voz activada ({nombre}). Clic para silenciar." if self.voz_activada
            else "Voz desactivada. Clic para activarla."
        )

    def _hablar(self, texto: str) -> bool:
        """Lee el texto si la voz está activada. Devuelve True si empezó a hablar."""
        if not self.voz_activada or not texto:
            return False
        self.salida_voz.hablar(texto)
        return True

    def _al_terminar_voz(self, _natural: bool) -> None:
        if self._trabajador is None and self.circulo.estado == "respondiendo":
            self.circulo.establecer_estado("espera")
        if self.isVisible():
            self._reiniciar_inactividad()

    # ------------------------------------------------------------------ #
    # Pedidos
    # ------------------------------------------------------------------ #
    def _enviar_desde_caja(self) -> None:
        self.enviar_pedido(self.entrada.text())

    def enviar_pedido(self, texto: str) -> None:
        """Punto de entrada común para texto escrito y, en el futuro, voz transcrita."""
        texto = texto.strip()
        if not texto or self._trabajador is not None:
            return
        self._temporizador_estado.stop()
        self.salida_voz.detener()
        self.entrada.clear()
        self.entrada.setPlaceholderText(texto[:60] + ("…" if len(texto) > 60 else ""))
        self.entrada.setEnabled(False)
        self.boton_cancelar.show()
        self.etiqueta_herramienta.hide()
        self.respuesta.hide()
        self._mostrar_aviso("Pensando…")
        self.circulo.establecer_estado("pensando")
        self._reiniciar_inactividad()

        trabajador = Trabajador(self.agente, texto)
        self._trabajador = trabajador
        # Cada señal verifica que provenga del pedido vigente (los cancelados se ignoran).
        trabajador.estado.connect(lambda e, t=trabajador: self._si_vigente(t, self._al_estado, e))
        trabajador.herramienta.connect(lambda n, a, t=trabajador: self._si_vigente(t, self._al_herramienta, n, a))
        trabajador.aviso.connect(lambda x, t=trabajador: self._si_vigente(t, self._mostrar_aviso, x))
        trabajador.pedir_confirmacion.connect(lambda p, t=trabajador: self._si_vigente(t, self._al_pedir_confirmacion, p))
        trabajador.terminado.connect(lambda x, t=trabajador: self._si_vigente(t, self._al_terminar, x))
        trabajador.fallo.connect(lambda x, t=trabajador: self._si_vigente(t, self._al_fallar, x))
        trabajador.iniciar()

    def _si_vigente(self, trabajador, funcion, *args) -> None:
        if trabajador is self._trabajador:
            funcion(*args)

    def cancelar(self, silencioso: bool = False) -> None:
        if self._trabajador is None:
            return
        self._trabajador.detener()
        self.salida_voz.detener()
        self._fin_de_pedido()
        if not silencioso:
            self.etiqueta_herramienta.hide()
            self._mostrar_respuesta("Pedido cancelado.")
            self.circulo.establecer_estado("espera")
        self._reiniciar_inactividad()

    def _fin_de_pedido(self) -> None:
        self._trabajador = None
        self.confirmacion.hide()
        self.boton_cancelar.hide()
        self.aviso.hide()
        self.entrada.setEnabled(True)
        self.entrada.setPlaceholderText("Pregúntale a Jarvis…")
        if self.isVisible():
            self.entrada.setFocus()
        self._ajustar_tamano()

    def _mostrar_respuesta(self, texto: str) -> None:
        self.respuesta.setPlainText(texto)
        self.respuesta.setVisible(bool(texto))
        self._ajustar_tamano()

    def _mostrar_aviso(self, texto: str) -> None:
        self.aviso.setText(texto)
        self.aviso.setVisible(bool(texto))
        self._ajustar_tamano()

    # --- Señales del trabajador --------------------------------------- #
    def _al_estado(self, estado: str) -> None:
        self.circulo.establecer_estado(estado)
        if estado == "pensando":
            self._mostrar_aviso("Pensando…")

    def _al_herramienta(self, nombre: str, argumentos: str) -> None:
        # Una sola línea, recortada con "…": la isla no crece por argumentos largos.
        texto = f"⚙ {nombre} {argumentos}"
        self.etiqueta_herramienta.setToolTip(texto)
        self.etiqueta_herramienta.setText(self.etiqueta_herramienta.fontMetrics().elidedText(
            texto, Qt.ElideRight, ANCHO - 40))
        self.etiqueta_herramienta.show()
        self._mostrar_aviso(f"Usando {nombre}…")

    def _al_pedir_confirmacion(self, pregunta: str) -> None:
        self.pregunta.setText(pregunta)
        self.confirmacion.show()
        self.circulo.establecer_estado("esperando")
        self._mostrar_aviso("Esperando tu confirmación…")
        self.boton_no.setFocus()  # por seguridad, el foco queda en "No"
        if self.config.voz.leer_confirmaciones:
            self._hablar(pregunta.split("\n", 1)[0])  # solo la primera línea, sin detalles técnicos

    def _responder_confirmacion(self, aprobado: bool) -> None:
        self.salida_voz.detener()
        self.confirmacion.hide()
        if self._trabajador is not None:
            self._trabajador.responder_confirmacion(aprobado)
            self.circulo.establecer_estado("pensando")
            self._mostrar_aviso("Pensando…")
        self._reiniciar_inactividad()

    def _al_terminar(self, texto: str) -> None:
        self._fin_de_pedido()
        self._mostrar_respuesta(texto)
        self.circulo.establecer_estado("respondiendo")
        # Mientras habla, el círculo sigue en "respondiendo"; al terminar vuelve a espera.
        if not self._hablar(texto):
            self._temporizador_estado.start(2500)
        self._reiniciar_inactividad()

    def _al_fallar(self, mensaje: str) -> None:
        self._fin_de_pedido()
        self._mostrar_respuesta(mensaje)
        self.circulo.establecer_estado("error")
        self._temporizador_estado.start(3000)
        if self.config.voz.leer_errores:
            self._hablar(mensaje)
        self._reiniciar_inactividad()

    # ------------------------------------------------------------------ #
    # Vidrio esmerilado y forma redondeada
    # ------------------------------------------------------------------ #
    def _zona_vidrio(self) -> QRect:
        """La isla siempre crece dentro de esta zona: se captura entera una sola vez."""
        return self._rect_objetivo(alto=ALTO_MAX_ISLA)

    def aplicar_apariencia(self, opacidad: int, desenfoque: int) -> None:
        self.vidrio.configurar(opacidad, desenfoque)

    def paintEvent(self, evento):
        p = QPainter(self)
        self.vidrio.pintar(p)
        p.end()

    def showEvent(self, evento):
        self.vidrio.iniciar()
        super().showEvent(evento)

    def hideEvent(self, evento):
        self.vidrio.detener()
        super().hideEvent(evento)

    # ------------------------------------------------------------------ #
    def enterEvent(self, evento):
        self._reiniciar_inactividad()
        super().enterEvent(evento)

    def mousePressEvent(self, evento):
        if self.entrada.isEnabled():
            self.entrada.setFocus()
        super().mousePressEvent(evento)
