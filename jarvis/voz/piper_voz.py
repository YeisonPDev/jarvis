"""Voz local con Piper: natural, gratuita y sin internet (salvo para descargar voces).

Las voces se guardan en %LOCALAPPDATA%\\Jarvis\\voces_piper. El catálogo y los modelos
se descargan solo desde el repositorio oficial de voces de Piper en Hugging Face, y cada
archivo se verifica con su tamaño y su md5 antes de usarlo.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import quote
from urllib.request import urlopen

from jarvis.voz.base import SalidaVoz
from jarvis.voz.reproductor import ErrorPermanente, Interrumpido, SalidaVozFragmentada

URL_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
URL_CATALOGO = URL_BASE + "voices.json?download=true"
PATRON_CLAVE = re.compile(r"^[a-z]{2,3}_[A-Z]{2}-[A-Za-z0-9_]+-(x_low|low|medium|high)$")
PATRON_ARCHIVO = re.compile(r"^[a-z]{2,3}/[a-z]{2,3}_[A-Z]{2}/[A-Za-z0-9_]+/[a-z_]+/[A-Za-z0-9_\-]+\.onnx(\.json)?$")
VOZ_POR_DEFECTO = "es_MX-ald-medium"
CALIDADES = {"x_low": "muy baja", "low": "baja", "medium": "media", "high": "alta"}
PAISES = {
    "Mexico": "México", "Spain": "España", "Argentina": "Argentina", "United States": "Estados Unidos",
    "Great Britain": "Reino Unido", "Brazil": "Brasil", "Portugal": "Portugal", "France": "Francia",
    "Italy": "Italia", "Germany": "Alemania", "Netherlands": "Países Bajos", "Belgium": "Bélgica",
    "Russia": "Rusia", "China": "China", "Canada": "Canadá", "Switzerland": "Suiza",
}


@dataclass
class VozPiper:
    clave: str  # p. ej. "es_MX-ald-medium"
    nombre: str  # "ald"
    codigo: str  # "es_MX"
    familia: str  # "es"
    idioma: str  # "Español"
    pais: str  # "Mexico"
    calidad: str  # "medium"
    archivos: dict[str, tuple[int, str]] = field(default_factory=dict)  # ruta → (bytes, md5)

    @property
    def tamano_mb(self) -> float:
        return sum(t for t, _ in self.archivos.values()) / 1e6

    def descripcion(self) -> str:
        pais = PAISES.get(self.pais, self.pais) or self.codigo
        return f"{self.nombre} — {pais} — calidad {CALIDADES.get(self.calidad, self.calidad)}"


def ruta_modelo(carpeta: str, clave: str) -> str:
    return os.path.join(carpeta, f"{clave}.onnx")


def esta_descargada(carpeta: str, clave: str) -> bool:
    modelo = ruta_modelo(carpeta, clave)
    return os.path.isfile(modelo) and os.path.isfile(modelo + ".json")


def _desde_entrada(clave: str, datos: dict) -> VozPiper | None:
    if not PATRON_CLAVE.match(clave):
        return None
    idioma = datos.get("language") or {}
    archivos = {}
    for ruta, info in (datos.get("files") or {}).items():
        if ruta.endswith((".onnx", ".onnx.json")) and PATRON_ARCHIVO.match(ruta):
            archivos[ruta] = (int(info.get("size_bytes", 0)), str(info.get("md5_digest", "")))
    return VozPiper(
        clave=clave,
        nombre=str(datos.get("name", clave.split("-")[1])),
        codigo=str(idioma.get("code", clave.split("-")[0])),
        familia=str(idioma.get("family", clave[:2])),
        idioma=str(idioma.get("name_native") or idioma.get("name_english") or clave[:2]),
        pais=str(idioma.get("country_english", "")),
        calidad=str(datos.get("quality", clave.rsplit("-", 1)[-1])),
        archivos=archivos,
    )


def _voces_locales(carpeta: str) -> list[VozPiper]:
    """Voces ya descargadas, leyendo su .onnx.json (sirve sin internet)."""
    voces = []
    if not os.path.isdir(carpeta):
        return voces
    for nombre in os.listdir(carpeta):
        if not nombre.endswith(".onnx"):
            continue
        clave = nombre[:-5]
        try:
            with open(os.path.join(carpeta, nombre + ".json"), encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError):
            continue
        voz = _desde_entrada(clave, {"language": datos.get("language") or {}, "quality": clave.rsplit("-", 1)[-1]})
        if voz:
            voces.append(voz)
    return voces


def cargar_catalogo(carpeta: str, usar_red: bool = True, timeout: float = 15) -> list[VozPiper]:
    """Lista de voces disponibles. Usa internet si puede; si no, la copia guardada o las locales."""
    os.makedirs(carpeta, exist_ok=True)
    cache = os.path.join(carpeta, "voices.json")
    datos = None
    if usar_red:
        try:
            with urlopen(URL_CATALOGO, timeout=timeout) as r:  # noqa: S310 - URL fija y https
                datos = json.loads(r.read(20_000_000))
            if isinstance(datos, dict):
                temporal = cache + ".parcial"
                with open(temporal, "w", encoding="utf-8") as f:
                    json.dump(datos, f)
                os.replace(temporal, cache)
        except (OSError, ValueError):
            datos = None
    if datos is None and os.path.isfile(cache):
        try:
            with open(cache, encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError):
            datos = None
    if not isinstance(datos, dict):
        return sorted(_voces_locales(carpeta), key=lambda v: v.clave)
    voces = [v for v in (_desde_entrada(k, d) for k, d in datos.items() if isinstance(d, dict)) if v]
    return sorted(voces, key=lambda v: v.clave)


def descargar_voz(voz: VozPiper, carpeta: str,
                  progreso: Callable[[int, int], None] | None = None,
                  cancelar: threading.Event | None = None) -> None:
    """Descarga el modelo y su configuración, verificando tamaño y md5. Lanza OSError si falla."""
    if not PATRON_CLAVE.match(voz.clave) or not voz.archivos:
        raise OSError("Voz no válida en el catálogo.")
    os.makedirs(carpeta, exist_ok=True)
    total = sum(t for t, _ in voz.archivos.values()) or 1
    hecho = 0
    for ruta, (tamano, md5) in voz.archivos.items():
        if not PATRON_ARCHIVO.match(ruta):
            raise OSError("Ruta de archivo no válida en el catálogo.")
        extension = ".onnx.json" if ruta.endswith(".onnx.json") else ".onnx"
        destino = os.path.join(carpeta, voz.clave + extension)
        temporal = destino + ".parcial"
        resumen = hashlib.md5()  # noqa: S324 - solo verificación de integridad, como publica Piper
        recibidos = 0
        try:
            with urlopen(URL_BASE + quote(ruta) + "?download=true", timeout=30) as r, \
                    open(temporal, "wb") as f:  # noqa: S310
                while True:
                    if cancelar is not None and cancelar.is_set():
                        raise OSError("Descarga cancelada.")
                    bloque = r.read(256 * 1024)
                    if not bloque:
                        break
                    f.write(bloque)
                    resumen.update(bloque)
                    recibidos += len(bloque)
                    if progreso:
                        progreso(hecho + recibidos, total)
            if tamano and recibidos != tamano:
                raise OSError("El archivo descargado está incompleto.")
            if md5 and resumen.hexdigest() != md5:
                raise OSError("El archivo descargado no pasó la verificación (md5).")
            os.replace(temporal, destino)
        finally:
            if os.path.exists(temporal):
                try:
                    os.remove(temporal)
                except OSError:
                    pass
        hecho += recibidos


# ---------------------------------------------------------------------- #
class SalidaVozPiper(SalidaVozFragmentada):
    nombre_motor = "Piper"

    def __init__(self, carpeta_voces: str, clave: str, carpeta_temporal: str,
                 velocidad: float = 1.0, max_caracteres: int = 1500,
                 respaldo: SalidaVoz | None = None):
        self.clave = clave
        self.modelo = ruta_modelo(carpeta_voces, clave)
        # length_scale > 1 habla más lento; < 1 más rápido.
        self.escala = 1.0 / max(0.5, min(2.0, float(velocidad)))
        self.nombre_voz = f"Piper {clave}"
        self._voz = None
        self._candado = threading.Lock()  # el fonemizador (espeak) no es seguro entre hilos
        super().__init__(carpeta_temporal, max_caracteres, respaldo)

    def preparar(self) -> None:
        if not esta_descargada(os.path.dirname(self.modelo), self.clave):
            raise ErrorPermanente(f"la voz {self.clave} no está descargada (ábrela en los ajustes)")
        from piper import PiperVoice

        self._voz = PiperVoice.load(self.modelo)

    def sintetizar(self, texto: str, generacion: int) -> tuple[bytes, int]:
        from piper import SynthesisConfig

        if self._voz is None:
            raise ErrorPermanente("la voz de Piper no se pudo cargar")
        configuracion = SynthesisConfig(length_scale=self.escala)
        datos, frecuencia = bytearray(), 22050
        with self._candado:
            for trozo in self._voz.synthesize(texto, syn_config=configuracion):
                if generacion != self._generacion:
                    raise Interrumpido()
                datos += trozo.audio_int16_bytes
                frecuencia = trozo.sample_rate
        return bytes(datos), frecuencia
