"""Calculadora segura: evalúa expresiones matemáticas sin usar eval().

Se analiza la expresión como árbol (ast) y solo se permiten números, operadores
aritméticos y una lista cerrada de funciones. Hay límites para que una expresión
enorme (como 9**9**9) no congele el equipo.
"""

from __future__ import annotations

import ast
import math
import operator
import re

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, error, esquema_objeto, exito

MAX_LARGO = 300
MAX_EXPONENTE = 10_000
MAX_DIGITOS = 400
MAX_FACTORIAL = 500

_BINARIOS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARIOS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _factorial(n):
    if float(n) != int(n) or n < 0:
        raise ValueError("el factorial solo existe para enteros no negativos")
    if n > MAX_FACTORIAL:
        raise ValueError(f"factorial demasiado grande (máximo {MAX_FACTORIAL})")
    return math.factorial(int(n))


_FUNCIONES = {
    "raiz": math.sqrt, "sqrt": math.sqrt, "abs": abs, "round": round, "redondear": round,
    "sin": math.sin, "sen": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log10, "log10": math.log10, "ln": math.log, "log2": math.log2, "exp": math.exp,
    "factorial": _factorial, "floor": math.floor, "ceil": math.ceil,
    "radianes": math.radians, "grados": math.degrees, "radians": math.radians, "degrees": math.degrees,
    "max": max, "min": min,
}
_CONSTANTES = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _normalizar(expresion: str) -> str:
    t = expresion.strip().lower()
    t = t.replace("×", "*").replace("÷", "/").replace("−", "-").replace("^", "**")
    t = t.replace("√", "raiz").replace("π", "pi")
    # "15% de 200" → (15/100)*200 ; "20%" suelto → (20/100)
    if not re.search(r"[a-z]\s*\(", t):
        t = re.sub(r"(\d),(\d)", r"\1.\2", t)  # coma decimal ("1,5"), solo si no hay funciones
    t = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*(?:de|of)\s*", r"(\1/100)*", t)
    # "20%" es porcentaje; "10 % 3" (seguido de número) es el resto de la división.
    t = re.sub(r"(\d+(?:\.\d+)?)\s*%(?!\s*[\d(])", r"(\1/100)", t)
    return t


def _evaluar(nodo):
    if isinstance(nodo, ast.Expression):
        return _evaluar(nodo.body)
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)) and not isinstance(nodo.value, bool):
        return nodo.value
    if isinstance(nodo, ast.Name) and nodo.id in _CONSTANTES:
        return _CONSTANTES[nodo.id]
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _UNARIOS:
        return _UNARIOS[type(nodo.op)](_evaluar(nodo.operand))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _BINARIOS:
        izquierda, derecha = _evaluar(nodo.left), _evaluar(nodo.right)
        if isinstance(nodo.op, ast.Pow):
            if abs(derecha) > MAX_EXPONENTE:
                raise ValueError("exponente demasiado grande")
            if abs(izquierda) > 1 and abs(derecha) * math.log10(abs(izquierda)) > MAX_DIGITOS:
                raise ValueError("el resultado sería demasiado grande")
        resultado = _BINARIOS[type(nodo.op)](izquierda, derecha)
        if isinstance(resultado, int) and abs(resultado) > 10 ** MAX_DIGITOS:
            raise ValueError("el resultado es demasiado grande")
        return resultado
    if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name)
            and nodo.func.id in _FUNCIONES and not nodo.keywords and len(nodo.args) <= 4):
        return _FUNCIONES[nodo.func.id](*[_evaluar(a) for a in nodo.args])
    raise ValueError("la expresión contiene algo que no es una operación matemática permitida")


def evaluar_expresion(expresion: str):
    """Devuelve el resultado numérico o lanza ValueError con un mensaje claro."""
    if not isinstance(expresion, str) or not expresion.strip():
        raise ValueError("la expresión está vacía")
    if len(expresion) > MAX_LARGO:
        raise ValueError(f"la expresión es demasiado larga (máximo {MAX_LARGO} caracteres)")
    texto = _normalizar(expresion)
    try:
        arbol = ast.parse(texto, mode="eval")
    except SyntaxError:
        raise ValueError("la expresión no está bien escrita") from None
    try:
        return _evaluar(arbol)
    except ZeroDivisionError:
        raise ValueError("división entre cero") from None
    except OverflowError:
        raise ValueError("el resultado es demasiado grande") from None
    except (TypeError, RecursionError):
        raise ValueError("la expresión no es válida") from None


def formatear_numero(valor) -> str:
    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            return str(valor)
        if valor.is_integer() and abs(valor) < 1e15:
            return f"{int(valor):,}".replace(",", " ")
        return f"{valor:.10g}"
    if isinstance(valor, int):
        return f"{valor:,}".replace(",", " ") if abs(valor) < 10 ** 30 else str(valor)
    return str(valor)


def calcular(ctx: Contexto, args: dict) -> Resultado:
    try:
        valor = evaluar_expresion(args["expresion"])
    except ValueError as e:
        return error(f"No pude calcular: {e}.")
    return exito(f"{args['expresion']} = {formatear_numero(valor)}")


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "calcular",
            "Calcula una expresión matemática. Admite + - * / % ^, paréntesis, '15% de 200', pi, e, "
            "raiz, sin, cos, tan (radianes; radianes(x)), log, ln, exp, abs, round, factorial, max, min.",
            esquema_objeto({
                "expresion": {"type": "string", "maxLength": MAX_LARGO},
            }, ["expresion"]),
            calcular,
        ),
    ]
