"""Notificaciones de Windows (las del centro de notificaciones), solo lectura.

Se leen de la base de datos de notificaciones del usuario actual, abierta en modo
solo lectura: Jarvis no descarta ni modifica ninguna. El texto de las notificaciones
(mensajes de otras personas) se entrega al modelo marcado como DATOS NO CONFIABLES.
"""

from __future__ import annotations

import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, error, esquema_objeto, exito

_NOMBRES_APPS = {
    "screensketch": "Recortes", "whatsappdesktop": "WhatsApp", "whatsapp": "WhatsApp",
    "msteams": "Teams", "teams": "Teams", "outlook": "Outlook", "chrome": "Chrome",
    "msedge": "Edge", "microsoftedge": "Edge", "spotify": "Spotify", "windowsstore": "Microsoft Store",
    "securityhealthui": "Seguridad de Windows", "windows.defender": "Seguridad de Windows",
    "telegramdesktop": "Telegram", "discord": "Discord", "people": "Contactos",
    "windowscommunicationsapps": "Correo", "alarms": "Reloj",
}


def ruta_base_datos() -> str:
    local = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    return os.path.join(local, "Microsoft", "Windows", "Notifications", "wpndatabase.db")


def nombre_app(identificador: str) -> str:
    """'5319275A.WhatsAppDesktop_cw5n1h2txyewy!App' → 'WhatsApp'."""
    base = identificador.split("!")[0].split("_")[0]
    partes = [p for p in re.split(r"[.\\]", base) if p and not p.isdigit() and p.lower() not in ("exe", "microsoft", "app")]
    for parte in reversed(partes):
        if parte.lower() in _NOMBRES_APPS:
            return _NOMBRES_APPS[parte.lower()]
    candidato = partes[-1] if partes else identificador
    if re.fullmatch(r"[0-9A-F]{6,}", candidato) or candidato.startswith("{"):
        return "Aplicación"
    return _NOMBRES_APPS.get(candidato.lower(), candidato)


def textos_de_toast(payload: bytes | str) -> list[str]:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")
    try:
        raiz = ET.fromstring(payload)
    except ET.ParseError:
        return []
    textos = [" ".join((t.text or "").split()) for t in raiz.iter("text")]
    return [t for t in textos if t]


def _desde_filetime(valor: int) -> datetime:
    return (datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=valor / 10)).astimezone()


def leer_notificaciones(ruta: str, limite: int) -> list[tuple[datetime, str, list[str]]]:
    conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True, timeout=3)
    try:
        filas = conexion.execute(
            "SELECT h.PrimaryId, n.ArrivalTime, n.Payload FROM Notification n "
            "JOIN NotificationHandler h ON h.RecordId = n.HandlerId "
            "WHERE n.Type = 'toast' ORDER BY n.ArrivalTime DESC LIMIT ?",
            (limite,),
        ).fetchall()
    finally:
        conexion.close()
    resultado = []
    for app, llegada, payload in filas:
        textos = textos_de_toast(payload or b"")
        if textos:
            resultado.append((_desde_filetime(int(llegada or 0)), nombre_app(str(app)), textos))
    return resultado


def ver_notificaciones(ctx: Contexto, args: dict) -> Resultado:
    limite = int(args.get("limite") or 10)
    ruta = ruta_base_datos()
    if not os.path.isfile(ruta):
        return error("No encontré la base de datos de notificaciones de Windows.")
    try:
        notificaciones = leer_notificaciones(ruta, limite)
    except sqlite3.Error:
        return error("Windows no permitió leer las notificaciones en este momento. Intenta de nuevo.")
    if not notificaciones:
        return exito("No tienes notificaciones en el centro de notificaciones.")
    lineas = []
    for momento, app, textos in notificaciones:
        contenido = " — ".join(textos)[:300]
        lineas.append(f"[{momento:%d/%m %H:%M}] {app}: {contenido}")
    return exito(f"Hay {len(notificaciones)} notificaciones recientes (de la más nueva a la más vieja).",
                 "\n".join(lineas), origen="notificaciones de Windows")


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "ver_notificaciones",
            "Lee las notificaciones recientes del centro de notificaciones de Windows (solo lectura).",
            esquema_objeto({
                "limite": {"type": "integer", "minimum": 1, "maximum": 30},
            }),
            ver_notificaciones,
            lee_contenido=True,  # contienen mensajes de terceros: datos privados y no confiables
        ),
    ]
