"""Atajo de teclado global con la API nativa de Windows (RegisterHotKey).

No instala ganchos de teclado ni necesita permisos de administrador.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
_ID_ATAJO = 0x4A41  # "JA"

_MODIFICADORES = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
    "shift": MOD_SHIFT, "mayus": MOD_SHIFT, "win": MOD_WIN,
}
_TECLAS = {
    "space": 0x20, "espacio": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
    "insert": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "pause": 0x13, "scrolllock": 0x91,
}


def interpretar_atajo(texto: str) -> tuple[int, int]:
    """'ctrl+space' → (modificadores, código virtual). Lanza ValueError si no es válido."""
    partes = [p.strip().lower() for p in texto.split("+") if p.strip()]
    if not partes:
        raise ValueError("Atajo vacío")
    mods, tecla = 0, None
    for p in partes:
        if p in _MODIFICADORES:
            mods |= _MODIFICADORES[p]
        elif tecla is None:
            if p in _TECLAS:
                tecla = _TECLAS[p]
            elif len(p) == 1 and p.isalnum():
                tecla = ord(p.upper())
            elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 24:
                tecla = 0x70 + int(p[1:]) - 1
            else:
                raise ValueError(f"Tecla desconocida: {p}")
        else:
            raise ValueError("El atajo solo puede tener una tecla principal")
    if tecla is None:
        raise ValueError("Falta la tecla principal")
    return mods, tecla


class AtajoGlobal(QObject):
    activado = Signal()

    def __init__(self, combinacion: str):
        super().__init__()
        self.combinacion = combinacion
        self._mods, self._tecla = interpretar_atajo(combinacion)
        self._hilo: threading.Thread | None = None
        self._id_hilo = 0
        self._listo = threading.Event()
        self._ok = False

    def iniciar(self) -> bool:
        self._hilo = threading.Thread(target=self._bucle, daemon=True, name="jarvis-atajo")
        self._hilo.start()
        self._listo.wait(3)
        return self._ok

    def detener(self) -> None:
        if self._id_hilo:
            ctypes.windll.user32.PostThreadMessageW(self._id_hilo, WM_QUIT, 0, 0)

    def _bucle(self) -> None:
        user32 = ctypes.windll.user32
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = wintypes.BOOL
        self._id_hilo = ctypes.windll.kernel32.GetCurrentThreadId()
        # RegisterHotKey y GetMessage deben ejecutarse en el mismo hilo.
        self._ok = bool(user32.RegisterHotKey(None, _ID_ATAJO, self._mods | MOD_NOREPEAT, self._tecla))
        self._listo.set()
        if not self._ok:
            return
        try:
            mensaje = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) > 0:
                if mensaje.message == WM_HOTKEY and mensaje.wParam == _ID_ATAJO:
                    self.activado.emit()
        finally:
            user32.UnregisterHotKey(None, _ID_ATAJO)
