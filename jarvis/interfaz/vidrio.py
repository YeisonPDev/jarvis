"""Fondo de vidrio esmerilado dibujado por Jarvis, con esquinas suavizadas.

Cómo funciona:
1. La ventana se excluye de las capturas de pantalla (SetWindowDisplayAffinity), así
   Jarvis puede capturar lo que hay DETRÁS de ella sin verse a sí misma.
2. Esa zona se desenfoca (Pillow) y se pinta dentro de un rectángulo redondeado con
   antialiasing, más un tinte negro cuya opacidad elige el usuario.
3. Mientras la ventana está visible, el fondo se actualiza unas 5 veces por segundo.

Efecto secundario: las ventanas de Jarvis no aparecen en capturas, grabaciones ni al
compartir pantalla.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes

from PIL import Image, ImageFilter
from PySide6.QtCore import QPoint, QRect, QRectF, QTimer
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPixmap, QTransform

WDA_EXCLUDEFROMCAPTURE = 0x11
INTERVALO_MS = 200
FACTOR_REDUCCION = 4  # se desenfoca una versión reducida: más rápido y más suave


def excluir_de_capturas(widget) -> bool:
    try:
        funcion = ctypes.windll.user32.SetWindowDisplayAffinity
        funcion.argtypes = [wintypes.HWND, wintypes.DWORD]
        funcion.restype = wintypes.BOOL
        return bool(funcion(wintypes.HWND(int(widget.winId())), WDA_EXCLUDEFROMCAPTURE))
    except Exception:  # noqa: BLE001 - versiones antiguas de Windows
        return False


def desenfocar(pixmap: QPixmap, radio: float, ancho: int, alto: int) -> QPixmap:
    """Desenfoca una captura y la devuelve en tamaño lógico (ancho × alto)."""
    imagen = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
    w, h = imagen.width(), imagen.height()
    if w <= 0 or h <= 0:
        return QPixmap()
    datos = bytes(imagen.constBits())[: imagen.sizeInBytes()]
    pil = Image.frombuffer("RGBA", (w, h), datos, "raw", "RGBA", imagen.bytesPerLine(), 1)
    pequeno = pil.resize((max(1, w // FACTOR_REDUCCION), max(1, h // FACTOR_REDUCCION)), Image.BILINEAR)
    escala = w / max(1, ancho)  # píxeles físicos por píxel lógico
    if radio > 0:
        pequeno = pequeno.filter(ImageFilter.GaussianBlur(radio * escala / FACTOR_REDUCCION))
    final = pequeno.resize((max(1, ancho), max(1, alto)), Image.BICUBIC).convert("RGBA")
    resultado = QImage(final.tobytes("raw", "RGBA"), final.width, final.height,
                       final.width * 4, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(resultado)


class FondoVidrio:
    def __init__(self, widget, radio: float, opacidad: int = 45, desenfoque: int = 18,
                 zona_captura: Callable[[], QRect] | None = None):
        """opacidad: 0–100 (tinte negro). desenfoque: radio en píxeles (0 = nada).

        zona_captura: rectángulo global a capturar (por defecto, la ventana misma).
        """
        self.widget = widget
        self.radio = radio
        self.opacidad = opacidad
        self.desenfoque = desenfoque
        self.zona_captura = zona_captura or widget.frameGeometry
        self._pixmap: QPixmap | None = None
        self._origen = QPoint()
        self._excluida = False
        self._temporizador = QTimer(widget)
        self._temporizador.setInterval(INTERVALO_MS)
        self._temporizador.timeout.connect(self.actualizar)

    def configurar(self, opacidad: int | None = None, desenfoque: int | None = None) -> None:
        if opacidad is not None:
            self.opacidad = max(0, min(100, int(opacidad)))
        if desenfoque is not None:
            self.desenfoque = max(0, min(40, int(desenfoque)))
        self.actualizar()

    def iniciar(self) -> None:
        """Llamar en showEvent."""
        if not self._excluida:
            self._excluida = excluir_de_capturas(self.widget)
        self.actualizar()
        if self._excluida:  # sin exclusión no se puede refrescar (se vería a sí misma)
            self._temporizador.start()

    def detener(self) -> None:
        """Llamar en hideEvent."""
        self._temporizador.stop()

    def actualizar(self) -> None:
        zona = self.zona_captura()
        if zona.width() <= 0 or zona.height() <= 0:
            return
        pantalla = QGuiApplication.screenAt(zona.center()) or QGuiApplication.primaryScreen()
        if pantalla is None:
            return
        geo = pantalla.geometry()
        try:
            captura = pantalla.grabWindow(0, zona.x() - geo.x(), zona.y() - geo.y(), zona.width(), zona.height())
            self._pixmap = desenfocar(captura, self.desenfoque, zona.width(), zona.height())
            self._origen = zona.topLeft()
        except Exception:  # noqa: BLE001 - si falla, queda solo el tinte
            self._pixmap = None
        self.widget.update()

    def pintar(self, p: QPainter) -> None:
        """Dibuja el vidrio. Llamar al inicio del paintEvent de la ventana."""
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radio = min(self.radio, rect.height() / 2)
        forma = QPainterPath()
        forma.addRoundedRect(rect, radio, radio)

        if self._pixmap is not None and not self._pixmap.isNull():
            desplazamiento = self._origen - self.widget.mapToGlobal(QPoint(0, 0))
            pincel = QBrush(self._pixmap)
            pincel.setTransform(QTransform.fromTranslate(desplazamiento.x(), desplazamiento.y()))
            p.fillPath(forma, pincel)  # relleno con antialiasing: bordes suaves
        p.fillPath(forma, QColor(0, 0, 0, int(255 * self.opacidad / 100)))
        p.setPen(QPen(QColor(255, 255, 255, 38), 1))
        p.drawPath(forma)
