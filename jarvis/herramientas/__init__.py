"""Herramientas disponibles para el modelo. No existe ninguna para borrar, mover,
renombrar o modificar archivos, ni para ejecutar comandos de consola."""

from jarvis.herramientas import (
    ajustes, archivos, calculo, captura, creacion, informacion, multimedia, notificaciones,
    programas, sistema, tiempo, web,
)
from jarvis.herramientas.base import RegistroHerramientas


def crear_registro() -> RegistroHerramientas:
    registro = RegistroHerramientas()
    for modulo in (
        archivos, creacion, programas, sistema, multimedia, web, captura, ajustes,
        calculo, tiempo, notificaciones, informacion,
    ):
        registro.registrar(*modulo.herramientas())
    return registro
