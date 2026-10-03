"""Ayudas compartidas por los tests."""
from __future__ import annotations

import json
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
AC_ROOT = FIXTURES                          # content/cars/... dentro de fixtures
TEST_CAR = AC_ROOT / "content" / "cars" / "ks_test_car"
TEST_CAR_DATA = TEST_CAR / "data"


class TempCarMixin(unittest.TestCase):
    """Copia el coche de prueba a una carpeta temporal para poder escribir en el."""

    def setUp(self) -> None:
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="qm_test_"))
        self.data_dir = self.tmp / "data"
        shutil.copytree(TEST_CAR_DATA, self.data_dir)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.read = lambda name: (self.data_dir / name).read_text(
            encoding="utf-8", errors="replace"
        )

    def comments_in(self, name: str) -> int:
        """Lineas con comentario: AC comenta al final de la linea, no solo en lineas enteras."""
        return sum(
            1
            for line in self.read(name).splitlines()
            if ";" in line or line.strip().startswith(("#", "//"))
        )


# --------------------------------------------------------------------------
# Imagenes de prueba: se generan al vuelo para no guardar binarios en el repo
# --------------------------------------------------------------------------
def write_png(path: Path, width: int = 4, height: int = 3, color=(255, 106, 19)) -> Path:
    """Escribe un PNG minimo valido (color plano) usando solo la libreria estandar."""
    row = bytes(color) * width
    raw = b"".join(b"\x00" + row for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path


def make_skin(
    car_dir: Path,
    name: str = "Quick_Orange",
    *,
    preview: bool = True,
    display_name: str = "",
    number: str = "",
    team: str = "",
    priority: int = 0,
    extra_files: bool = False,
) -> Path:
    """Crea una carpeta de skin como las del juego, con su preview y ui_skin.json."""
    folder = Path(car_dir) / "skins" / name
    folder.mkdir(parents=True, exist_ok=True)
    if preview:
        write_png(folder / "preview.png")
    (folder / "ui_skin.json").write_text(
        json.dumps(
            {
                "skinname": display_name or name.replace("_", " "),
                "drivername": "",
                "number": number,
                "team": team,
                "priority": priority,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if extra_files:
        (folder / "livery.png").write_bytes(b"not really an image")
    return folder


def make_car_preview(car_dir: Path, name: str = "preview.png") -> Path:
    """Deja una preview suelta en la raiz del coche (algunos mods lo hacen asi)."""
    return write_png(Path(car_dir) / name)
