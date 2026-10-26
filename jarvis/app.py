"""Arma todas las piezas y arranca la aplicación."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from jarvis import registro
from jarvis.cerebro.agente import Agente
from jarvis.cerebro.errores import ErrorJarvis
from jarvis.cerebro.proveedores.fabrica import crear_proveedor
from jarvis.config import Config
from jarvis.herramientas import crear_registro
from jarvis.interfaz.ajustes import VentanaAjustes
from jarvis.interfaz.atajo import AtajoGlobal
from jarvis.interfaz.bandeja import BandejaJarvis, crear_icono
from jarvis.interfaz.ventana import VentanaJarvis
from jarvis.seguridad.entorno import es_administrador
from jarvis.seguridad.rutas import ValidadorRutas
from jarvis.voz import crear_salida_voz


class PuenteInterfaz(QObject):
    """Permite que las herramientas (en el hilo del agente) pidan cosas a la interfaz."""

    abrir_ajustes = Signal()

    def solicitar_ajustes(self) -> None:
        self.abrir_ajustes.emit()  # Qt la entrega en el hilo principal


def main() -> int:
    config = Config.cargar()
    os.makedirs(config.carpeta_datos, exist_ok=True)
    carpeta_logs = registro.configurar(config.carpeta_datos, secretos=[config.api_key, config.tts_api_key, config.busqueda_api_key])

    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")
    app.setQuitOnLastWindowClosed(False)  # sigue en segundo plano al ocultarse
    app.setWindowIcon(crear_icono())

    # Una sola instancia de Jarvis a la vez.
    bloqueo = QLockFile(os.path.join(config.carpeta_datos, "jarvis.lock"))
    if not bloqueo.tryLock(100):
        QMessageBox.information(None, "Jarvis", "Jarvis ya está en ejecución (mira la bandeja del sistema).")
        return 0

    if es_administrador():
        QMessageBox.warning(
            None, "Jarvis",
            "Jarvis se está ejecutando como administrador.\n\n"
            "No es necesario y aumenta el riesgo. Ciérralo y ábrelo normalmente.",
        )

    try:
        proveedor = crear_proveedor(config)
    except ErrorJarvis as e:
        QMessageBox.critical(None, "Jarvis — configuración", e.mensaje_usuario)
        return 1

    validador = ValidadorRutas.desde_config(config)
    agente = Agente(proveedor, crear_registro(), config, validador)
    salida_voz = crear_salida_voz(config)
    if not salida_voz.disponible:
        registro.general().warning("No se encontraron voces de Windows; Jarvis funcionará sin voz.")
    ventana = VentanaJarvis(agente, config, salida_voz=salida_voz)
    app.aboutToQuit.connect(lambda: ventana.salida_voz.cerrar())

    # Ajustes: solo se abren cuando el usuario se lo pide a Jarvis.
    puente = PuenteInterfaz()
    agente.interfaz = puente
    estado = {"ajustes": None}

    def aplicar_voz() -> None:
        """Se llama al guardar los ajustes: aplica la voz y el tiempo de ocultado al instante."""
        ventana.cambiar_salida_voz(crear_salida_voz(config))
        if ventana.isVisible():
            ventana._reiniciar_inactividad()

    def mostrar_ajustes() -> None:
        if estado["ajustes"] is None:
            estado["ajustes"] = VentanaAjustes(
                config, aplicar=aplicar_voz, vista_previa=ventana.aplicar_apariencia,
            )
        estado["ajustes"].abrir()

    puente.abrir_ajustes.connect(mostrar_ajustes)
    bandeja = BandejaJarvis(ventana, app, config.atajo)
    bandeja.show()

    try:
        atajo = AtajoGlobal(config.atajo)
        atajo_ok = atajo.iniciar()
    except ValueError as e:
        atajo, atajo_ok = None, False
        registro.general().warning("Atajo inválido en config.json: %s", e)

    if atajo is not None:
        atajo.activado.connect(ventana.alternar)
        app.aboutToQuit.connect(atajo.detener)

    if atajo_ok:
        bandeja.showMessage("Jarvis está listo", f"Presiona {config.atajo} para llamarlo.",
                            BandejaJarvis.Information, 3000)
    else:
        bandeja.showMessage(
            "Jarvis: atajo no disponible",
            f"No pude registrar '{config.atajo}' (inválido o usado por otro programa). "
            "Cámbialo en config.json. Mientras tanto, haz clic en este ícono.",
            BandejaJarvis.Warning, 8000,
        )

    registro.general().info(
        "Jarvis iniciado. Proveedor=%s modelo=%s logs=%s", config.proveedor, proveedor.modelo, carpeta_logs
    )
    codigo = app.exec()
    bloqueo.unlock()
    return codigo
