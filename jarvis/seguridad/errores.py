"""Excepción común para rechazos de seguridad."""


class ErrorSeguridad(Exception):
    """Una acción fue rechazada por las reglas de seguridad. El mensaje es apto para el modelo."""
