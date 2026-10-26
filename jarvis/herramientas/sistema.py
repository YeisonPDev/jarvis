"""Información del sistema (solo consulta)."""

from __future__ import annotations

import time

import psutil

from jarvis.herramientas.base import Contexto, Herramienta, Resultado, esquema_objeto, exito


def _gb(n: float) -> str:
    return f"{n / 1024 ** 3:.1f} GB"


def _duracion(segundos: float) -> str:
    dias, resto = divmod(int(segundos), 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    partes = []
    if dias:
        partes.append(f"{dias} d")
    if horas:
        partes.append(f"{horas} h")
    partes.append(f"{minutos} min")
    return " ".join(partes)


def info_sistema(ctx: Contexto, args: dict) -> Resultado:
    procesos = list(psutil.process_iter(["name", "memory_info"]))
    for p in procesos:
        try:
            p.cpu_percent(None)  # primera muestra
        except (psutil.Error, OSError):
            pass
    cpu = psutil.cpu_percent(interval=0.6)
    lineas = [f"CPU: {cpu:.0f}% ({psutil.cpu_count(logical=True)} núcleos lógicos)"]

    ram = psutil.virtual_memory()
    lineas.append(f"RAM: {ram.percent:.0f}% en uso ({_gb(ram.used)} de {_gb(ram.total)})")

    for part in psutil.disk_partitions(all=False):
        if "fixed" not in part.opts:
            continue
        try:
            uso = psutil.disk_usage(part.mountpoint)
        except (OSError, PermissionError):
            continue
        lineas.append(
            f"Disco {part.mountpoint} {_gb(uso.free)} libres de {_gb(uso.total)} ({uso.percent:.0f}% usado)"
        )

    bateria = psutil.sensors_battery()
    if bateria is None:
        lineas.append("Batería: no detectada (equipo de escritorio)")
    else:
        estado = "cargando" if bateria.power_plugged else "descargando"
        lineas.append(f"Batería: {bateria.percent:.0f}% ({estado})")

    lineas.append(f"Encendido desde hace: {_duracion(time.time() - psutil.boot_time())}")

    datos = []
    for p in procesos:
        if p.pid == 0:  # "System Idle Process" representa CPU libre, no consumo
            continue
        try:
            mem = p.info["memory_info"].rss if p.info.get("memory_info") else 0
            datos.append((p.info.get("name") or "?", p.cpu_percent(None), mem))
        except (psutil.Error, OSError):
            continue
    nucleos = psutil.cpu_count(logical=True) or 1
    por_cpu = sorted(datos, key=lambda d: d[1], reverse=True)[:5]
    por_ram = sorted(datos, key=lambda d: d[2], reverse=True)[:5]
    lineas.append("Más CPU: " + ", ".join(f"{n} {c / nucleos:.0f}%" for n, c, _ in por_cpu))
    lineas.append("Más RAM: " + ", ".join(f"{n} {m / 1024 ** 2:.0f} MB" for n, _, m in por_ram))
    return exito("\n".join(lineas))


def herramientas() -> list[Herramienta]:
    return [
        Herramienta(
            "info_sistema",
            "Consulta CPU, RAM, discos, batería, tiempo encendido y procesos que más consumen.",
            esquema_objeto({}),
            info_sistema,
        ),
    ]
