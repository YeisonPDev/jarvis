"""Punto de entrada de Jarvis.

Con consola:     .venv\\Scripts\\python.exe main.py
Sin consola:     .venv\\Scripts\\pythonw.exe main.py
"""

import sys

from jarvis.app import main

if __name__ == "__main__":
    sys.exit(main())
