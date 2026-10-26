"""Errores del cerebro con mensajes claros para el usuario (sin datos sensibles)."""

from __future__ import annotations


class ErrorJarvis(Exception):
    """Error con un mensaje apto para mostrar en la interfaz."""

    def __init__(self, mensaje_usuario: str):
        super().__init__(mensaje_usuario)
        self.mensaje_usuario = mensaje_usuario


class ErrorCancelado(ErrorJarvis):
    def __init__(self):
        super().__init__("Pedido cancelado.")


class ErrorTiempoAgotado(ErrorJarvis):
    def __init__(self, segundos: float | None = None):
        extra = f" de {segundos:.0f} segundos" if segundos else ""
        super().__init__(f"El pedido superó el tiempo máximo{extra}. Intenta algo más simple.")


class ErrorConexion(ErrorJarvis):
    def __init__(self, proveedor: str, base_url: str = ""):
        if proveedor == "ollama":
            texto = f"No pude conectar con Ollama ({base_url}). ¿Está abierto y con el modelo descargado?"
        else:
            texto = f"Sin conexión con {proveedor}. Revisa tu conexión a internet."
        super().__init__(texto)


class ErrorLimiteUso(ErrorJarvis):
    """HTTP 429. 'reintentar_en' son segundos sugeridos por el servidor (si los dio)."""

    def __init__(self, proveedor: str, reintentar_en: float | None = None):
        self.reintentar_en = reintentar_en
        if reintentar_en and reintentar_en > 90:
            minutos = max(1, round(reintentar_en / 60))
            texto = (f"Se agotó el límite de uso gratuito de {proveedor}. "
                     f"Vuelve a intentarlo en unos {minutos} minutos.")
        else:
            texto = (f"{proveedor} está limitando las peticiones (límite de uso gratuito). "
                     "Espera un momento y vuelve a intentarlo.")
        super().__init__(texto)


class ErrorAutenticacion(ErrorJarvis):
    def __init__(self, proveedor: str):
        super().__init__(
            f"La API key de {proveedor} no es válida o falta. Revisa JARVIS_API_KEY en el archivo .env."
        )


class ErrorConfiguracion(ErrorJarvis):
    pass


class ErrorProveedor(ErrorJarvis):
    pass


class ErrorHerramientaMalFormada(ErrorJarvis):
    """El servidor rechazó una llamada a herramienta mal generada por el modelo (p. ej. Groq 'tool_use_failed')."""

    def __init__(self, detalle: str = ""):
        super().__init__("El modelo generó una llamada a herramienta mal formada.")
        self.detalle = detalle
