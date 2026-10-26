"""Creación de archivos: nunca sobrescribe, solo .txt/.md/.csv y siempre en la carpeta de salida."""

import pytest

from jarvis.herramientas.base import Contexto
from jarvis.herramientas.creacion import (
    crear_archivo, crear_archivo_seguro, herramientas, validar_nombre_nuevo,
)
from jarvis.seguridad.errores import ErrorSeguridad


def test_crea_archivo(tmp_path):
    ruta = crear_archivo_seguro(str(tmp_path), "lista.txt", "uno", 1000)
    assert (tmp_path / "lista.txt").read_text(encoding="utf-8") == "uno"
    assert ruta.endswith("lista.txt")


def test_nunca_sobrescribe_y_agrega_sufijos(tmp_path):
    (tmp_path / "lista.txt").write_text("original", encoding="utf-8")
    r2 = crear_archivo_seguro(str(tmp_path), "lista.txt", "segundo", 1000)
    r3 = crear_archivo_seguro(str(tmp_path), "lista.txt", "tercero", 1000)
    assert r2.endswith("lista_2.txt") and r3.endswith("lista_3.txt")
    assert (tmp_path / "lista.txt").read_text(encoding="utf-8") == "original"


def test_no_sobrescribe_aunque_cambien_mayusculas(tmp_path):
    (tmp_path / "Notas.md").write_text("original", encoding="utf-8")
    ruta = crear_archivo_seguro(str(tmp_path), "notas.md", "nuevo", 1000)
    assert ruta.endswith("notas_2.md")
    assert (tmp_path / "Notas.md").read_text(encoding="utf-8") == "original"


def test_agrega_txt_si_no_tiene_extension():
    assert validar_nombre_nuevo("recordatorio") == "recordatorio.txt"


@pytest.mark.parametrize("nombre", [
    "virus.exe", "script.ps1", "datos.json", "pagina.html", "macro.bat", "doc.docx", "x.py", "a.lnk",
])
def test_rechaza_extensiones_no_permitidas(nombre):
    with pytest.raises(ErrorSeguridad, match=r"\.txt, \.md o \.csv"):
        validar_nombre_nuevo(nombre)


@pytest.mark.parametrize("nombre", [
    r"..\fuera.txt", "../fuera.txt", r"C:\Windows\x.txt", r"sub\x.txt", "a:b.txt", "x?.txt",
    r"\\servidor\x.txt", "..", ".", "con.txt", "NUL.md", "com1.csv", "nombre.txt.", "",
])
def test_rechaza_nombres_peligrosos(nombre):
    with pytest.raises(ErrorSeguridad):
        validar_nombre_nuevo(nombre)


def test_limite_de_contenido(tmp_path):
    with pytest.raises(ErrorSeguridad, match="máximo"):
        crear_archivo_seguro(str(tmp_path), "grande.txt", "x" * 101, 100)


def test_herramienta_crea_en_carpeta_de_salida(entorno, config_prueba):
    ctx = Contexto(config_prueba, entorno["validador"], pedido="crea una lista")
    r = crear_archivo(ctx, {"nombre": "compras.csv", "contenido": "pan,leche"})
    assert r.ok
    assert (entorno["permitida"] / "Jarvis" / "compras.csv").exists()


def test_herramienta_no_escribe_fuera_aunque_salida_sea_junction(entorno, config_prueba):
    """Si alguien reemplaza Documentos\\Jarvis por una junction hacia fuera, se rechaza."""
    import _winapi

    salida = entorno["permitida"] / "Jarvis"
    _winapi.CreateJunction(str(entorno["fuera"]), str(salida))
    ctx = Contexto(config_prueba, entorno["validador"])
    r = herramientas()[0].ejecutar(ctx, {"nombre": "x.txt", "contenido": "x"})
    assert not r.ok
    assert not (entorno["fuera"] / "x.txt").exists()
