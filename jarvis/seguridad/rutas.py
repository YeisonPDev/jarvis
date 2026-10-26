"""Validación de rutas: normalización, tipo de unidad, carpetas permitidas y bloqueadas."""

from __future__ import annotations

import ctypes
import os
import re
from collections.abc import Callable, Iterable

from jarvis.seguridad.errores import ErrorSeguridad
from jarvis.seguridad.lista_negra import ListaNegra, normalizar_texto

DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

_NOMBRES_UNIDAD = {
    DRIVE_REMOVABLE: "extraíble",
    DRIVE_REMOTE: "de red",
    DRIVE_CDROM: "de CD/DVD",
    DRIVE_RAMDISK: "de memoria RAM",
}


def obtener_tipo_unidad(raiz: str) -> int:
    """Llama a GetDriveTypeW. 'raiz' debe ser como 'C:\\'."""
    try:
        return int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(raiz)))
    except (AttributeError, OSError):
        return DRIVE_UNKNOWN


def _es_junction(ruta: str) -> bool:
    funcion = getattr(os.path, "isjunction", None)
    return bool(funcion and funcion(ruta))


def es_enlace(ruta: str) -> bool:
    """True si la ruta es un enlace simbólico o una junction."""
    return os.path.islink(ruta) or _es_junction(ruta)


def _preparar(carpeta: str) -> str:
    real = os.path.realpath(os.path.expandvars(carpeta))
    if real.startswith("\\\\?\\") and not real.upper().startswith("\\\\?\\UNC\\"):
        real = real[4:]
    return os.path.normcase(real).rstrip("\\/")


def _dentro(ruta_nc: str, carpeta_nc: str) -> bool:
    """Ambos argumentos ya normalizados con normcase y sin barra final."""
    ruta_nc = ruta_nc.rstrip("\\/")
    return ruta_nc == carpeta_nc or ruta_nc.startswith(carpeta_nc + "\\")


