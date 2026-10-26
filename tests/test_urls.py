"""Solo se abren URLs http y https."""

import pytest

from jarvis.seguridad.errores import ErrorSeguridad
from jarvis.seguridad.urls import codificar_consulta, url_escrita_por_usuario, validar_url


@pytest.mark.parametrize("url", [
    "https://www.google.com", "http://example.com/ruta?x=1", "HTTPS://Example.com", "google.com",
    "www.wikipedia.org/wiki/Python",
])
def test_urls_permitidas(url):
    assert validar_url(url).lower().startswith(("http://", "https://"))


@pytest.mark.parametrize("url", [
    "file:///C:/Windows/system.ini", "file://servidor/compartido", "javascript:alert(1)",
    "JavaScript:alert(1)", "data:text/html,<script>alert(1)</script>", "vbscript:msgbox(1)",
    "ms-settings:", "ftp://servidor/archivo", "mailto:a@b.com", "ms-msdt:/id", "search-ms:query=x",
    "https://usuario:clave@banco.com", "https:///sin-dominio", "", "   ", "https://ex ample.com",
    "https://example.com/\nfile:///x",
])
def test_urls_rechazadas(url):
    with pytest.raises(ErrorSeguridad):
        validar_url(url)


def test_url_escrita_por_usuario():
    assert url_escrita_por_usuario("https://www.youtube.com", "abre youtube.com por favor")
    assert url_escrita_por_usuario("https://github.com/anthropics", "abre https://github.com/anthropics")
    assert not url_escrita_por_usuario("https://sitio-malicioso.com", "abre mi correo")
    assert not url_escrita_por_usuario("https://google.com/otra/ruta", "abre google.com")


def test_codificar_consulta():
    assert codificar_consulta("café & té?") == "caf%C3%A9%20%26%20t%C3%A9%3F"
    assert "/" not in codificar_consulta("a/b")
