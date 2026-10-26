"""Archivos sensibles que nunca se leen ni se abren, y extensiones ejecutables."""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterable


def normalizar_texto(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres de forma robusta."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_nombre(nombre: str) -> str:
    # Windows ignora puntos y espacios finales: "virus.exe. " equivale a "virus.exe".
    return normalizar_texto(nombre).rstrip(". ")


EXTENSIONES_EJECUTABLES_BASE = {
    ".exe", ".bat", ".cmd", ".com", ".ps1", ".psm1", ".psd1", ".ps1xml", ".vbs", ".vbe", ".vb",
    ".js", ".jse", ".wsf", ".wsh", ".ws", ".msi", ".msp", ".mst", ".lnk", ".url", ".reg", ".py",
    ".pyw", ".pyc", ".scr", ".hta", ".cpl", ".jar", ".dll", ".sys", ".drv", ".ocx", ".msc", ".inf",
    ".pif", ".gadget", ".application", ".appref-ms", ".appx", ".appxbundle", ".msix",
    ".msixbundle", ".scf", ".chm", ".settingcontent-ms", ".search-ms", ".library-ms", ".sh",
    ".bash", ".iso", ".img", ".vhd", ".vhdx", ".docm", ".dotm", ".xlsm", ".xltm", ".xlam",
    ".pptm", ".potm", ".ppam", ".sldm", ".diagcab", ".xll", ".rdp",
}

_EXTENSIONES_PROTEGIDAS = {
    ".pem", ".key", ".ppk", ".pfx", ".p12", ".kdbx", ".kdb", ".keystore", ".jks", ".gpg",
    ".pgp", ".asc", ".ovpn", ".crt", ".cer", ".der", ".p7b",
}

_NOMBRES_PROTEGIDOS = {
    ".env", ".netrc", "_netrc", ".git-credentials", ".npmrc", ".pypirc", ".pgpass", "credentials",
    "known_hosts", "authorized_keys", "wallet.dat",
    # Bases de datos de navegadores (Chrome, Edge, Brave, Firefox)
    "login data", "login data for account", "web data", "cookies", "history", "local state",
    "key3.db", "key4.db", "logins.json", "cookies.sqlite", "places.sqlite", "formhistory.sqlite",
    "cert9.db", "signons.sqlite",
}

_PREFIJOS_PROTEGIDOS = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}

_PALABRAS_PROTEGIDAS = {
    "password", "passwd", "contrasena", "clave", "secret", "token", "credential", "credencial",
}

_CARPETAS_PROTEGIDAS = {
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", "user data",
    # Billeteras de criptomonedas
    "wallets", "wallet", ".bitcoin", "bitcoin", ".ethereum", "ethereum", "monero", "electrum",
    "exodus", "atomic", "metamask", "ledger live", "trezor", "phantom",
}


def _normalizar_lista(valores: Iterable[str]) -> set[str]:
    return {normalizar_nombre(v) for v in valores if v and v.strip()}


class ListaNegra:
    """Decide si un nombre de archivo o carpeta está protegido."""

    def __init__(
        self,
        extensiones: Iterable[str] = (),
        nombres: Iterable[str] = (),
        prefijos: Iterable[str] = (),
        palabras: Iterable[str] = (),
        carpetas: Iterable[str] = (),
    ):
        # Los valores base siempre se aplican; config.json solo puede agregar.
        self.extensiones = _normalizar_lista(_EXTENSIONES_PROTEGIDAS) | _normalizar_lista(extensiones)
        self.nombres = _normalizar_lista(_NOMBRES_PROTEGIDOS) | _normalizar_lista(nombres)
        self.prefijos = _normalizar_lista(_PREFIJOS_PROTEGIDOS) | _normalizar_lista(prefijos)
        self.palabras = _normalizar_lista(_PALABRAS_PROTEGIDAS) | _normalizar_lista(palabras)
        self.carpetas = _normalizar_lista(_CARPETAS_PROTEGIDAS) | _normalizar_lista(carpetas)

    @classmethod
    def desde_dict(cls, datos: dict | None) -> "ListaNegra":
        datos = datos or {}
        return cls(
            extensiones=datos.get("extensiones", []),
            nombres=datos.get("nombres", []),
            prefijos=datos.get("prefijos", []),
            palabras=datos.get("palabras", []),
            carpetas=datos.get("carpetas", []),
        )

    def motivo_nombre(self, nombre: str) -> str | None:
        """Revisa un único componente de ruta. Devuelve el motivo del bloqueo o None."""
        n = normalizar_nombre(nombre)
        if not n:
            return None
        if n in self.carpetas:
            return f"'{nombre}' es una carpeta protegida (credenciales o billeteras)"
        if n in self.nombres or any(n.startswith(p) for p in self.prefijos):
            return f"'{nombre}' es un archivo protegido (credenciales o datos privados)"
        if any(p in n for p in self.palabras):
            return f"'{nombre}' parece contener credenciales por su nombre"
        if os.path.splitext(n)[1] in self.extensiones:
            return f"'{nombre}' es una llave o certificado protegido"
        return None

    def motivo(self, partes: Iterable[str]) -> str | None:
        """Revisa todos los componentes (carpetas y archivo) de una ruta relativa."""
        for parte in partes:
            m = self.motivo_nombre(parte)
            if m:
                return m
        return None


def es_ejecutable(ruta: str, extra: Iterable[str] = ()) -> bool:
    """True si la extensión del archivo es ejecutable o peligrosa de abrir."""
    nombre = normalizar_nombre(os.path.basename(ruta))
    ext = os.path.splitext(nombre)[1]
    return ext in EXTENSIONES_EJECUTABLES_BASE or ext in _normalizar_lista(extra)
