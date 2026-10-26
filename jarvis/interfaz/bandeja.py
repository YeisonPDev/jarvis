"""Ícono en la bandeja del sistema con opciones Mostrar y Salir."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from jarvis.interfaz.cubo import GIRO_REPOSO, dibujar_cubo


def crear_icono() -> QIcon:
    """Ícono de la bandeja y de la aplicación: el mismo cubo Rubik del logo."""
    icono = QIcon()
    for tam in (16, 24, 32, 48, 64):
        pixmap = QPixmap(tam, tam)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        dibujar_cubo(p, tam / 2, tam / 2, tam * 0.29, GIRO_REPOSO)
        p.end()
        icono.addPixmap(pixmap)
    return icono


class BandejaJarvis(QSystemTrayIcon):
    def __init__(self, ventana, app: QApplication, atajo: str):
        super().__init__(crear_icono(), app)
        self.ventana = ventana
        self.setToolTip(f"Jarvis — {atajo} para llamarlo")

        menu = QMenu()
        accion_mostrar = QAction("Mostrar Jarvis", menu)
        accion_mostrar.triggered.connect(ventana.mostrar)
        self.accion_voz = QAction("Voz activada", menu)
        self.accion_voz.setCheckable(True)
        self.accion_voz.setChecked(ventana.voz_activada)
        self.accion_voz.setEnabled(ventana.salida_voz.disponible)
        self.accion_voz.toggled.connect(ventana.establecer_voz)
        ventana.voz_cambiada.connect(self._sincronizar_voz)
        accion_salir = QAction("Salir", menu)
        accion_salir.triggered.connect(app.quit)
        menu.addAction(accion_mostrar)
        menu.addAction(self.accion_voz)
        menu.addSeparator()
        menu.addAction(accion_salir)
        self._menu = menu  # mantener referencia
        self.setContextMenu(menu)
        self.activated.connect(self._al_activar)

    def _sincronizar_voz(self, activada: bool) -> None:
        self.accion_voz.setEnabled(self.ventana.salida_voz.disponible)
        if self.accion_voz.isChecked() != activada:
            self.accion_voz.blockSignals(True)
            self.accion_voz.setChecked(activada)
            self.accion_voz.blockSignals(False)

    def _al_activar(self, motivo) -> None:
        if motivo in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.ventana.mostrar()
