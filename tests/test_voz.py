"""Preparación del texto para voz y elección de la voz."""

from jarvis.voz.texto import AVISO_RECORTE, preparar_texto_para_voz
from jarvis.voz.windows import elegir_voz


def test_acorta_rutas_al_nombre_final():
    t = preparar_texto_para_voz(r"Archivo creado: C:\Users\Ana\Mis Documentos\Jarvis\lista.txt")
    assert t == "Archivo creado: lista.txt"


def test_ruta_de_carpeta():
    assert "Descargas" in preparar_texto_para_voz("Abrí la carpeta C:\\Users\\Ana\\Descargas\\ en el Explorador.")
    assert "\\" not in preparar_texto_para_voz("Abrí la carpeta C:\\Users\\Ana\\Descargas\\ en el Explorador.")


def test_url_se_lee_como_dominio():
    t = preparar_texto_para_voz("Abrí https://www.youtube.com/results?search_query=hola en el navegador.")
    assert t == "Abrí youtube.com en el navegador."


def test_quita_markdown_y_emojis():
    t = preparar_texto_para_voz("**Listo** ✅\n- uno\n- dos\n# Título")
    assert "*" not in t and "#" not in t and "✅" not in t
    assert "uno" in t and "dos" in t and "Título" in t


def test_lineas_se_convierten_en_pausas():
    assert preparar_texto_para_voz("CPU: 4%\nRAM: 61%") == "CPU: 4%. RAM: 61%"


def test_recorta_textos_largos():
    texto = "Esta es una frase. " * 200
    t = preparar_texto_para_voz(texto, max_caracteres=300)
    assert len(t) <= 300 + len(AVISO_RECORTE)
    assert t.endswith(AVISO_RECORTE)


def test_texto_vacio():
    assert preparar_texto_para_voz("") == ""
    assert preparar_texto_para_voz("   \n ") == ""


def test_elegir_voz():
    voces = [("Microsoft Zira - English", "409"), ("Microsoft Sabina - Spanish", "80A"),
             ("Microsoft Raul - Spanish", "80A")]
    assert elegir_voz(voces, "Raúl") == 2  # sin importar tildes
    assert elegir_voz(voces, "Inexistente") == 1  # primera en español
    assert elegir_voz([("Zira", "409")], "Raul") == 0  # sin español: la primera
    assert elegir_voz([], "Raul") is None


def test_dividir_en_fragmentos():
    from jarvis.voz.reproductor import dividir_en_fragmentos

    texto = "Primera frase. Segunda frase más larga, con una coma. ¿Tercera? " + "palabra " * 80
    fragmentos = dividir_en_fragmentos(texto, maximo=120)
    assert all(len(f) <= 121 for f in fragmentos)
    assert " ".join(fragmentos).split() == texto.split()  # no se pierde ni duplica nada
    assert dividir_en_fragmentos("Hola.") == ["Hola."]


def test_elegir_voz_por_idioma():
    voces = [("Microsoft Zira - English", "409"), ("Microsoft Raul - Spanish", "80A")]
    assert elegir_voz(voces, "", idioma="en") == 0
    assert elegir_voz(voces, "", idioma="es") == 1


def test_velocidad_a_rate():
    from jarvis.voz.windows import velocidad_a_rate

    assert velocidad_a_rate(1.0) == 0
    assert velocidad_a_rate(2.0) > 0 > velocidad_a_rate(0.5)
    assert -10 <= velocidad_a_rate(0.1) and velocidad_a_rate(10) <= 10


def test_catalogo_local_sin_internet(tmp_path):
    import json

    from jarvis.voz.piper_voz import cargar_catalogo, esta_descargada

    (tmp_path / "es_MX-prueba-medium.onnx").write_bytes(b"x")
    (tmp_path / "es_MX-prueba-medium.onnx.json").write_text(json.dumps({
        "language": {"code": "es_MX", "family": "es", "name_native": "Español", "country_english": "Mexico"},
    }), encoding="utf-8")
    voces = cargar_catalogo(str(tmp_path), usar_red=False)
    assert [v.clave for v in voces] == ["es_MX-prueba-medium"]
    assert voces[0].familia == "es" and esta_descargada(str(tmp_path), "es_MX-prueba-medium")


def test_catalogo_rechaza_rutas_raras():
    from jarvis.voz.piper_voz import _desde_entrada

    voz = _desde_entrada("es_MX-ald-medium", {"files": {
        "es/es_MX/ald/medium/es_MX-ald-medium.onnx": {"size_bytes": 10, "md5_digest": "a"},
        "../../malicioso.onnx": {"size_bytes": 10, "md5_digest": "b"},
        "es/es_MX/ald/medium/../../x.onnx": {"size_bytes": 10, "md5_digest": "c"},
    }})
    assert list(voz.archivos) == ["es/es_MX/ald/medium/es_MX-ald-medium.onnx"]
    assert _desde_entrada("../../x-y-medium", {}) is None


def test_guardar_ajustes_conserva_el_resto(tmp_path):
    import json

    from jarvis.config import Config

    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps({"atajo": "ctrl+alt+j", "programas": {"calc": "calc.exe"},
                                "voz": {"velocidad": 1}}), encoding="utf-8")
    config = Config.cargar(ruta_json=ruta, ruta_env=tmp_path / "no_existe.env")
    assert config.voz.velocidad == 1.0 and config.voz.motor == "piper"
    config.voz.velocidad = 1.5
    config.voz.piper_voz = "en_US-lessac-medium"
    config.idioma_codigo, config.idioma_nombre = "en", "English"
    config.guardar_ajustes()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["atajo"] == "ctrl+alt+j" and datos["programas"] == {"calc": "calc.exe"}
    assert datos["voz"]["velocidad"] == 1.5 and datos["idioma"]["codigo"] == "en"
    assert Config.cargar(ruta_json=ruta).idioma_nombre == "English"


def test_apariencia_se_carga_y_guarda(tmp_path):
    import json

    from jarvis.config import Config

    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps({"interfaz": {"ocultar_tras_inactividad_s": 30, "opacidad_fondo": 300,
                                             "desenfoque": "mucho"}}), encoding="utf-8")
    config = Config.cargar(ruta_json=ruta, ruta_env=tmp_path / "no_existe.env")
    assert config.opacidad_fondo == 100  # se limita al máximo
    assert config.desenfoque == 18  # valor inválido: se usa el de por defecto
    config.opacidad_fondo, config.desenfoque = 30, 25
    config.guardar_ajustes()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["interfaz"] == {"ocultar_tras_inactividad_s": 30, "opacidad_fondo": 30, "desenfoque": 25}


def test_tiempo_de_ocultado_se_guarda(tmp_path):
    import json

    from jarvis.config import Config

    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps({"interfaz": {"ocultar_tras_inactividad_s": 30}}), encoding="utf-8")
    config = Config.cargar(ruta_json=ruta, ruta_env=tmp_path / "no_existe.env")
    assert config.ocultar_tras_inactividad_s == 30
    config.ocultar_tras_inactividad_s = 0  # nunca
    config.guardar_ajustes()
    assert Config.cargar(ruta_json=ruta).ocultar_tras_inactividad_s == 0
