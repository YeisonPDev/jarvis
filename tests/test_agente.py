"""Ciclo del agente: argumentos mal formados, confirmaciones y datos no confiables."""

import threading

import pytest

from jarvis.cerebro.agente import Agente
from jarvis.cerebro.prompts import MARCA_INICIO
from jarvis.cerebro.proveedores.base import LlamadaHerramienta, Proveedor, RespuestaModelo
from jarvis.herramientas import crear_registro
from jarvis.herramientas.base import exito, validar_argumentos


class ProveedorGuionado(Proveedor):
    """Devuelve respuestas predefinidas y guarda lo que recibió."""

    nombre = "prueba"

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.recibidos = []

    def completar(self, mensajes, herramientas, tiempo_limite):
        self.recibidos.append([dict(m) for m in mensajes])
        return self.respuestas.pop(0)


class ObservadorPrueba:
    def __init__(self, aprobar=False):
        self.aprobar = aprobar
        self.preguntas = []
        self.herramientas = []

    def al_cambiar_estado(self, estado):
        pass

    def al_usar_herramienta(self, nombre, argumentos):
        self.herramientas.append((nombre, argumentos))

    def al_informar(self, texto):
        pass

    def confirmar(self, pregunta):
        self.preguntas.append(pregunta)
        return self.aprobar


def llamada(nombre, args, id_="1"):
    return RespuestaModelo(llamadas=[LlamadaHerramienta(id_, nombre, args)])


def ultimo_resultado(proveedor):
    return proveedor.recibidos[-1][-1]["content"]


def crear_agente(proveedor, entorno, config):
    return Agente(proveedor, crear_registro(), config, entorno["validador"])


def test_json_mal_formado_se_devuelve_al_modelo(entorno, config_prueba):
    p = ProveedorGuionado([llamada("listar_carpeta", "{ruta: sin comillas"), RespuestaModelo(texto="Listo")])
    texto = crear_agente(p, entorno, config_prueba).procesar("lista", ObservadorPrueba(), threading.Event())
    assert texto == "Listo"
    assert "no son JSON válido" in ultimo_resultado(p)


def test_argumento_desconocido_o_faltante(entorno, config_prueba):
    p = ProveedorGuionado([
        llamada("listar_carpeta", '{"carpeta": "x"}'),
        RespuestaModelo(texto="ok"),
    ])
    crear_agente(p, entorno, config_prueba).procesar("x", ObservadorPrueba(), threading.Event())
    assert "Argumentos desconocidos" in ultimo_resultado(p)


def test_herramienta_inexistente(entorno, config_prueba):
    p = ProveedorGuionado([llamada("borrar_archivo", '{"ruta": "x"}'), RespuestaModelo(texto="No puedo")])
    crear_agente(p, entorno, config_prueba).procesar("borra", ObservadorPrueba(), threading.Event())
    assert "no existe" in ultimo_resultado(p)


def test_no_existen_herramientas_destructivas():
    nombres = " ".join(crear_registro().nombres())
    for prohibida in ("borrar", "eliminar", "mover", "renombrar", "modificar", "ejecutar", "comando", "cerrar"):
        assert prohibida not in nombres


def test_lectura_se_marca_como_no_confiable(entorno, config_prueba):
    p = ProveedorGuionado([
        llamada("leer_archivo", f'{{"ruta": "{(entorno["permitida"] / "notas.txt").as_posix()}"}}'),
        RespuestaModelo(texto="Dice hola"),
    ])
    crear_agente(p, entorno, config_prueba).procesar("lee notas", ObservadorPrueba(), threading.Event())
    resultado = ultimo_resultado(p)
    assert MARCA_INICIO in resultado and "hola" in resultado


def test_tras_leer_archivo_abrir_pagina_requiere_confirmacion(entorno, config_prueba, monkeypatch):
    import webbrowser

    abiertas = []
    monkeypatch.setattr(webbrowser, "open", lambda url, new=0: abiertas.append(url))
    notas = (entorno["permitida"] / "notas.txt").as_posix()
    p = ProveedorGuionado([
        llamada("leer_archivo", f'{{"ruta": "{notas}"}}', "1"),
        # El usuario escribió la URL, pero como ya se leyó un archivo igual se pide confirmación.
        llamada("abrir_pagina", '{"url": "https://example.com"}', "2"),
        RespuestaModelo(texto="fin"),
    ])
    obs = ObservadorPrueba(aprobar=False)
    crear_agente(p, entorno, config_prueba).procesar(
        "lee notas y abre https://example.com", obs, threading.Event()
    )
    assert len(obs.preguntas) == 1 and "leyó un archivo" in obs.preguntas[0]
    assert abiertas == []
    assert "NO autorizó" in ultimo_resultado(p)


