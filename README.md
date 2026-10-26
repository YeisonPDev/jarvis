# Jarvis

Asistente de escritorio para Windows 11. Al presionar **Ctrl+Espacio** aparece arriba en el centro de la pantalla como una "isla dinámica": una píldora de vidrio esmerilado con un pequeño cubo Rubik como logo y el campo para escribir tu pedido. El modelo de lenguaje decide qué herramienta usar, Jarvis la ejecuta con reglas de seguridad estrictas y te muestra (y te lee en voz alta) la respuesta.

## Requisitos

- Windows 10/11
- Python 3.11 o superior (probado con 3.14)
- Una API key gratuita de Groq (https://console.groq.com/keys), o Ollama instalado si prefieres un modelo local

## Instalación

Abre PowerShell en la carpeta del proyecto:

```powershell
# 1. Crear el entorno virtual
py -3 -m venv .venv

# 2. Activarlo
.\.venv\Scripts\Activate.ps1
#    Si PowerShell lo bloquea, ejecuta una vez:
#    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#    (en cmd.exe se activa con: .venv\Scripts\activate.bat)

# 3. Instalar dependencias
pip install -r requirements.txt
```

## Configurar la API key

1. Copia `.env.example` como `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Abre `.env` con el Bloc de notas y pega tu llave de Groq después de `JARVIS_API_KEY=`.
3. (Opcional) Solo si eliges el motor de voz OpenAI: pega tu llave de OpenAI (https://platform.openai.com/api-keys) después de `JARVIS_TTS_API_KEY=`.

El archivo `.env` está en `.gitignore`. La llave nunca se escribe en los logs ni en los mensajes de error.

## Ejecutar

```powershell
# Con consola (útil para ver errores)
.\.venv\Scripts\python.exe main.py

# Sin consola (uso normal)
.\.venv\Scripts\pythonw.exe main.py
```

Jarvis queda en la bandeja del sistema (junto al reloj).

- **Ctrl+Espacio**: muestra u oculta Jarvis.
- **Enter**: envía el pedido.
- **Esc**: cancela el pedido en curso; si está hablando, lo calla; si no, oculta la ventana.
- **✕** (aparece mientras trabaja): cancela el pedido en cualquier momento.
- **🔊 / 🔇**: activa o silencia la voz.
- **Clic derecho en el ícono → Salir**: cierra Jarvis.

La isla aparece expandiéndose desde una píldora pequeña y crece hacia abajo para mostrar la herramienta en uso, la respuesta o la confirmación Sí/No. El cubo Rubik **gira mientras Jarvis piensa, usa una herramienta o habla**, y se detiene en reposo. La isla y la ventana de ajustes tienen fondo de vidrio esmerilado con esquinas suavizadas: Jarvis toma en vivo lo que hay detrás, lo desenfoca y le pone un tinte oscuro. La **opacidad** y el **desenfoque** se ajustan en la ventana de ajustes (sección *Apariencia*), con vista previa en vivo.

Para poder ver lo que tienen detrás, las ventanas de Jarvis se excluyen de las capturas de pantalla: **no aparecen en capturas, grabaciones ni al compartir pantalla** (por ejemplo, en Teams o Zoom). La conversación se mantiene mientras está abierta y se reinicia al ocultarse.

**Se desvanece sola tras 30 segundos sin actividad**. El contador se reinicia cada vez que escribes, pasas el mouse por encima o llega una respuesta, y no corre mientras trabaja, habla o espera tu confirmación. Se cambia en los ajustes (**Ocultar tras**) o en `config.json` → `interfaz.ocultar_tras_inactividad_s` (`0` = nunca).

## Límite gratuito de Groq

El plan gratuito de Groq permite **8.000 tokens por minuto** por modelo. Cada paso de Jarvis usa unos 2.500, y un pedido puede necesitar de 2 a 4 pasos. Si haces varios pedidos seguidos, a veces verás *"Límite de uso alcanzado; reintento en N s…"* y la respuesta tardará de 10 a 20 segundos más. Jarvis reintenta solo.

Para reducir el consumo, Jarvis usa razonamiento breve (`JARVIS_REASONING_EFFORT=low`, se puede cambiar en `.env`) y hace las búsquedas web con otro modelo. Si quieres respuestas siempre rápidas, el plan de pago de Groq (Developer) tiene límites mucho más altos y se cobra por uso.

## Iniciar con Windows

Ejecuta esto en PowerShell **desde la carpeta del proyecto**. Crea un acceso directo en la carpeta de Inicio:

```powershell
$proyecto = (Get-Location).Path
$inicio = [Environment]::GetFolderPath("Startup")
$shell = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut("$inicio\Jarvis.lnk")
$acceso.TargetPath = "$proyecto\.venv\Scripts\pythonw.exe"
$acceso.Arguments = "`"$proyecto\main.py`""
$acceso.WorkingDirectory = $proyecto
$acceso.Save()
```

Para quitarlo, borra `Jarvis.lnk` de la carpeta que se abre con `Win+R` → `shell:startup`.

No lo ejecutes como administrador: no hace falta, y Jarvis muestra una advertencia si detecta que lo es.

## Cambiar de proveedor

Todo se controla desde `.env`:

| Proveedor | JARVIS_PROVIDER | JARVIS_MODEL | JARVIS_BASE_URL | JARVIS_API_KEY |
|---|---|---|---|---|
| Groq (por defecto) | `groq` | `openai/gpt-oss-120b` | `https://api.groq.com/openai/v1` | tu llave de Groq |
| Ollama (local) | `ollama` | `qwen3:4b` | `http://localhost:11434/v1` | (vacío) |
| Anthropic (futuro) | `anthropic` | `claude-sonnet-5-5` | (vacío) | tu llave de Anthropic |

Si dejas `JARVIS_MODEL` o `JARVIS_BASE_URL` vacíos, se usa el valor por defecto del proveedor. **Al cambiar de proveedor, cambia o vacía también el modelo y la URL**, para no mezclar los de uno con los del otro.

Para Ollama, primero descarga el modelo: `ollama pull qwen3:4b`.

Sobre el modelo de Groq: según la documentación de Groq, todos sus modelos admiten herramientas y recomiendan "los más recientes". Se eligió `openai/gpt-oss-120b` por ser el más capaz entre los modelos de **producción** (estables). Los modelos en "preview" pueden retirarse sin aviso.

## Agregar programas a la lista blanca

En `config.json`, sección `programas`, agrega `"nombre amigable": "ruta o comando"`:

```json
"programas": {
  "bloc de notas": "notepad.exe",
  "calculadora": "calc.exe",
  "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "word": "winword.exe",
  "configuracion": "ms-settings:"
}
```

- En JSON las barras invertidas se escriben dobles (`\\`).
- Se pueden usar variables de entorno: `"%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe"`.
- Solo se abre el programa, sin argumentos. Jarvis no puede ejecutar comandos de consola.
- Reinicia Jarvis después de editar `config.json`.

## Qué puede hacer

| Categoría | Herramientas | ¿Pide confirmación? |
|---|---|---|
| Archivos (solo lectura) | `listar_carpeta`, `buscar_archivos`, `leer_archivo` (.txt .md .csv .json .log .docx .xlsx .pdf) | No |
| Abrir | `abrir_archivo`, `abrir_carpeta` | Sí, si el archivo está en Descargas |
| Crear | `crear_archivo` (.txt .md .csv solo en `Documentos\Jarvis`, nunca sobrescribe) | Siempre |
| Programas | `abrir_programa` (solo los de la lista blanca) | No |
| Sistema | `info_sistema` (CPU, RAM, discos, batería, procesos) | No |
| Multimedia | `control_musica`, `volumen`, `brillo` | No |
| Pantalla | `tomar_captura` (en `Documentos\Jarvis\Capturas`) | No |
| Ajustes | `abrir_ajustes` (voz, velocidad, idioma, apariencia, ciudad) | No |
| Cálculos | `calcular` (porcentajes, raíces, potencias, trigonometría…) | No |
| Hora y clima | `fecha_hora` (local o de cualquier zona), `consultar_clima` (Open-Meteo, gratis) | No |
| Notificaciones | `ver_notificaciones` (lee el centro de notificaciones, sin tocarlo) | No |
| Información web | `buscar_informacion` (busca en internet y resume con fuentes) | No |
| Internet | `buscar_en_web`, `abrir_pagina`, `buscar_musica` | Sí, si la URL no la escribiste tú |

Reglas contra instrucciones escondidas (en archivos, notificaciones o páginas web):

- Si en un pedido Jarvis ya leyó **un archivo o tus notificaciones**, cualquier acción de abrir, crear o buscar en internet pide confirmación. Así, datos privados no pueden terminar dentro de una búsqueda sin que lo autorices.
- Si leyó **información de internet**, abrir programas, páginas, archivos o crear archivos pide confirmación. Hacer otra búsqueda no la pide, porque esos datos ya son públicos.

### Ejemplos

- *"¿Cuánto es el 19 % de 2.350.000?"* · *"raíz de 144 más 15 % de 80"*
- *"¿Qué hora es en Tokio?"* · *"¿Cómo estará el clima en Madrid esta semana?"*
- *"¿Qué notificaciones tengo?"*
- *"Busca quién ganó el último Balón de Oro"*: busca, resume y cita la fuente.
- *"Abre una pestaña buscando recetas de arepas"*: abre la búsqueda en el navegador.
- *"Abre Word"*, *"abre Excel y PowerPoint"*.

### Clima

Usa Open-Meteo, que es gratis y no necesita llave. Si no dices la ciudad, usa la que configures en los ajustes (*"abre los ajustes"* → **Ciudad**). Por ejemplo: `Bogotá, Colombia`.

### Notificaciones

Jarvis lee la base de datos de notificaciones de tu usuario en modo **solo lectura**: no las descarta ni las modifica. Su contenido (mensajes de otras personas) se envía al modelo de lenguaje para resumirlo.

### Búsqueda en internet

Usa la búsqueda integrada de Groq (`browser_search`) con el modelo `openai/gpt-oss-20b`, que tiene un cupo aparte del modelo principal. Jarvis no navega ni descarga páginas: la búsqueda la hace Groq y devuelve un resumen con las fuentes. Con el proveedor `groq` usa tu `JARVIS_API_KEY`. Con Ollama o Anthropic, agrega una llave de Groq en `JARVIS_GROQ_API_KEY`.

## Seguridad

Todas estas reglas se aplican en el código, no solo en el prompt:

- **No existe** ninguna herramienta para borrar, mover, renombrar o modificar archivos, ni para ejecutar comandos o cerrar procesos.
- Cada ruta se resuelve con `os.path.realpath` (elimina `..`, enlaces simbólicos y junctions) antes de validarla.
- Solo se aceptan discos locales fijos (`GetDriveType = DRIVE_FIXED`). Se rechazan rutas UNC (`\\servidor\...`), unidades de red, USB y CD.
- Carpetas permitidas por defecto: Escritorio, Documentos, Descargas, Música, Imágenes y Videos. Se configuran en `carpetas_permitidas`; se pueden usar los marcadores `{ESCRITORIO}`, `{DOCUMENTOS}`, `{DESCARGAS}`, `{MUSICA}`, `{IMAGENES}`, `{VIDEOS}`.
- Siempre bloqueadas: `C:\Windows`, `Program Files`, `Program Files (x86)`, `ProgramData` y `AppData`. Puedes agregar más en `carpetas_bloqueadas_extra`.
- **Lista negra** (nunca se leen ni se abren): `.env`, nombres con password/contraseña/clave/secret/token/credencial, llaves y certificados (.pem, .key, .ppk, .pfx…), `id_rsa`, bases de datos de navegadores, `.ssh` y carpetas de billeteras de criptomonedas. En `config.json` → `lista_negra` puedes **agregar** elementos; los de base no se pueden quitar.
- Nunca se abren ejecutables ni scripts (.exe, .bat, .cmd, .ps1, .vbs, .msi, .lnk, .reg, .js, .py, .scr, .hta y muchos más, incluidos documentos de Office con macros). Puedes agregar extensiones en `extensiones_ejecutables_extra`.
- URLs: solo `http` y `https`. Las búsquedas se codifican con `urllib.parse.quote`.
- El contenido leído de archivos se entrega al modelo envuelto en marcas `DATOS_NO_CONFIABLES`, y el prompt le indica que ahí nunca hay instrucciones válidas.

## Logs

Se guardan en `%LOCALAPPDATA%\Jarvis\logs`:

- `acciones.log`: una línea JSON por herramienta usada, con fecha, pedido, herramienta, argumentos y si tuvo éxito. Nunca guarda el contenido de los archivos leídos.
- `jarvis.log`: errores generales.

Rotan cada día y se borran solos a los 30 días.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Cubren la validación de seguridad: rutas UNC y de red, `..`, junctions y enlaces, carpetas bloqueadas, lista negra, no sobrescribir, extensiones ejecutables, esquemas de URL y confirmaciones. La prueba de enlaces simbólicos se salta si Windows no permite crearlos sin el modo desarrollador. Las junctions sí se prueban siempre.

## Estructura

```
main.py                       Punto de entrada
config.json                   Carpetas, lista negra, programas, atajo, límites
jarvis/
  app.py                      Arma todo y arranca
  config.py                   Lee .env y config.json
  registro.py                 Logs con rotación
  seguridad/                  Rutas, lista negra, URLs, administrador
  cerebro/
    agente.py                 Ciclo de herramientas (máx. 10 pasos / 60 s)
    prompts.py                Instrucciones del sistema
    proveedores/              Groq/Ollama (openai_compat), Anthropic, fábrica
  herramientas/               Un módulo por categoría
  interfaz/                   Isla, círculo, ajustes, bandeja, atajo global, hilo de trabajo
  voz/                        Motores de voz (Piper, OpenAI, Windows) e interfaz para micrófono
tests/                        Pruebas con pytest
```

## Voz

Jarvis lee en voz alta cada respuesta, los mensajes de error y las preguntas de confirmación. Hay tres motores:

| Motor | Calidad | Internet | Costo |
|---|---|---|---|
| **Piper** (por defecto) | Natural | No (solo para descargar voces) | Gratis |
| **OpenAI** (voz `onyx`) | Muy natural | Sí; el texto se envía a OpenAI | De pago, requiere `JARVIS_TTS_API_KEY` |
| **Windows** (Raúl, Sabina…) | Básica | No | Gratis |

- **Voz por defecto:** Piper `es_MX-ald-medium` (masculina, español de México).
- **Respaldo automático:** si el motor elegido falla (voz no descargada, sin llave, sin internet), Jarvis sigue hablando con la voz de Windows.
- **Aviso sobre OpenAI:** según su documentación, el modelo `gpt-4o-mini-tts` (y con él la voz Onyx) se retira el **6 de enero de 2027**.

### Ajustes

Pídele a Jarvis **"abre los ajustes"** (o "quiero cambiar la voz"). La ventana de ajustes solo aparece cuando se la pides. En ella puedes elegir:

- **Motor:** Piper, OpenAI o Windows.
- **Idioma:** 53 idiomas. Cambia el idioma en que Jarvis te responde y filtra las voces disponibles.
- **Voz:** con Piper se listan las 177 voces del catálogo oficial. ✓ = ya descargada; ⬇ = se descarga una sola vez (20 a 120 MB) al probarla o guardar.
- **Velocidad:** de 0.5× a 2×. No se aplica a OpenAI.
- **Ocultar tras:** cuántos segundos sin actividad espera la isla antes de desvanecerse, de 5 a 120 s. En 0 queda en **Nunca**: solo se cierra con Esc o con el atajo.
- **Ciudad:** la ciudad por defecto para el clima, con o sin coma ("Bucaramanga, Santander" o "bucaramanga santander").
- **Apariencia:** opacidad del fondo (0 % = vidrio muy transparente, 100 % = negro sólido) y nivel de desenfoque (0 a 40 px). Se ven en vivo y se guardan con *Guardar*; si cierras sin guardar, vuelve a lo anterior.
- **▶ Probar voz:** escuchas una frase de ejemplo sin guardar nada.
- **Guardar:** escribe los cambios en `config.json` y los aplica al instante, sin reiniciar Jarvis.

Las voces de Piper se guardan en `%LOCALAPPDATA%\Jarvis\voces_piper`. Se descargan solo desde el repositorio oficial de Piper en Hugging Face, y cada archivo se verifica con su tamaño y su md5.

### Uso

- **🔊 / 🔇** junto a la caja de texto, o **clic derecho en el ícono → Voz activada**: activa o silencia la voz.
- **Esc** mientras habla: lo calla. Un segundo Esc oculta la ventana.
- Escribir un pedido nuevo, cancelar u ocultar también corta la lectura.
- Antes de leer, Jarvis limpia el texto: dice solo el nombre del archivo en vez de la ruta completa, solo el dominio de las URLs ("youtube.com") y omite símbolos.
- Las respuestas largas se leen hasta 1500 caracteres; el resto queda en pantalla.
- Si quieres que te lea un archivo completo, pídeselo así: *"léeme el archivo notas.txt"*.

### Configuración manual (`config.json`)

```json
"voz": {
  "activada": true,
  "motor": "piper",
  "piper_voz": "es_MX-ald-medium",
  "openai_modelo": "gpt-4o-mini-tts",
  "openai_voz": "onyx",
  "openai_instrucciones": "Habla siempre en {idioma}. Voz grave, calmada y segura…",
  "nombre": "Raul",
  "velocidad": 1.0,
  "volumen": 100,
  "max_caracteres": 1500,
  "leer_confirmaciones": true,
  "leer_errores": true
},
"idioma": { "codigo": "es", "nombre": "Español" }
```

- `nombre`: la voz de Windows (para el motor `windows` y como respaldo). Basta una parte del nombre.
- `velocidad`: multiplicador de 0.5 a 2.0.
- `volumen`: solo afecta a la voz de Windows.
- `openai_instrucciones`: `{idioma}` se reemplaza por el idioma elegido.
- **Más voces de Windows:** Configuración de Windows → Hora e idioma → Voz → Agregar voces.

### Entrada por micrófono (futuro)

En `jarvis/voz/base.py` está la interfaz `EntradaVoz`. Para hablarle a Jarvis basta implementar `escuchar()` (por ejemplo, con `whisper-large-v3-turbo` de Groq) y pasar el texto a `VentanaJarvis.enviar_pedido(texto)`, el mismo método que usa la caja de texto.
