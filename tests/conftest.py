"""Utilidades comunes para las pruebas."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.config import Config, Limites  # noqa: E402
from jarvis.seguridad.lista_negra import ListaNegra  # noqa: E402
from jarvis.seguridad.rutas import DRIVE_FIXED, ValidadorRutas  # noqa: E402


def siempre_fijo(_raiz: str) -> int:
    return DRIVE_FIXED


@pytest.fixture
def entorno(tmp_path):
    """Estructura de prueba: una carpeta permitida, una de descargas, una externa y una bloqueada.

    tmp_path está dentro de AppData, así que estas pruebas usan su propia lista de bloqueadas.
    """
    permitida = tmp_path / "permitida"
    descargas = permitida / "Descargas"
    fuera = tmp_path / "fuera"
    bloqueada = permitida / "sistema_bloqueado"
    for c in (permitida, descargas, fuera, bloqueada):
        c.mkdir()
    (permitida / "notas.txt").write_text("hola", encoding="utf-8")
    (descargas / "factura.pdf").write_bytes(b"%PDF-1.4")
    (fuera / "secreto.txt").write_text("no deberías leer esto", encoding="utf-8")
    (bloqueada / "x.txt").write_text("x", encoding="utf-8")

    validador = ValidadorRutas(
        permitidas=[str(permitida)],
        bloqueadas=[str(bloqueada)],
        lista_negra=ListaNegra(),
        descargas=str(descargas),
        base_relativa=str(permitida),
        tipo_unidad=siempre_fijo,
    )
    return {
        "raiz": tmp_path, "permitida": permitida, "descargas": descargas,
        "fuera": fuera, "bloqueada": bloqueada, "validador": validador,
    }


@pytest.fixture
def config_prueba(entorno):
    salida = entorno["permitida"] / "Jarvis"
    return Config(
        proveedor="groq", modelo="prueba", api_key="",
        carpetas_permitidas=[str(entorno["permitida"])],
        carpetas_bloqueadas=[str(entorno["bloqueada"])],
        carpeta_salida=str(salida),
        carpeta_descargas=str(entorno["descargas"]),
        programas={"calculadora": "calc.exe"},
        limites=Limites(),
    )
