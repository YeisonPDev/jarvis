"""Carga de configuración desde .env (proveedor y llave) y config.json (todo lo demás)."""

from __future__ import annotations

import ctypes
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# GUID de las carpetas conocidas de Windows (KNOWNFOLDERID).
# Se usan en vez de rutas fijas porque OneDrive o el usuario pueden haberlas movido.
_CARPETAS_CONOCIDAS = {
    "ESCRITORIO": ("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Desktop"),
    "DOCUMENTOS": ("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}", "Documents"),
    "DESCARGAS": ("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
    "MUSICA": ("{4BD8D571-6D19-48D3-BE97-422220080E43}", "Music"),
    "IMAGENES": ("{33E28130-4E1E-4676-835A-98395C3BC3BB}", "Pictures"),
    "VIDEOS": ("{18989B1D-99B5-455B-841C-AB7C74E4DDFC}", "Videos"),
}

# Nombres que el usuario o el modelo pueden usar al inicio de una ruta ("Documentos\\notas.txt").
_ALIAS = {
    "escritorio": "ESCRITORIO", "desktop": "ESCRITORIO",
    "documentos": "DOCUMENTOS", "mis documentos": "DOCUMENTOS", "documents": "DOCUMENTOS",
    "descargas": "DESCARGAS", "downloads": "DESCARGAS",
    "musica": "MUSICA", "música": "MUSICA", "music": "MUSICA",
    "imagenes": "IMAGENES", "imágenes": "IMAGENES", "pictures": "IMAGENES", "fotos": "IMAGENES",
    "videos": "VIDEOS", "vídeos": "VIDEOS",
}


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(texto: str) -> _GUID:
    u = uuid.UUID(texto)
    g = _GUID()
    g.Data1, g.Data2, g.Data3 = u.fields[0], u.fields[1], u.fields[2]
    for i, b in enumerate(u.bytes[8:]):
        g.Data4[i] = b
    return g


def carpeta_conocida(clave: str) -> str:
    """Devuelve la ruta real de una carpeta del usuario (Escritorio, Documentos...)."""
    guid_txt, respaldo = _CARPETAS_CONOCIDAS[clave]
    try:
        ruta = ctypes.c_wchar_p()
        guid = _guid(guid_txt)
        res = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(ruta)
        )
        if res == 0 and ruta.value:
            valor = ruta.value
            ctypes.windll.ole32.CoTaskMemFree(ruta)
            return valor
    except (AttributeError, OSError):
        pass
    return str(Path.home() / respaldo)


def expandir_marcadores(texto: str) -> str:
    """Reemplaza {DOCUMENTOS}, {DESCARGAS}... y variables %ENTORNO%."""
    for clave in _CARPETAS_CONOCIDAS:
        marcador = "{" + clave + "}"
        if marcador in texto:
            texto = texto.replace(marcador, carpeta_conocida(clave))
    return os.path.expandvars(texto)


