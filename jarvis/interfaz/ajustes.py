"""Ventana de ajustes: motor de voz, idioma, voz, velocidad y apariencia (opacidad y desenfoque).

Solo se abre cuando el usuario se lo pide a Jarvis (herramienta abrir_ajustes).
Los cambios se guardan en config.json y se aplican al instante.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

from jarvis import registro
from jarvis.interfaz.vidrio import FondoVidrio
from jarvis.voz import crear_salida_voz
from jarvis.voz.openai_voz import VOCES_OPENAI
from jarvis.voz.piper_voz import VozPiper, cargar_catalogo, descargar_voz, esta_descargada
from jarvis.voz.windows import es_del_idioma, listar_voces_windows

MOTORES = [
    ("Piper — natural, local, sin internet", "piper"),
    ("OpenAI — en línea, requiere llave", "openai"),
    ("Windows — básica, sin internet", "windows"),
]
FRASES_PRUEBA = {
    "es": "Hola, soy Jarvis. Así sonará mi voz con esta velocidad.",
    "en": "Hello, I'm Jarvis. This is how my voice will sound at this speed.",
    "pt": "Olá, eu sou o Jarvis. É assim que a minha voz vai soar.",
    "fr": "Bonjour, je suis Jarvis. Voici comment ma voix va sonner.",
    "it": "Ciao, sono Jarvis. Ecco come suonerà la mia voce.",
    "de": "Hallo, ich bin Jarvis. So wird meine Stimme klingen.",
}

ESTILO = """
#tarjeta { background: transparent; border: none; }
#seccion { color: #ffffff; font-size: 13px; font-weight: 600; padding-top: 4px; }
QLabel { color: #e5e5ea; font-size: 13px; }
#titulo { color: #ffffff; font-size: 17px; font-weight: 600; }
#subtitulo, #estado { color: #8e8e93; font-size: 12px; }
#velocidad { color: #64d2ff; font-size: 13px; min-width: 48px; }
QComboBox {
    background-color: rgba(44, 44, 46, 150); color: #ffffff; border: 1px solid rgba(255,255,255,30);
    border-radius: 9px; padding: 6px 10px; font-size: 13px; min-height: 20px;
}
QComboBox:hover { border-color: rgba(10,132,255,160); }
QLineEdit {
    background-color: rgba(44, 44, 46, 150); color: #ffffff; border: 1px solid rgba(255,255,255,30);
    border-radius: 9px; padding: 6px 10px; font-size: 13px;
}
QLineEdit:focus { border-color: rgba(10,132,255,200); }
QComboBox QAbstractItemView {
    background-color: #1c1c1e; color: #ffffff; selection-background-color: #0a84ff;
    border: 1px solid rgba(255,255,255,30); outline: 0;
}
QSlider::groove:horizontal { height: 4px; background: #3a3a3c; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #0a84ff; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffffff; width: 16px; margin: -6px 0; border-radius: 8px; }
QPushButton {
    color: #ffffff; background-color: rgba(58, 58, 60, 160); border: none; border-radius: 10px;
    padding: 8px 14px; font-size: 13px;
}
QPushButton:hover { background-color: #3a3a3c; }
QPushButton:disabled { color: #636366; }
QPushButton#guardar { background-color: #0a84ff; }
QPushButton#guardar:hover { background-color: #3a9bff; }
QPushButton#cerrar { background: transparent; font-size: 15px; padding: 4px 8px; }
QProgressBar { background: #1c1c1e; border: none; border-radius: 4px; height: 8px; color: transparent; }
QProgressBar::chunk { background: #0a84ff; border-radius: 4px; }
"""


class VentanaAjustes(QWidget):
    _catalogo_listo = Signal(list)
    _progreso = Signal(int, int)
    _descarga_lista = Signal(bool, str, str)  # ok, mensaje, siguiente acción

    def __init__(self, config, aplicar: Callable[[], None],
                 vista_previa: Callable[[int, int], None] | None = None):
        """aplicar(): recrea la voz tras guardar. vista_previa(opacidad, desenfoque): cambia la isla en vivo."""
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.config = config
        self.aplicar = aplicar
        self.vista_previa = vista_previa or (lambda _o, _d: None)
        self.catalogo: list[VozPiper] = []
        self.voces_windows: list[tuple[str, str]] = []
        self._descargando = False
        self._cancelar_descarga = threading.Event()
        self._voz_prueba = None
        self._arrastre: QPoint | None = None

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("Ajustes de Jarvis")
        self.setStyleSheet(ESTILO)
        self.setFixedWidth(460)
        self.vidrio = FondoVidrio(self, 18, opacidad=config.opacidad_fondo, desenfoque=config.desenfoque)
        self._construir()

        self._catalogo_listo.connect(self._al_cargar_catalogo)
        self._progreso.connect(self._al_progresar)
        self._descarga_lista.connect(self._al_terminar_descarga)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)

    # ------------------------------------------------------------------ #
    def _construir(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        tarjeta = QFrame(objectName="tarjeta")
        raiz.addWidget(tarjeta)
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(22, 16, 22, 20)
        caja.setSpacing(12)

        cabecera = QHBoxLayout()
        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        titulos.addWidget(QLabel("Ajustes de Jarvis", objectName="titulo"))
        titulos.addWidget(QLabel("Voz, idioma, clima y apariencia", objectName="subtitulo"))
        cabecera.addLayout(titulos)
        cabecera.addStretch(1)
        cerrar = QPushButton("✕", objectName="cerrar")
        cerrar.clicked.connect(self.close)
        cabecera.addWidget(cerrar, 0, Qt.AlignTop)
        caja.addLayout(cabecera)

        formulario = QFormLayout()
        formulario.setHorizontalSpacing(14)
        formulario.setVerticalSpacing(12)
        formulario.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.combo_motor = QComboBox()
        for texto, clave in MOTORES:
            self.combo_motor.addItem(texto, clave)
        self.combo_motor.currentIndexChanged.connect(self._al_cambiar_motor)
        formulario.addRow("Motor", self.combo_motor)

        self.combo_idioma = QComboBox()
        self.combo_idioma.currentIndexChanged.connect(lambda _: self._llenar_voces())
        formulario.addRow("Idioma", self.combo_idioma)

        self.combo_voz = QComboBox()
        self.combo_voz.currentIndexChanged.connect(lambda _: self._actualizar_estado_voz())
        formulario.addRow("Voz", self.combo_voz)

        fila_velocidad = QHBoxLayout()
        self.deslizador = QSlider(Qt.Horizontal)
        self.deslizador.setRange(50, 200)
        self.deslizador.setSingleStep(5)
        self.deslizador.setPageStep(10)
        self.deslizador.valueChanged.connect(self._al_cambiar_velocidad)
        self.etiqueta_velocidad = QLabel(objectName="velocidad")
        fila_velocidad.addWidget(self.deslizador, 1)
        fila_velocidad.addWidget(self.etiqueta_velocidad)
        formulario.addRow("Velocidad", fila_velocidad)

        self.campo_ciudad = QLineEdit()
        self.campo_ciudad.setPlaceholderText("Ej.: Bogotá, Colombia")
        self.campo_ciudad.setMaxLength(100)
        formulario.addRow("Ciudad", self.campo_ciudad)

        formulario.addRow(QLabel("Apariencia", objectName="seccion"))
        self.deslizador_opacidad, self.etiqueta_opacidad = self._fila_deslizador(
            formulario, "Opacidad", 0, 100, "{}%")
        self.deslizador_desenfoque, self.etiqueta_desenfoque = self._fila_deslizador(
            formulario, "Desenfoque", 0, 40, "{} px")
        self.deslizador_opacidad.valueChanged.connect(self._al_cambiar_apariencia)
        self.deslizador_desenfoque.valueChanged.connect(self._al_cambiar_apariencia)

        # Tiempo sin actividad antes de que la isla se desvanezca (0 = nunca).
        self.deslizador_ocultar, self.etiqueta_ocultar = self._fila_deslizador(
            formulario, "Ocultar tras", 0, 120, "{} s")
        self.deslizador_ocultar.setSingleStep(5)
        self.deslizador_ocultar.setPageStep(10)
        self.deslizador_ocultar.valueChanged.connect(lambda _: self._actualizar_etiquetas_apariencia())
        caja.addLayout(formulario)

        self.barra = QProgressBar()
        self.barra.setRange(0, 1000)
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(8)
        self.barra.hide()
        caja.addWidget(self.barra)

        self.estado = QLabel(objectName="estado")
        self.estado.setWordWrap(True)
        caja.addWidget(self.estado)

        botones = QHBoxLayout()
        self.boton_probar = QPushButton("▶  Probar voz")
        self.boton_probar.clicked.connect(lambda: self._iniciar("probar"))
        self.boton_guardar = QPushButton("Guardar", objectName="guardar")
        self.boton_guardar.clicked.connect(lambda: self._iniciar("guardar"))
        botones.addWidget(self.boton_probar)
        botones.addStretch(1)
        botones.addWidget(self.boton_guardar)
        caja.addLayout(botones)

    # ------------------------------------------------------------------ #
    # Abrir y cargar datos
    # ------------------------------------------------------------------ #
    def abrir(self) -> None:
        voz = self.config.voz
        self.combo_motor.blockSignals(True)
        self.combo_motor.setCurrentIndex(max(0, self.combo_motor.findData(voz.motor)))
        self.combo_motor.blockSignals(False)
        self.deslizador.setValue(round(voz.velocidad * 100))
        self._al_cambiar_velocidad(self.deslizador.value())
        for deslizador, valor in ((self.deslizador_opacidad, self.config.opacidad_fondo),
                                  (self.deslizador_desenfoque, self.config.desenfoque),
                                  (self.deslizador_ocultar, round(self.config.ocultar_tras_inactividad_s))):
            deslizador.blockSignals(True)
            deslizador.setValue(valor)
            deslizador.blockSignals(False)
        self._actualizar_etiquetas_apariencia()
        self.campo_ciudad.setText(self.config.ciudad)
        self.estado.setText("")

        # Primero lo que hay en el equipo; luego el catálogo completo de internet.
        self.catalogo = cargar_catalogo(self.config.carpeta_voces_piper, usar_red=False)
        self.voces_windows = listar_voces_windows()
        self._llenar_idiomas()
        self._llenar_voces(seleccion_inicial=True)
        threading.Thread(target=self._cargar_catalogo_red, daemon=True, name="jarvis-catalogo").start()
        self.estado.setText("Buscando más voces en internet…")

        area = (QGuiApplication.primaryScreen().availableGeometry()
                if QGuiApplication.primaryScreen() else None)
        self.adjustSize()
        if area is not None:
            self.move(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)
        self.show()
        self.raise_()
        self.activateWindow()

    def _cargar_catalogo_red(self) -> None:
        try:
            voces = cargar_catalogo(self.config.carpeta_voces_piper, usar_red=True)
        except Exception as e:  # noqa: BLE001
            registro.general().warning("No pude cargar el catálogo de Piper: %s", type(e).__name__)
            voces = []
        self._catalogo_listo.emit(voces)

    def _al_cargar_catalogo(self, voces: list) -> None:
        if not self.isVisible():
            return
        if voces:
            idioma, voz = self.combo_idioma.currentData(), self.combo_voz.currentData()
            self.catalogo = voces
            self._llenar_idiomas(preferido=idioma)
            self._llenar_voces(preferida=voz)
            self.estado.setText(f"{len(voces)} voces de Piper disponibles.")
        else:
            self.estado.setText("Sin internet: solo se muestran las voces ya descargadas.")

    # ------------------------------------------------------------------ #
    # Listas
    # ------------------------------------------------------------------ #
    def _llenar_idiomas(self, preferido: str | None = None) -> None:
        idiomas: dict[str, str] = {}
        for v in self.catalogo:
            idiomas.setdefault(v.familia, v.idioma)
        idiomas.setdefault(self.config.idioma_codigo, self.config.idioma_nombre)
        preferido = preferido or self.config.idioma_codigo
        self.combo_idioma.blockSignals(True)
        self.combo_idioma.clear()
        for codigo, nombre in sorted(idiomas.items(), key=lambda x: x[1].lower()):
            self.combo_idioma.addItem(f"{nombre} ({codigo})", codigo)
        self.combo_idioma.setCurrentIndex(max(0, self.combo_idioma.findData(preferido)))
        self.combo_idioma.blockSignals(False)

    def _nombre_idioma(self) -> str:
        texto = self.combo_idioma.currentText()
        return texto.rsplit(" (", 1)[0] if texto else self.config.idioma_nombre

    def _llenar_voces(self, preferida: str | None = None, seleccion_inicial: bool = False) -> None:
        motor = self.combo_motor.currentData()
        idioma = self.combo_idioma.currentData() or self.config.idioma_codigo
        voz = self.config.voz
        self.combo_voz.blockSignals(True)
        self.combo_voz.clear()

        if motor == "piper":
            carpeta = self.config.carpeta_voces_piper
            for v in (v for v in self.catalogo if v.familia == idioma):
                if esta_descargada(carpeta, v.clave):
                    texto = f"✓ {v.descripcion()}"
                else:
                    texto = f"⬇ {v.descripcion()} ({v.tamano_mb:.0f} MB)"
                self.combo_voz.addItem(texto, v.clave)
            indice = self.combo_voz.findData(preferida or voz.piper_voz)
            if indice < 0:  # preferir una voz ya descargada y de calidad media
                claves = [self.combo_voz.itemData(i) for i in range(self.combo_voz.count())]
                descargadas = [i for i, c in enumerate(claves) if esta_descargada(carpeta, c)]
                medias = [i for i, c in enumerate(claves) if c.endswith("-medium")]
                indice = (descargadas or medias or [0])[0]
            self.combo_voz.setCurrentIndex(indice if self.combo_voz.count() else -1)

        elif motor == "openai":
            for nombre in VOCES_OPENAI:
                self.combo_voz.addItem(nombre, nombre)
            self.combo_voz.setCurrentIndex(max(0, self.combo_voz.findData(preferida or voz.openai_voz)))

        else:  # windows
            propias = [(d, i) for d, i in self.voces_windows if es_del_idioma(i, idioma)]
            for descripcion, _ in (propias or self.voces_windows):
                self.combo_voz.addItem(descripcion, descripcion)
            buscada = (preferida or voz.nombre).lower()
            indice = next((i for i in range(self.combo_voz.count())
                           if buscada in self.combo_voz.itemData(i).lower()), 0)
            self.combo_voz.setCurrentIndex(indice if self.combo_voz.count() else -1)

        self.combo_voz.blockSignals(False)
        self._actualizar_estado_voz()

    def _actualizar_estado_voz(self) -> None:
        motor = self.combo_motor.currentData()
        self.deslizador.setEnabled(motor != "openai")
        if self.combo_voz.count() == 0:
            self.estado.setText("No hay voces para este idioma con este motor.")
            return
        if motor == "piper":
            clave = self.combo_voz.currentData()
            if clave and not esta_descargada(self.config.carpeta_voces_piper, clave):
                self.estado.setText("Esta voz se descargará (una sola vez) al probarla o guardar.")
            else:
                self.estado.setText("Voz instalada. Funciona sin internet.")
        elif motor == "openai":
            if self.config.tts_api_key:
                self.estado.setText("Necesita internet. Lo que Jarvis lee en voz alta se envía a OpenAI. "
                                    "La velocidad no se aplica a este motor.")
            else:
                self.estado.setText("Falta JARVIS_TTS_API_KEY en .env: hasta agregarla se usará la voz de Windows.")
        else:
            idioma = self.combo_idioma.currentData() or "es"
            if not any(es_del_idioma(i, idioma) for _, i in self.voces_windows):
                self.estado.setText("No hay voces de Windows en este idioma. Puedes instalarlas en "
                                    "Configuración → Hora e idioma → Voz.")
            else:
                self.estado.setText("Voz de Windows. Funciona sin internet.")

    def _al_cambiar_motor(self, _indice: int) -> None:
        self._llenar_voces()

    @staticmethod
    def _fila_deslizador(formulario, titulo: str, minimo: int, maximo: int, formato: str):
        fila = QHBoxLayout()
        deslizador = QSlider(Qt.Horizontal)
        deslizador.setRange(minimo, maximo)
        etiqueta = QLabel(objectName="velocidad")
        etiqueta.setProperty("formato", formato)
        fila.addWidget(deslizador, 1)
        fila.addWidget(etiqueta)
        formulario.addRow(titulo, fila)
        return deslizador, etiqueta

    def _actualizar_etiquetas_apariencia(self) -> None:
        for deslizador, etiqueta in ((self.deslizador_opacidad, self.etiqueta_opacidad),
                                     (self.deslizador_desenfoque, self.etiqueta_desenfoque)):
            etiqueta.setText(etiqueta.property("formato").format(deslizador.value()))
        segundos = self.deslizador_ocultar.value()
        self.etiqueta_ocultar.setText("Nunca" if segundos == 0 else f"{segundos} s")
        self.deslizador_ocultar.setToolTip(
            "La isla no se oculta sola; ciérrala con Esc." if segundos == 0
            else f"La isla se desvanece tras {segundos} segundos sin actividad.")

    def _al_cambiar_apariencia(self, _valor: int = 0) -> None:
        """Vista previa en vivo, en esta ventana y en la isla. Se guarda con 'Guardar'."""
        opacidad, desenfoque = self.deslizador_opacidad.value(), self.deslizador_desenfoque.value()
        self._actualizar_etiquetas_apariencia()
        self.vidrio.configurar(opacidad, desenfoque)
        self.vista_previa(opacidad, desenfoque)

    def _al_cambiar_velocidad(self, valor: int) -> None:
        self.etiqueta_velocidad.setText(f"{valor / 100:.2f}×")

    # ------------------------------------------------------------------ #
    # Probar y guardar
    # ------------------------------------------------------------------ #
    def _iniciar(self, accion: str) -> None:
        if self._descargando or self.combo_voz.count() == 0:
            return
        motor, clave = self.combo_motor.currentData(), self.combo_voz.currentData()
        if motor == "piper" and clave and not esta_descargada(self.config.carpeta_voces_piper, clave):
            voz = next((v for v in self.catalogo if v.clave == clave), None)
            if voz is None:
                self.estado.setText("No encontré esa voz en el catálogo.")
                return
            self._descargar(voz, accion)
            return
        self._ejecutar(accion)

    def _descargar(self, voz: VozPiper, accion: str) -> None:
        self._descargando = True
        self._cancelar_descarga.clear()
        self._botones(False)
        self.barra.setValue(0)
        self.barra.show()
        self.estado.setText(f"Descargando la voz {voz.nombre} ({voz.tamano_mb:.0f} MB)…")

        def trabajo():
            try:
                descargar_voz(voz, self.config.carpeta_voces_piper,
                              progreso=lambda h, t: self._progreso.emit(h, t),
                              cancelar=self._cancelar_descarga)
                self._descarga_lista.emit(True, "Voz descargada.", accion)
            except Exception as e:  # noqa: BLE001
                registro.general().warning("Falló la descarga de %s: %s", voz.clave, type(e).__name__)
                self._descarga_lista.emit(False, f"No se pudo descargar la voz: {e}", accion)

        threading.Thread(target=trabajo, daemon=True, name="jarvis-descarga-voz").start()

    def _al_progresar(self, hecho: int, total: int) -> None:
        self.barra.setValue(int(1000 * hecho / max(1, total)))

    def _al_terminar_descarga(self, ok: bool, mensaje: str, accion: str) -> None:
        self._descargando = False
        self.barra.hide()
        self._botones(True)
        self.estado.setText(mensaje)
        if ok:
            self._llenar_voces(preferida=self.combo_voz.currentData())
            self._ejecutar(accion)

    def _botones(self, activos: bool) -> None:
        for w in (self.boton_probar, self.boton_guardar, self.combo_motor, self.combo_idioma, self.combo_voz):
            w.setEnabled(activos)

    def _config_elegida(self, base):
        """Copia de la configuración con lo elegido en pantalla."""
        motor, seleccion = self.combo_motor.currentData(), self.combo_voz.currentData()
        base.voz.motor = motor
        base.voz.velocidad = self.deslizador.value() / 100
        if motor == "piper" and seleccion:
            base.voz.piper_voz = seleccion
        elif motor == "openai" and seleccion:
            base.voz.openai_voz = seleccion
        elif motor == "windows" and seleccion:
            base.voz.nombre = seleccion
        base.idioma_codigo = self.combo_idioma.currentData() or base.idioma_codigo
        base.idioma_nombre = self._nombre_idioma()
        return base

    def _ejecutar(self, accion: str) -> None:
        if accion == "probar":
            self._detener_prueba()
            prueba = self._config_elegida(copy.deepcopy(self.config))
            self._voz_prueba = crear_salida_voz(prueba)
            frase = FRASES_PRUEBA.get(prueba.idioma_codigo[:2], FRASES_PRUEBA["en"])
            self._voz_prueba.hablar(frase)
            self.estado.setText(f"Probando: {self._voz_prueba.nombre_voz or 'sin voz'}")
            return

        self._detener_prueba()
        self._config_elegida(self.config)
        self.config.ciudad = self.campo_ciudad.text().strip()
        self.config.ocultar_tras_inactividad_s = float(self.deslizador_ocultar.value())
        self.config.opacidad_fondo = self.deslizador_opacidad.value()
        self.config.desenfoque = self.deslizador_desenfoque.value()
        try:
            self.config.guardar_ajustes()
        except OSError as e:
            self.estado.setText(f"No pude guardar config.json: {e}")
            return
        self.aplicar()
        self._llenar_voces(preferida=self.combo_voz.currentData())
        self.estado.setText("✓ Ajustes guardados y aplicados.")

    def _detener_prueba(self) -> None:
        if self._voz_prueba is not None:
            self._voz_prueba.al_terminar = None
            self._voz_prueba.cerrar()
            self._voz_prueba = None

    # ------------------------------------------------------------------ #
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

    def closeEvent(self, evento):
        self._cancelar_descarga.set()
        self._detener_prueba()
        # Si movió la apariencia pero no guardó, se vuelve a lo guardado.
        self.vidrio.configurar(self.config.opacidad_fondo, self.config.desenfoque)
        self.vista_previa(self.config.opacidad_fondo, self.config.desenfoque)
        super().closeEvent(evento)

    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self._arrastre = evento.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento):
        if self._arrastre is not None and evento.buttons() & Qt.LeftButton:
            self.move(evento.globalPosition().toPoint() - self._arrastre)
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento):
        self._arrastre = None
        super().mouseReleaseEvent(evento)
