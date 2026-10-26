"""Abrir programas: solo los de la lista blanca de config.json."""

from __future__ import annotations

import os
import re

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, error, esquema_objeto, exito
from jarvis.seguridad.lista_negra import normalizar_texto


_RELLENO = re.compile(r"\b(el|la|los|las|programa|aplicacion|app|de|mi|microsoft|abre|abrir)\b")


def _limpiar(texto: str) -> str:
    return " ".join(_RELLENO.sub(" ", normalizar_texto(texto)).split())


def buscar_programa(programas: dict[str, str], nombre: str) -> tuple[str, str] | None:
    """Busca por nombre amigable sin importar mayúsculas ni tildes.

    Primero exacto; luego ignorando palabras de relleno ("el", "programa", "microsoft"...);
    por último, si el pedido contiene exactamente un nombre de la lista ("excel 2016").
    Nunca abre nada que no esté en la lista.
    """
    objetivo = normalizar_texto(nombre).strip()
    for clave, destino in programas.items():
        if normalizar_texto(clave).strip() == objetivo:
            return clave, destino
    limpio = _limpiar(nombre)
    for clave, destino in programas.items():
        if limpio and _limpiar(clave) == limpio:
            return clave, destino
    contenidos = {destino: clave for clave, destino in programas.items()
                  if _limpiar(clave) and re.search(rf"\b{re.escape(_limpiar(clave))}\b", limpio)}
    if len(contenidos) == 1:  # solo si no hay ambigüedad
        destino, clave = next(iter(contenidos.items()))
        return clave, destino
    return None


def abrir_programa(ctx: Contexto, args: dict) -> Resultado:
    programas = ctx.config.programas
    encontrado = buscar_programa(programas, args["nombre"])
    if encontrado is None:
        disponibles = ", ".join(programas) or "(la lista está vacía)"
        return error(
            f"'{args['nombre']}' no está en la lista de programas permitidos. "
            f"Disponibles: {disponibles}. El usuario puede agregar más en config.json."
        )
    clave, destino = encontrado
    # os.startfile no interpreta argumentos ni comandos de consola: solo abre el destino.
    os.startfile(os.path.expandvars(destino))  # noqa: S606
    return exito(f"Abrí {clave}.")


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "abrir_programa",
            "Abre un programa de la lista permitida por el usuario (por nombre amigable).",
            esquema_objeto({
                "nombre": {"type": "string", "maxLength": 100},
            }, ["nombre"]),
            abrir_programa,
        ),
    ]