def carpetas_bloqueadas_obligatorias() -> list[str]:
    """Carpetas del sistema que nunca son accesibles, sin importar config.json."""
    inicio = str(Path.home())
    candidatas = [
        os.environ.get("SystemRoot", r"C:\Windows"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramW6432", r"C:\Program Files"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        os.environ.get("APPDATA", os.path.join(inicio, "AppData", "Roaming")),
        os.environ.get("LOCALAPPDATA", os.path.join(inicio, "AppData", "Local")),
        os.path.join(inicio, "AppData"),
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\ProgramData",
    ]
    vistas, resultado = set(), []
    for c in candidatas:
        clave = os.path.normcase(c)
        if c and clave not in vistas:
            vistas.add(clave)
            resultado.append(c)
    return resultado


@dataclass
class Limites:
    max_tamano_archivo_mb: float = 10
    max_caracteres_lectura: int = 8000
    max_resultados_busqueda: int = 25
    max_archivos_revisados: int = 30000
    tiempo_busqueda_s: float = 8
    max_elementos_listado: int = 200
    max_caracteres_creacion: int = 50000
    max_iteraciones: int = 10
    tiempo_maximo_pedido_s: float = 60


# {idioma} se reemplaza por el idioma elegido en los ajustes.
INSTRUCCIONES_VOZ = (
    "Habla siempre en {idioma}. Voz grave, calmada y segura, "
    "como un asistente de inteligencia artificial elegante y eficiente. Ritmo ágil y natural, "
    "sin exagerar la emoción."
)

MOTORES_VOZ = ("piper", "openai", "windows")


@dataclass
class Voz:
    activada: bool = True
    motor: str = "piper"  # "piper" (local), "openai" (en línea) o "windows" (básica)
    piper_voz: str = "es_MX-ald-medium"
    openai_modelo: str = "gpt-4o-mini-tts"
    openai_voz: str = "onyx"
    openai_instrucciones: str = INSTRUCCIONES_VOZ
    # Voz de Windows: se usa con motor "windows" y como respaldo si el motor elegido falla.
    nombre: str = "Raul"  # parte del nombre de la voz de Windows; si no existe, usa una del idioma
    velocidad: float = 1.0  # multiplicador: 0.5 (lenta) a 2.0 (rápida)
    volumen: int = 100  # de 0 a 100 (relativo al volumen del sistema)
    max_caracteres: int = 1500  # lo que exceda se ve en pantalla pero no se lee
    leer_confirmaciones: bool = True
    leer_errores: bool = True


@dataclass
class Config:
    proveedor: str = "groq"
    modelo: str = ""
    base_url: str = ""
    api_key: str = field(default="", repr=False)  # nunca se imprime
    tts_api_key: str = field(default="", repr=False)  # llave de OpenAI para la voz
    tts_base_url: str = ""
    atajo: str = "ctrl+space"
    carpetas_permitidas: list[str] = field(default_factory=list)
    carpetas_bloqueadas: list[str] = field(default_factory=list)
    carpeta_salida: str = ""
    carpeta_descargas: str = ""
    alias_carpetas: dict[str, str] = field(default_factory=dict)
    lista_negra: dict[str, list[str]] = field(default_factory=dict)
    extensiones_ejecutables_extra: list[str] = field(default_factory=list)
    programas: dict[str, str] = field(default_factory=dict)
    motor_busqueda: str = "https://www.google.com/search?q="
    limites: Limites = field(default_factory=Limites)
    ocultar_tras_inactividad_s: float = 30  # 0 = nunca se oculta solo
    opacidad_fondo: int = 45  # 0 (vidrio muy transparente) a 100 (negro sólido)
    desenfoque: int = 18  # radio del desenfoque en píxeles (0 = sin desenfoque)
    ciudad: str = ""  # ciudad por defecto para el clima
    busqueda_api_key: str = field(default="", repr=False)  # llave de Groq para buscar en internet
    busqueda_modelo: str = "openai/gpt-oss-20b"  # modelo aparte: no gasta el cupo del principal
    voz: Voz = field(default_factory=Voz)
    idioma_codigo: str = "es"  # idioma de las respuestas y de la voz
    idioma_nombre: str = "Español"
    carpeta_datos: str = ""  # logs, voces y archivo de bloqueo de Jarvis
    ruta_json: str = ""  # config.json del que se cargó (para guardar los ajustes)

    @property
    def carpeta_voces_piper(self) -> str:
        return os.path.join(self.carpeta_datos, "voces_piper")

    def idioma_para_voz(self) -> str:
        """Cómo se nombra el idioma en las instrucciones de voz."""
        if self.idioma_codigo.lower().startswith("es"):
            return "español latinoamericano neutro"
        return self.idioma_nombre

    def instrucciones_voz(self) -> str:
        texto = self.voz.openai_instrucciones or INSTRUCCIONES_VOZ
        return texto.replace("{idioma}", self.idioma_para_voz())

    def guardar_ajustes(self) -> None:
        """Escribe la sección 'voz' y el idioma en config.json, conservando lo demás."""
        ruta = self.ruta_json or str(RAIZ_PROYECTO / "config.json")
        datos: dict = {}
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                datos = json.load(f)
        datos["idioma"] = {"codigo": self.idioma_codigo, "nombre": self.idioma_nombre}
        datos["voz"] = asdict(self.voz)
        interfaz = datos.get("interfaz") if isinstance(datos.get("interfaz"), dict) else {}
        interfaz["opacidad_fondo"] = self.opacidad_fondo
        interfaz["desenfoque"] = self.desenfoque
        interfaz["ocultar_tras_inactividad_s"] = int(self.ocultar_tras_inactividad_s)
        datos["interfaz"] = interfaz
        ubicacion = datos.get("ubicacion") if isinstance(datos.get("ubicacion"), dict) else {}
        ubicacion["ciudad"] = self.ciudad
        datos["ubicacion"] = ubicacion
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temporal, ruta)  # reemplazo atómico: nunca queda un archivo a medias

    @classmethod
    def cargar(cls, ruta_json: Path | None = None, ruta_env: Path | None = None) -> "Config":
        load_dotenv(ruta_env or RAIZ_PROYECTO / ".env", override=False)
        ruta_json = ruta_json or RAIZ_PROYECTO / "config.json"
        datos: dict = {}
        if ruta_json.exists():
            with open(ruta_json, encoding="utf-8") as f:
                datos = json.load(f)

        permitidas = datos.get("carpetas_permitidas") or [
            "{ESCRITORIO}", "{DOCUMENTOS}", "{DESCARGAS}", "{MUSICA}", "{IMAGENES}", "{VIDEOS}",
        ]
        bloqueadas = carpetas_bloqueadas_obligatorias() + [
            expandir_marcadores(c) for c in datos.get("carpetas_bloqueadas_extra", [])
        ]

        limites = Limites()
        for k, v in (datos.get("limites") or {}).items():
            if hasattr(limites, k) and isinstance(v, (int, float)):
                setattr(limites, k, v)

        voz = Voz()
        for k, v in (datos.get("voz") or {}).items():
            if not hasattr(voz, k):
                continue
            actual = getattr(voz, k)
            if isinstance(actual, float) and isinstance(v, (int, float)) and not isinstance(v, bool):
                setattr(voz, k, float(v))
            elif isinstance(v, type(actual)):
                setattr(voz, k, v)
        if voz.motor not in MOTORES_VOZ:
            voz.motor = "piper"
        voz.velocidad = max(0.5, min(2.0, voz.velocidad))
        idioma = datos.get("idioma") or {}
        interfaz = datos.get("interfaz") or {}

        def entero(clave: str, defecto: int, minimo: int, maximo: int) -> int:
            valor = interfaz.get(clave, defecto)
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                return defecto
            return max(minimo, min(maximo, int(valor)))

        alias = {nombre: carpeta_conocida(clave) for nombre, clave in _ALIAS.items()}
        local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))

        return cls(
            proveedor=os.getenv("JARVIS_PROVIDER", "groq").strip().lower() or "groq",
            modelo=os.getenv("JARVIS_MODEL", "").strip(),
            base_url=os.getenv("JARVIS_BASE_URL", "").strip(),
            api_key=os.getenv("JARVIS_API_KEY", "").strip(),
            tts_api_key=os.getenv("JARVIS_TTS_API_KEY", "").strip(),
            tts_base_url=os.getenv("JARVIS_TTS_BASE_URL", "").strip(),
            atajo=str(datos.get("atajo", "ctrl+space")),
            carpetas_permitidas=[expandir_marcadores(c) for c in permitidas],
            carpetas_bloqueadas=bloqueadas,
            carpeta_salida=expandir_marcadores(datos.get("carpeta_salida", "{DOCUMENTOS}\\Jarvis")),
            carpeta_descargas=carpeta_conocida("DESCARGAS"),
            alias_carpetas=alias,
            lista_negra=datos.get("lista_negra") or {},
            extensiones_ejecutables_extra=datos.get("extensiones_ejecutables_extra") or [],
            programas={str(k): str(v) for k, v in (datos.get("programas") or {}).items()},
            motor_busqueda=datos.get("motor_busqueda", "https://www.google.com/search?q="),
            limites=limites,
            ocultar_tras_inactividad_s=float(
                (datos.get("interfaz") or {}).get(
                    "ocultar_tras_inactividad_s",
                    (datos.get("interfaz") or {}).get("ocultar_tras_respuesta_s", 30),
                )
            ),
            voz=voz,
            opacidad_fondo=entero("opacidad_fondo", 45, 0, 100),
            desenfoque=entero("desenfoque", 18, 0, 40),
            ciudad=str((datos.get("ubicacion") or {}).get("ciudad", "")).strip()[:100],
            busqueda_api_key=(os.getenv("JARVIS_GROQ_API_KEY", "").strip()
                              or (os.getenv("JARVIS_API_KEY", "").strip()
                                  if (os.getenv("JARVIS_PROVIDER", "groq").strip().lower() or "groq") == "groq"
                                  else "")),
            busqueda_modelo=str((datos.get("busqueda") or {}).get("modelo", "openai/gpt-oss-20b")),
            idioma_codigo=str(idioma.get("codigo", "es")) if isinstance(idioma, dict) else "es",
            idioma_nombre=str(idioma.get("nombre", "Español")) if isinstance(idioma, dict) else "Español",
            carpeta_datos=os.path.join(local, "Jarvis"),
            ruta_json=str(ruta_json),
        )
