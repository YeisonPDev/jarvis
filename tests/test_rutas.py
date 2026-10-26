"""Validación de rutas: red, UNC, '..', enlaces, junctions, unidades y carpetas bloqueadas."""

import os
from pathlib import Path

import pytest

from jarvis.config import carpetas_bloqueadas_obligatorias
from jarvis.seguridad.errores import ErrorSeguridad
from jarvis.seguridad.lista_negra import ListaNegra
from jarvis.seguridad.rutas import (
    DRIVE_CDROM, DRIVE_FIXED, DRIVE_REMOTE, DRIVE_REMOVABLE, ValidadorRutas,
)


def test_ruta_permitida_valida(entorno):
    real = entorno["validador"].validar(str(entorno["permitida"] / "notas.txt"), tipo="archivo")
    assert real.lower().endswith("notas.txt")


def test_ruta_relativa_se_resuelve_dentro_de_la_base(entorno):
    real = entorno["validador"].validar("notas.txt", tipo="archivo")
    assert os.path.normcase(real) == os.path.normcase(str(entorno["permitida"] / "notas.txt"))


@pytest.mark.parametrize("ruta", [
    r"\\servidor\compartida\archivo.txt",
    "//servidor/compartida/archivo.txt",
    r"\\?\UNC\servidor\compartida\archivo.txt",
    r"\\?\C:\Windows\system.ini",
    r"\\.\C:\Windows\system.ini",
    r"\\localhost\c$\Users",
    r"\\127.0.0.1\c$",
])
def test_rechaza_rutas_unc_y_de_dispositivo(entorno, ruta):
    with pytest.raises(ErrorSeguridad):
        entorno["validador"].validar(ruta, debe_existir=False)


def test_rechaza_escape_con_puntos(entorno):
    ruta = str(entorno["permitida"]) + r"\..\fuera\secreto.txt"
    with pytest.raises(ErrorSeguridad, match="fuera de las carpetas permitidas"):
        entorno["validador"].validar(ruta)


def test_rechaza_escape_relativo_con_puntos(entorno):
    with pytest.raises(ErrorSeguridad):
        entorno["validador"].validar(r"..\fuera\secreto.txt")


def test_rechaza_ruta_fuera_de_permitidas(entorno):
    with pytest.raises(ErrorSeguridad, match="fuera de las carpetas permitidas"):
        entorno["validador"].validar(str(entorno["fuera"] / "secreto.txt"))


def test_rechaza_carpeta_bloqueada_dentro_de_permitida(entorno):
    with pytest.raises(ErrorSeguridad, match="protegida"):
        entorno["validador"].validar(str(entorno["bloqueada"] / "x.txt"))


def test_rechaza_junction_que_sale_de_la_carpeta(entorno):
    import _winapi

    enlace = entorno["permitida"] / "atajo_junction"
    _winapi.CreateJunction(str(entorno["fuera"]), str(enlace))
    assert (enlace / "secreto.txt").exists()  # el archivo es alcanzable por la junction…
    with pytest.raises(ErrorSeguridad):  # …pero la validación lo rechaza
        entorno["validador"].validar(str(enlace / "secreto.txt"))


def test_rechaza_enlace_simbolico_que_sale_de_la_carpeta(entorno):
    enlace = entorno["permitida"] / "enlace.txt"
    try:
        os.symlink(entorno["fuera"] / "secreto.txt", enlace)
    except OSError:
        pytest.skip("Windows no permite crear enlaces simbólicos sin modo desarrollador")
    with pytest.raises(ErrorSeguridad):
        entorno["validador"].validar(str(enlace))


@pytest.mark.parametrize("tipo", [DRIVE_REMOTE, DRIVE_REMOVABLE, DRIVE_CDROM, 0, 1])
def test_rechaza_unidades_que_no_son_fijas(entorno, tipo):
    validador = entorno["validador"]
    validador.tipo_unidad = lambda raiz: tipo
    with pytest.raises(ErrorSeguridad, match="Solo se permiten discos locales"):
        validador.validar(str(entorno["permitida"] / "notas.txt"))


def test_unidad_de_red_mapeada_con_letra(entorno):
    """Una unidad Z: de red se rechaza aunque esté dentro de 'permitidas'."""
    validador = ValidadorRutas(
        permitidas=[r"Z:\Compartido"], bloqueadas=[], lista_negra=ListaNegra(),
        tipo_unidad=lambda raiz: DRIVE_REMOTE if raiz.upper().startswith("Z") else DRIVE_FIXED,
    )
    with pytest.raises(ErrorSeguridad, match="de red"):
        validador.validar(r"Z:\Compartido\doc.txt", debe_existir=False)


def test_rechaza_ruta_ambigua_con_letra(entorno):
    with pytest.raises(ErrorSeguridad, match="ambigua"):
        entorno["validador"].validar("C:notas.txt", debe_existir=False)


def test_rechaza_flujo_alternativo(entorno):
    with pytest.raises(ErrorSeguridad):
        entorno["validador"].validar(str(entorno["permitida"] / "notas.txt") + ":oculto", debe_existir=False)


def test_rechaza_ruta_vacia_o_no_texto(entorno):
    for valor in ("", "   ", None, 123):
        with pytest.raises(ErrorSeguridad):
            entorno["validador"].validar(valor)


def test_carpetas_del_sistema_siempre_bloqueadas():
    """Aunque se permitiera todo el disco C:, Windows/Program Files/ProgramData/AppData quedan bloqueadas."""
    validador = ValidadorRutas(
        permitidas=["C:\\"], bloqueadas=carpetas_bloqueadas_obligatorias(), lista_negra=ListaNegra(),
    )
    inicio = Path.home()
    for ruta in (
        os.environ.get("SystemRoot", r"C:\Windows") + r"\System32\drivers\etc\hosts",
        r"C:\Program Files\algo.txt",
        r"C:\Program Files (x86)\algo.txt",
        r"C:\ProgramData\algo.txt",
        str(inicio / "AppData" / "Roaming" / "algo.txt"),
        str(inicio / "AppData" / "Local" / "algo.txt"),
    ):
        with pytest.raises(ErrorSeguridad, match="protegida"):
            validador.validar(ruta, debe_existir=False)


def test_tipo_de_archivo_o_carpeta(entorno):
    v = entorno["validador"]
    with pytest.raises(ErrorSeguridad, match="No es una carpeta"):
        v.validar(str(entorno["permitida"] / "notas.txt"), tipo="carpeta")
    with pytest.raises(ErrorSeguridad, match="No es un archivo"):
        v.validar(str(entorno["permitida"]), tipo="archivo")


def test_detecta_descargas(entorno):
    v = entorno["validador"]
    real = v.validar(str(entorno["descargas"] / "factura.pdf"))
    assert v.esta_en_descargas(real)
    assert not v.esta_en_descargas(v.validar(str(entorno["permitida"] / "notas.txt")))
