"""Lista negra de archivos sensibles."""

import pytest

from jarvis.seguridad.errores import ErrorSeguridad
from jarvis.seguridad.lista_negra import ListaNegra


@pytest.mark.parametrize("nombre", [
    ".env", ".env.local", "mis_passwords.txt", "Contraseñas.xlsx", "CONTRASENAS.txt",
    "clave_wifi.txt", "client_secret.json", "token_github.txt", "servidor.pem", "privada.key",
    "putty.ppk", "certificado.pfx", "id_rsa", "id_rsa.pub", "id_ed25519", "Login Data", "Cookies",
    "key4.db", "logins.json", "wallet.dat", "credenciales.docx",
])
def test_archivos_protegidos(nombre):
    assert ListaNegra().motivo_nombre(nombre) is not None


@pytest.mark.parametrize("partes", [
    [".ssh", "config"], ["Exodus", "datos.json"], ["Electrum", "x.txt"], ["MetaMask", "a.txt"],
    ["respaldo", ".gnupg", "pubring.kbx"],
])
def test_carpetas_protegidas(partes):
    assert ListaNegra().motivo(partes) is not None


@pytest.mark.parametrize("nombre", ["informe.docx", "notas.txt", "foto.jpg", "presupuesto.xlsx"])
def test_archivos_normales_permitidos(nombre):
    assert ListaNegra().motivo_nombre(nombre) is None


def test_lista_negra_configurable():
    lista = ListaNegra(palabras=["nomina"], extensiones=[".bak"])
    assert lista.motivo_nombre("nomina_2024.xlsx")
    assert lista.motivo_nombre("respaldo.bak")
    # Los valores base se mantienen aunque se agreguen otros.
    assert lista.motivo_nombre(".env")


def test_validador_bloquea_archivo_sensible_en_carpeta_permitida(entorno):
    sensible = entorno["permitida"] / "contraseñas.txt"
    sensible.write_text("1234", encoding="utf-8")
    with pytest.raises(ErrorSeguridad, match="credenciales"):
        entorno["validador"].validar(str(sensible))


def test_validador_bloquea_contenido_de_carpeta_ssh(entorno):
    ssh = entorno["permitida"] / ".ssh"
    ssh.mkdir()
    (ssh / "config").write_text("Host x", encoding="utf-8")
    with pytest.raises(ErrorSeguridad):
        entorno["validador"].validar(str(ssh / "config"))


def test_validador_bloquea_env(entorno):
    (entorno["permitida"] / ".env").write_text("JARVIS_API_KEY=abc", encoding="utf-8")
    with pytest.raises(ErrorSeguridad):
        entorno["validador"].validar(str(entorno["permitida"] / ".env"))


def test_nombre_del_usuario_no_afecta(tmp_path):
    """Solo se revisa la parte de la ruta debajo de la carpeta permitida."""
    from jarvis.seguridad.rutas import DRIVE_FIXED, ValidadorRutas

    base = tmp_path / "Token_Usuario"  # una carpeta permitida con palabra "token"
    base.mkdir()
    (base / "notas.txt").write_text("x", encoding="utf-8")
    v = ValidadorRutas([str(base)], [], ListaNegra(), tipo_unidad=lambda r: DRIVE_FIXED)
    assert v.validar(str(base / "notas.txt"))
