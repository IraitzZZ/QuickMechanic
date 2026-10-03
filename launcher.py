"""Arranque del programa y de la version empaquetada (.exe).

PyInstaller necesita un script de entrada que no use imports relativos, asi que
el .exe arranca por aqui.
"""
from __future__ import annotations

import sys

from quickmechanic.main import main

if __name__ == "__main__":
    sys.exit(main())
