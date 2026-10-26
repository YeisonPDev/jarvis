"""Creación de archivos nuevos: solo .txt, .md o .csv dentro de Documentos\\Jarvis, sin sobrescribir."""

from __future__ import annotations

import os

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, esquema_objeto, exito
from jarvis.seguridad.errores import ErrorSeguridad

EXTENSIONES_CREACION = {".txt", ".md", ".csv"}
_CARACTERES_PROHIBIDOS = set('<>:"/\\|?*')
_NOMBRES_RESERVADOS = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {
    f"lpt{i}" for i in range(1, 10)
}
MAX_SUFIJO = 1000


def validar_nombre_nuevo(nombre: object) -> str:
    """Valida que sea solo un nombre de archivo (sin carpetas). Agrega .txt si no tiene extensión."""
    if not isinstance(nombre, str) or not nombre.strip():
        raise ErrorSeguridad("El nombre del archivo está vacío.")
    nombre = nombre.strip()
    if any(c in _CARACTERES_PROHIBIDOS or ord(c) < 32 for c in nombre):
        raise ErrorSeguridad(
            "El nombre no puede incluir carpetas ni los caracteres < > : \" / \\ | ? *. "
            "Indica solo el nombre del archivo; siempre se guarda en Documentos\\Jarvis."
        )
    if nombre in (".", "..") or nombre.endswith((".", " ")):
        raise ErrorSeguridad("Nombre de archivo no válido.")
    base, ext = os.path.splitext(nombre)
    if not ext:
        nombre, ext = nombre + ".txt", ".txt"
        base = os.path.splitext(nombre)[0]
    if ext.lower() not in EXTENSIONES_CREACION:
        raise ErrorSeguridad("Solo puedo crear archivos .txt, .md o .csv.")
    if not base or base.split(".")[0].strip().lower() in _NOMBRES_RESERVADOS:
        raise ErrorSeguridad("Ese nombre está reservado por Windows.")
    if len(nombre) > 150:
        raise ErrorSeguridad("El nombre es demasiado largo (máximo 150 caracteres).")
    return nombre


def crear_archivo_seguro(carpeta: str, nombre: str, contenido: str, max_caracteres: int) -> str:
    """Crea el archivo sin sobrescribir nunca. Si existe, usa _2, _3... Devuelve la ruta creada."""
    nombre = validar_nombre_nuevo(nombre)
    if not isinstance(contenido, str):
        raise ErrorSeguridad("El contenido debe ser texto.")
    if len(contenido) > max_caracteres:
        raise ErrorSeguridad(f"El contenido supera el máximo de {max_caracteres} caracteres.")

    base, ext = os.path.splitext(nombre)
    codificacion = "utf-8-sig" if ext.lower() == ".csv" else "utf-8"  # BOM para que Excel lea tildes
    carpeta_nc = os.path.normcase(os.path.realpath(carpeta))
    for i in range(1, MAX_SUFIJO + 1):
        candidato = nombre if i == 1 else f"{base}_{i}{ext}"
        ruta = os.path.join(carpeta, candidato)
        # El archivo final debe quedar directamente dentro de la carpeta de salida.
        if os.path.normcase(os.path.dirname(os.path.realpath(ruta))) != carpeta_nc:
            continue
        try:
            # Modo "x": falla si ya existe algo con ese nombre (incluidos enlaces). Nunca sobrescribe.
            with open(ruta, "x", encoding=codificacion, newline="") as f:
                f.write(contenido)
            return ruta
        except FileExistsError:
            continue
    raise ErrorSeguridad("No encontré un nombre libre para el archivo.")


def preparar_carpeta_salida(ctx: Contexto) -> str:
    carpeta = ctx.config.carpeta_salida
    padre = os.path.dirname(carpeta.rstrip("\\/"))
    ctx.validador.validar(padre, tipo="carpeta")  # la carpeta padre (Documentos) debe ser válida
    os.makedirs(carpeta, exist_ok=True)
    return ctx.validador.validar(carpeta, tipo="carpeta")


def crear_archivo(ctx: Contexto, args: dict) -> Resultado:
    carpeta = preparar_carpeta_salida(ctx)
    ruta = crear_archivo_seguro(
        carpeta, args["nombre"], args["contenido"], int(ctx.config.limites.max_caracteres_creacion)
    )
    return exito(f"Archivo creado: {ruta}")


def _confirmar(ctx: Contexto, args: dict) -> str:
    vista = args.get("contenido", "")
    vista = vista[:150] + ("…" if len(vista) > 150 else "")
    return f"¿Crear el archivo '{args.get('nombre')}' en Documentos\\Jarvis?\nContenido: {vista}"


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "crear_archivo",
            "Crea un archivo nuevo .txt, .md o .csv en Documentos\\Jarvis (solo el nombre, sin carpetas).",
            esquema_objeto({
                "nombre": {"type": "string", "maxLength": 150},
                "contenido": {"type": "string"},
            }, ["nombre", "contenido"]),
            crear_archivo,
            confirmacion=_confirmar,
        ),
    ]
