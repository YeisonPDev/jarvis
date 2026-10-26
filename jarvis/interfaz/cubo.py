"""Logo de Jarvis: un cubo Rubik en 3D que gira mientras piensa o habla.

Se dibuja con proyección ortográfica: cada cara visible con sus 3×3 casillas,
iluminación simple y ocultamiento de caras traseras.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QWidget

_ROJO, _NARANJA, _BLANCO, _AMARILLO, _VERDE, _AZUL = (
    QColor(220, 40, 60), QColor(255, 120, 20), QColor(248, 248, 248),
    QColor(255, 215, 0), QColor(0, 185, 100), QColor(20, 100, 230),
)
_PALETA = [_ROJO, _NARANJA, _BLANCO, _AMARILLO, _VERDE, _AZUL]

# (normal, eje u, eje v, color del centro) — las esquinas de la cara son normal ± u ± v
_CARAS = [
    ((1, 0, 0), (0, 0, -1), (0, 1, 0), 0),    # derecha: rojo
    ((-1, 0, 0), (0, 0, 1), (0, 1, 0), 1),    # izquierda: naranja
    ((0, 1, 0), (1, 0, 0), (0, 0, -1), 2),    # arriba: blanco
    ((0, -1, 0), (1, 0, 0), (0, 0, 1), 3),    # abajo: amarillo
    ((0, 0, 1), (1, 0, 0), (0, 1, 0), 4),     # frente: verde
    ((0, 0, -1), (-1, 0, 0), (0, 1, 0), 5),   # atrás: azul
]
# Patrón fijo "a medio resolver" (índices de _PALETA); el centro (posición 4) es el de la cara.
_PATRON = [
    [0, 4, 0, 2, 0, 5, 0, 0, 3],
    [1, 1, 3, 1, 1, 0, 4, 1, 1],
    [2, 2, 5, 2, 2, 2, 1, 2, 2],
    [3, 3, 3, 0, 3, 3, 3, 2, 3],
    [4, 5, 4, 4, 4, 4, 1, 4, 4],
    [5, 5, 4, 5, 5, 5, 5, 3, 5],
]
_LUZ = (-0.35, 0.75, 0.55)
_HUECO = 0.09  # separación negra entre casillas (fracción de casilla)
INCLINACION = 0.52  # radianes: se ve un poco desde arriba
GIRO_REPOSO = math.radians(35)

_ESTADOS = {"espera", "pensando", "herramienta", "esperando", "respondiendo", "error"}
_VELOCIDADES = {  # grados por segundo
    "pensando": 220, "herramienta": 260, "esperando": 90, "respondiendo": 140,
}


def _rotar(p, giro: float, inclinacion: float):
    x, y, z = p
    cg, sg = math.cos(giro), math.sin(giro)
    x, z = x * cg + z * sg, -x * sg + z * cg
    ci, si = math.cos(inclinacion), math.sin(inclinacion)
    y, z = y * ci - z * si, y * si + z * ci
    return x, y, z


def dibujar_cubo(p: QPainter, cx: float, cy: float, escala: float, giro: float,
                 inclinacion: float = INCLINACION, atenuado: bool = False) -> None:
    """Dibuja el cubo centrado en (cx, cy). 'escala' es la mitad del lado en píxeles."""
    largo_luz = math.sqrt(sum(c * c for c in _LUZ))
    luz = tuple(c / largo_luz for c in _LUZ)
    visibles = []
    for normal, u, v, color in _CARAS:
        n = _rotar(normal, giro, inclinacion)
        if n[2] <= 0.02:
            continue  # cara de espaldas
        visibles.append((n[2], normal, u, v, color, n))  # color = índice de la cara
    visibles.sort(key=lambda c: c[0])

    def proyectar(a: float, b: float, normal, u, v) -> QPointF:
        punto = tuple(normal[k] + a * u[k] + b * v[k] for k in range(3))
        x, y, _ = _rotar(punto, giro, inclinacion)
        return QPointF(cx + x * escala, cy - y * escala)

    p.setPen(Qt.NoPen)
    for _, normal, u, v, color, n in visibles:
        # Cuerpo negro de la cara
        p.setBrush(QColor(12, 12, 14))
        p.drawPolygon(QPolygonF([proyectar(a, b, normal, u, v)
                                 for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]))
        # Casillas con iluminación suave
        brillo = 0.74 + 0.26 * max(0.0, sum(n[k] * luz[k] for k in range(3)))
        if atenuado:
            brillo *= 0.45
        for i in range(3):
            for j in range(3):
                base = _PALETA[_PATRON[color][(2 - j) * 3 + i]]
                p.setBrush(QColor(int(base.red() * brillo), int(base.green() * brillo),
                                  int(base.blue() * brillo)))
                a0 = -1 + 2 * (i + _HUECO) / 3
                a1 = -1 + 2 * (i + 1 - _HUECO) / 3
                b0 = -1 + 2 * (j + _HUECO) / 3
                b1 = -1 + 2 * (j + 1 - _HUECO) / 3
                p.drawPolygon(QPolygonF([
                    proyectar(a0, b0, normal, u, v), proyectar(a1, b0, normal, u, v),
                    proyectar(a1, b1, normal, u, v), proyectar(a0, b1, normal, u, v),
                ]))


class CuboRubik(QWidget):
    """Mismo uso que antes tenía el círculo: establecer_estado('pensando'), etc."""

    def __init__(self, tamano: int = 24, parent=None):
        super().__init__(parent)
        self.setFixedSize(tamano, tamano)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._estado = "espera"
        self._giro = GIRO_REPOSO
        self._ultimo = time.monotonic()
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(16)
        self._temporizador.timeout.connect(self._avanzar)

    @property
    def estado(self) -> str:
        return self._estado

    def establecer_estado(self, estado: str) -> None:
        estado = estado if estado in _ESTADOS else "espera"
        if estado != self._estado:
            self._estado = estado
            self._ultimo = time.monotonic()
            if self.isVisible():
                self._temporizador.start()
            self.update()

    def _avanzar(self) -> None:
        ahora = time.monotonic()
        dt = min(0.1, ahora - self._ultimo)
        self._ultimo = ahora
        velocidad = _VELOCIDADES.get(self._estado)
        if velocidad:
            self._giro += math.radians(velocidad) * dt
        else:
            # En reposo: se detiene suavemente en la posición de descanso más cercana.
            paso = math.pi / 2
            destino = GIRO_REPOSO + round((self._giro - GIRO_REPOSO) / paso) * paso
            diferencia = destino - self._giro
            if abs(diferencia) < 0.002:
                self._giro = destino
                self._temporizador.stop()  # quieto: no consume CPU
            else:
                self._giro += diferencia * min(1.0, dt * 8)
        self.update()

    def showEvent(self, evento):
        self._ultimo = time.monotonic()
        self._temporizador.start()
        super().showEvent(evento)

    def hideEvent(self, evento):
        self._temporizador.stop()
        super().hideEvent(evento)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        lado = min(self.width(), self.height())
        dibujar_cubo(p, self.width() / 2, self.height() / 2, lado * 0.27, self._giro,
                     atenuado=self._estado == "error")
        p.end()
