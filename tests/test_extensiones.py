"""Nunca se abren archivos ejecutables."""

import pytest

from jarvis.herramientas.archivos import herramientas as herramientas_archivos
from jarvis.herramientas.base import Contexto
from jarvis.seguridad.lista_negra import es_ejecutable


@pytest.mark.parametrize("nombre", [
    "setup.exe", "x.bat", "x.cmd", "x.ps1", "x.vbs", "x.msi", "acceso.lnk", "x.reg", "x.js",
    "x.py", "x.scr", "x.hta", "x.com", "x.jar", "x.cpl", "x.msc", "x.wsf", "x.url", "x.chm",
    "x.docm", "x.xlsm", "FOTO.JPG.EXE", "virus.exe.", "virus.exe ", "x.appref-ms",
])
def test_detecta_ejecutables(nombre):
    assert es_ejecutable(nombre)


@pytest.mark.parametrize("nombre", ["foto.jpg", "doc.pdf", "musica.mp3", "hoja.xlsx", "texto.txt", "video.mp4"])
def test_no_ejecutables(nombre):
    assert not es_ejecutable(nombre)


def test_extensiones_extra_configurables():
    assert es_ejecutable("x.abc", extra=[".abc"])


def test_abrir_archivo_rechaza_ejecutable(entorno, config_prueba, monkeypatch):
    import os

    abiertos = []
    monkeypatch.setattr(os, "startfile", lambda ruta: abiertos.append(ruta), raising=False)
    (entorno["permitida"] / "instalador.exe").write_bytes(b"MZ")
    ctx = Contexto(config_prueba, entorno["validador"])
    abrir = next(h for h in herramientas_archivos() if h.nombre == "abrir_archivo")
    r = abrir.ejecutar(ctx, {"ruta": str(entorno["permitida"] / "instalador.exe")})
    assert not r.ok and "ejecutables" in r.mensaje
    assert abiertos == []


def test_abrir_archivo_en_descargas_pide_confirmacion(entorno, config_prueba):
    ctx = Contexto(config_prueba, entorno["validador"])
    abrir = next(h for h in herramientas_archivos() if h.nombre == "abrir_archivo")
    assert abrir.confirmacion(ctx, {"ruta": str(entorno["descargas"] / "factura.pdf")})
    assert abrir.confirmacion(ctx, {"ruta": str(entorno["permitida"] / "notas.txt")}) is None