def test_url_no_escrita_requiere_confirmacion(entorno, config_prueba, monkeypatch):
    import webbrowser

    abiertas = []
    monkeypatch.setattr(webbrowser, "open", lambda url, new=0: abiertas.append(url))
    p = ProveedorGuionado([llamada("abrir_pagina", '{"url": "https://otro.com"}'), RespuestaModelo(texto="ok")])
    obs = ObservadorPrueba(aprobar=True)
    crear_agente(p, entorno, config_prueba).procesar("abre mi página favorita", obs, threading.Event())
    assert len(obs.preguntas) == 1
    assert abiertas == ["https://otro.com"]


def test_url_escrita_no_requiere_confirmacion(entorno, config_prueba, monkeypatch):
    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda url, new=0: None)
    p = ProveedorGuionado([llamada("abrir_pagina", '{"url": "https://example.com"}'), RespuestaModelo(texto="ok")])
    obs = ObservadorPrueba()
    crear_agente(p, entorno, config_prueba).procesar("abre example.com", obs, threading.Event())
    assert obs.preguntas == []


def test_esquema_url_peligroso_rechazado(entorno, config_prueba, monkeypatch):
    import webbrowser

    abiertas = []
    monkeypatch.setattr(webbrowser, "open", lambda url, new=0: abiertas.append(url))
    p = ProveedorGuionado([llamada("abrir_pagina", '{"url": "file:///C:/Windows/win.ini"}'), RespuestaModelo(texto="no")])
    crear_agente(p, entorno, config_prueba).procesar("abre file:///C:/Windows/win.ini", ObservadorPrueba(True), threading.Event())
    assert abiertas == [] and "no permitido" in ultimo_resultado(p)


def test_crear_archivo_siempre_pide_confirmacion(entorno, config_prueba):
    p = ProveedorGuionado([
        llamada("crear_archivo", '{"nombre": "a.txt", "contenido": "x"}'), RespuestaModelo(texto="ok"),
    ])
    obs = ObservadorPrueba(aprobar=False)
    crear_agente(p, entorno, config_prueba).procesar("crea a.txt", obs, threading.Event())
    assert len(obs.preguntas) == 1
    assert not (entorno["permitida"] / "Jarvis" / "a.txt").exists()


def test_maximo_de_iteraciones(entorno, config_prueba):
    from jarvis.cerebro.errores import ErrorJarvis

    config_prueba.limites.max_iteraciones = 3
    p = ProveedorGuionado([llamada("info_sistema", "{}", str(i)) for i in range(5)])
    agente = crear_agente(p, entorno, config_prueba)
    agente.herramientas.obtener("info_sistema").funcion = lambda ctx, a: exito("ok")
    with pytest.raises(ErrorJarvis, match="3 pasos"):
        agente.procesar("x", ObservadorPrueba(), threading.Event())


def test_historial_se_mantiene_y_se_reinicia(entorno, config_prueba):
    p = ProveedorGuionado([RespuestaModelo(texto="uno"), RespuestaModelo(texto="dos")])
    agente = crear_agente(p, entorno, config_prueba)
    agente.procesar("hola", ObservadorPrueba(), threading.Event())
    assert len(agente.historial) == 2
    agente.procesar("otra", ObservadorPrueba(), threading.Event())
    assert len(agente.historial) == 4
    agente.reiniciar()
    assert agente.historial == []


def test_validacion_de_tipos():
    esquema = {"type": "object", "properties": {
        "valor": {"type": "integer", "minimum": 0, "maximum": 100},
        "accion": {"type": "string", "enum": ["subir", "bajar"]},
    }, "required": ["accion"]}
    assert validar_argumentos(esquema, {"accion": "SUBIR", "valor": "50"}) == ({"accion": "subir", "valor": 50}, None)
    assert validar_argumentos(esquema, {"accion": "volar"})[1]
    assert validar_argumentos(esquema, {"accion": "subir", "valor": 150})[1]
    assert validar_argumentos(esquema, {"valor": 5})[1]
    assert validar_argumentos(esquema, ["no", "es", "objeto"])[1]


def test_abrir_ajustes_usa_el_puente(entorno, config_prueba):
    class Puente:
        llamadas = 0

        def solicitar_ajustes(self):
            Puente.llamadas += 1

    p = ProveedorGuionado([llamada("abrir_ajustes", "{}"), RespuestaModelo(texto="Listo")])
    agente = crear_agente(p, entorno, config_prueba)
    obs = ObservadorPrueba()
    agente.procesar("abre los ajustes", obs, threading.Event())  # sin puente: error claro
    assert "no está disponible" in ultimo_resultado(p)

    p2 = ProveedorGuionado([llamada("abrir_ajustes", "{}"), RespuestaModelo(texto="Listo")])
    agente2 = crear_agente(p2, entorno, config_prueba)
    agente2.interfaz = Puente()
    agente2.procesar("abre los ajustes", obs, threading.Event())
    assert Puente.llamadas == 1 and obs.preguntas == []