class ValidadorRutas:
    """Toda ruta que use una herramienta pasa por aquí antes de tocar el disco."""

    def __init__(
        self,
        permitidas: Iterable[str],
        bloqueadas: Iterable[str],
        lista_negra: ListaNegra,
        alias: dict[str, str] | None = None,
        base_relativa: str | None = None,
        descargas: str | None = None,
        tipo_unidad: Callable[[str], int] = obtener_tipo_unidad,
    ):
        self.permitidas = [_preparar(p) for p in permitidas if p]
        self.permitidas_originales = [p for p in permitidas if p]
        self.bloqueadas = [_preparar(b) for b in bloqueadas if b]
        self.lista_negra = lista_negra
        self.alias = {normalizar_texto(k): v for k, v in (alias or {}).items()}
        self.base_relativa = base_relativa or os.path.expanduser("~")
        self.descargas = _preparar(descargas) if descargas else None
        self.tipo_unidad = tipo_unidad

    @classmethod
    def desde_config(cls, config) -> "ValidadorRutas":
        return cls(
            permitidas=config.carpetas_permitidas,
            bloqueadas=config.carpetas_bloqueadas,
            lista_negra=ListaNegra.desde_dict(config.lista_negra),
            alias=config.alias_carpetas,
            descargas=config.carpeta_descargas,
        )

    # ------------------------------------------------------------------ #
    def _expandir_alias(self, ruta: str) -> str:
        partes = re.split(r"[\\/]", ruta, maxsplit=1)
        clave = normalizar_texto(partes[0].strip())
        if clave in self.alias:
            resto = partes[1] if len(partes) > 1 else ""
            return os.path.join(self.alias[clave], resto) if resto else self.alias[clave]
        return ruta

    def validar(self, ruta: object, tipo: str = "cualquiera", debe_existir: bool = True) -> str:
        """Devuelve la ruta real validada o lanza ErrorSeguridad.

        tipo: "archivo", "carpeta" o "cualquiera".
        """
        if not isinstance(ruta, str) or not ruta.strip():
            raise ErrorSeguridad("La ruta está vacía o no es texto.")
        if "\x00" in ruta or any(ord(c) < 32 for c in ruta):
            raise ErrorSeguridad("La ruta contiene caracteres no válidos.")

        cruda = ruta.strip().strip('"').strip()
        # Rutas UNC, de dispositivo o con prefijo \\?\ se rechazan antes de resolverlas.
        if cruda.startswith(("\\\\", "//", "\\/", "/\\")):
            raise ErrorSeguridad(
                "No se permiten rutas de red ni rutas UNC (\\\\servidor\\...). Solo discos locales."
            )
        cruda = os.path.expanduser(self._expandir_alias(cruda))

        unidad_cruda = os.path.splitdrive(cruda)[0]
        if unidad_cruda and not os.path.isabs(cruda):
            raise ErrorSeguridad("Ruta ambigua (por ejemplo 'C:archivo'). Usa una ruta completa.")
        if not os.path.isabs(cruda):
            cruda = os.path.join(self.base_relativa, cruda)

        # Si la unidad original no es un disco fijo, rechazar aunque realpath la traduzca.
        self._verificar_unidad(os.path.splitdrive(cruda)[0])

        # realpath resuelve "..", enlaces simbólicos y junctions.
        real = os.path.realpath(cruda)
        if real.startswith("\\\\?\\") and not real.upper().startswith("\\\\?\\UNC\\"):
            real = real[4:]
        if real.startswith("\\\\"):
            raise ErrorSeguridad("La ruta apunta a una ubicación de red. Solo se permiten discos locales.")

        unidad, resto = os.path.splitdrive(real)
        if len(unidad) != 2 or unidad[1] != ":":
            raise ErrorSeguridad("La ruta no está en un disco local con letra de unidad.")
        if ":" in resto:
            raise ErrorSeguridad("No se permiten flujos alternativos de datos (':' en el nombre).")
        self._verificar_unidad(unidad)

        real_nc = os.path.normcase(real).rstrip("\\/") or os.path.normcase(real)

        for bloqueada in self.bloqueadas:
            if _dentro(real_nc, bloqueada):
                raise ErrorSeguridad(
                    "Esa ubicación es una carpeta del sistema protegida (Windows, Program Files, "
                    "ProgramData o AppData) y no se puede acceder."
                )

        raiz = next((p for p in self.permitidas if _dentro(real_nc, p)), None)
        if raiz is None:
            raise ErrorSeguridad(
                "Esa ruta está fuera de las carpetas permitidas: "
                + ", ".join(self.permitidas_originales)
            )

        relativa = real[len(raiz):].strip("\\/")
        partes = [p for p in re.split(r"[\\/]", relativa) if p]
        motivo = self.lista_negra.motivo(partes)
        if motivo:
            raise ErrorSeguridad(f"Acceso denegado: {motivo}.")

        if debe_existir:
            if not os.path.exists(real):
                raise ErrorSeguridad(f"No existe: {real}")
            if tipo == "archivo" and not os.path.isfile(real):
                raise ErrorSeguridad(f"No es un archivo: {real}")
            if tipo == "carpeta" and not os.path.isdir(real):
                raise ErrorSeguridad(f"No es una carpeta: {real}")
        return real

    def _verificar_unidad(self, unidad: str) -> None:
        if not unidad:
            return
        if len(unidad) != 2 or unidad[1] != ":":
            raise ErrorSeguridad("La ruta no está en un disco local con letra de unidad.")
        tipo = self.tipo_unidad(unidad.upper() + "\\")
        if tipo != DRIVE_FIXED:
            nombre = _NOMBRES_UNIDAD.get(tipo, "desconocida o inexistente")
            raise ErrorSeguridad(
                f"La unidad {unidad.upper()} es {nombre}. Solo se permiten discos locales fijos."
            )

    def es_permitida_silenciosa(self, ruta: str, tipo: str = "cualquiera") -> bool:
        try:
            self.validar(ruta, tipo)
            return True
        except ErrorSeguridad:
            return False

    def esta_en_descargas(self, ruta_real: str) -> bool:
        return bool(self.descargas) and _dentro(os.path.normcase(ruta_real), self.descargas)

    def esta_bloqueada(self, ruta_real: str) -> bool:
        nc = os.path.normcase(ruta_real)
        return any(_dentro(nc, b) for b in self.bloqueadas)
