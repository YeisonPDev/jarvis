"""Definición común de herramientas, validación de argumentos y resultado estándar."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from jarvis.seguridad.errores import ErrorSeguridad

if TYPE_CHECKING:
    from jarvis.config import Config
    from jarvis.seguridad.rutas import ValidadorRutas


@dataclass
class Resultado:
    ok: bool
    mensaje: str
    # Texto proveniente de archivos o nombres de archivo: se entrega al modelo marcado como no confiable.
    datos_no_confiables: str | None = None
    origen: str = ""


def exito(mensaje: str, datos: str | None = None, origen: str = "") -> Resultado:
    return Resultado(True, mensaje, datos, origen)


def error(mensaje: str) -> Resultado:
    return Resultado(False, mensaje)


@dataclass
class Contexto:
    """Estado compartido por las herramientas durante un pedido."""

    config: "Config"
    validador: "ValidadorRutas"
    pedido: str = ""
    archivo_leido: bool = False  # se leyeron datos privados (archivos, notificaciones)
    externo_leido: bool = False  # se leyó contenido de internet
    # Puente hacia la interfaz (p. ej. para abrir los ajustes). None en pruebas.
    interfaz: object | None = None


FuncionHerramienta = Callable[[Contexto, dict], Resultado]
FuncionConfirmacion = Callable[[Contexto, dict], "str | None"]


@dataclass
class Herramienta:
    nombre: str
    descripcion: str
    parametros: dict
    funcion: FuncionHerramienta
    # Devuelve la pregunta para el usuario si la acción requiere confirmación, o None.
    confirmacion: FuncionConfirmacion | None = None
    # True si la herramienta entrega contenido de archivos al modelo.
    lee_contenido: bool = False
    # True si entrega al modelo contenido de internet (no confiable, pero no privado).
    lee_externo: bool = False

    def esquema(self) -> dict:
        return {"nombre": self.nombre, "descripcion": self.descripcion, "parametros": self.parametros}

    def ejecutar(self, ctx: Contexto, args: dict) -> Resultado:
        """Nunca lanza excepciones: todo error se convierte en un Resultado claro."""
        try:
            resultado = self.funcion(ctx, args)
            if not isinstance(resultado, Resultado):
                return error("La herramienta devolvió un resultado inválido.")
            return resultado
        except ErrorSeguridad as e:
            return error(str(e))
        except PermissionError:
            return error("Windows negó el acceso a ese recurso.")
        except FileNotFoundError:
            return error("No se encontró el archivo o carpeta indicada.")
        except Exception as e:  # noqa: BLE001 - la herramienta nunca debe romper el ciclo
            return error(f"Error interno al ejecutar {self.nombre} ({type(e).__name__}).")


@dataclass
class RegistroHerramientas:
    herramientas: dict[str, Herramienta] = field(default_factory=dict)

    def registrar(self, *nuevas: Herramienta) -> None:
        for h in nuevas:
            self.herramientas[h.nombre] = h

    def obtener(self, nombre: str) -> Herramienta | None:
        return self.herramientas.get(nombre)

    def esquemas(self) -> list[dict]:
        return [h.esquema() for h in self.herramientas.values()]

    def nombres(self) -> list[str]:
        return list(self.herramientas)


# ---------------------------------------------------------------------- #
# Validación de argumentos (subconjunto de JSON Schema que usamos)
# ---------------------------------------------------------------------- #
def validar_argumentos(esquema: dict, args: object) -> tuple[dict | None, str | None]:
    """Devuelve (argumentos_limpios, None) o (None, mensaje_de_error)."""
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return None, "Los argumentos deben ser un objeto JSON con nombre: valor."

    props: dict = esquema.get("properties", {})
    requeridos: list = esquema.get("required", [])

    desconocidos = [k for k in args if k not in props]
    if desconocidos:
        return None, (
            f"Argumentos desconocidos: {', '.join(desconocidos)}. "
            f"Los válidos son: {', '.join(props) or '(ninguno)'}."
        )
    faltan = [r for r in requeridos if args.get(r) in (None, "")]
    if faltan:
        return None, f"Faltan argumentos obligatorios: {', '.join(faltan)}."

    limpios: dict = {}
    for clave, valor in args.items():
        if valor is None:
            continue
        regla = props[clave]
        tipo = regla.get("type")
        if tipo == "string":
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                valor = str(valor)
            if not isinstance(valor, str):
                return None, f"'{clave}' debe ser texto."
            if "enum" in regla:
                normal = valor.strip().lower()
                if normal not in regla["enum"]:
                    return None, f"'{clave}' debe ser uno de: {', '.join(regla['enum'])}."
                valor = normal
            maximo = regla.get("maxLength")
            if maximo and len(valor) > maximo:
                return None, f"'{clave}' es demasiado largo (máximo {maximo} caracteres)."
        elif tipo in ("integer", "number"):
            if isinstance(valor, bool):
                return None, f"'{clave}' debe ser un número."
            if isinstance(valor, str):
                texto = valor.strip().rstrip("%").strip()
                if not re.fullmatch(r"-?\d+(\.\d+)?", texto):
                    return None, f"'{clave}' debe ser un número."
                valor = float(texto)
            if not isinstance(valor, (int, float)):
                return None, f"'{clave}' debe ser un número."
            if tipo == "integer":
                if float(valor) != int(valor):
                    return None, f"'{clave}' debe ser un número entero."
                valor = int(valor)
            if "minimum" in regla and valor < regla["minimum"]:
                return None, f"'{clave}' debe ser mayor o igual a {regla['minimum']}."
            if "maximum" in regla and valor > regla["maximum"]:
                return None, f"'{clave}' debe ser menor o igual a {regla['maximum']}."
        elif tipo == "boolean":
            if isinstance(valor, str) and valor.lower() in ("true", "false"):
                valor = valor.lower() == "true"
            if not isinstance(valor, bool):
                return None, f"'{clave}' debe ser true o false."
        limpios[clave] = valor
    return limpios, None


def esquema_objeto(propiedades: dict, requeridos: list[str] | None = None) -> dict:
    # Compacto a propósito: cada token cuenta en el límite por minuto del proveedor.
    # Los argumentos desconocidos los rechaza validar_argumentos, no el esquema.
    esquema = {"type": "object", "properties": propiedades}
    if requeridos:
        esquema["required"] = requeridos
    return esquema
