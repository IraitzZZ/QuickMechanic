"""Curvas .lut y relaciones .rto de Assetto Corsa.

No son .ini: cada linea es una lista de numeros separados por ``|``::

    power.lut       0|98        <- rpm|par motor en Nm  (la curva de potencia)
    coast.lut       1000|-45    <- rpm|par de freno motor
    analog_*.lut    0.5         <- un unico valor (instrumentacion del cockpit)
    ratios.rto      41//7|5.857 <- dientes//pinon | relacion (gearset)

Los comentarios (``;`` o ``//``) y el formato de cada linea se conservan: solo
se reescriben las lineas cuyos numeros cambian.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["LUT", "RtoInfo", "read_rto", "fmt_number"]

COMMENT_RE = re.compile(r"^\s*(?:[;#]|//)")
_BACKUP_SUFFIX = ".bak"


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        return fh.read()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        fh.write(text)


def fmt_number(value: float) -> str:
    """Numero con el minimo de decimales posible: 6500.0 -> '6500', 3.818 -> '3.818'."""
    value = float(value)
    if value == int(value) and abs(value) < 1e12:
        return str(int(value))
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-" else "0"


class LUT:
    """Curva de AC (power.lut, coast.lut, ...). Editable y guardable."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._exists = self.path.is_file()
        self._raw = _read_text(self.path) if self._exists else ""
        self._nl = "\r\n" if "\r\n" in self._raw else "\n"
        self._lines: list[str] = self._raw.splitlines()

        self.rows: list[list[float]] = []
        self._original_rows: list[list[float]] = []
        self._row_line: list[int] = []
        self._row_indent: list[str] = []
        self._row_sep: list[str] = []
        self._row_tail: list[str] = []
        self._dirty: set[int] = set()
        self._parse()

    def _parse(self) -> None:
        for index, raw in enumerate(self._lines):
            if not raw.strip() or COMMENT_RE.match(raw):
                continue
            body, tail = self._split_tail(raw)
            fields = [f for f in body.split("|")]
            try:
                values = [float(f.strip()) for f in fields]
            except ValueError:
                continue  # linea rara (cabecera de texto): se deja intacta
            self.rows.append(values)
            self._original_rows.append(list(values))
            self._row_line.append(index)
            self._row_indent.append(raw[: len(raw) - len(raw.lstrip())])
            self._row_sep.append(" | " if " | " in raw else "|")
            self._row_tail.append(tail)

    @staticmethod
    def _split_tail(raw: str) -> tuple[str, str]:
        for marker in (";", "//"):
            position = raw.find(marker)
            if position != -1:
                return raw[:position], raw[position:]
        return raw, ""

    # ------------------------------------------------------------------ lectura
    @property
    def exists(self) -> bool:
        return self._exists

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        return max((len(r) for r in self.rows), default=0)

    def column(self, index: int = -1) -> list[float]:
        out = []
        for row in self.rows:
            if -len(row) <= index < len(row):
                out.append(row[index])
        return out

    def to_points(self, x: int = 0, y: int = -1) -> list[tuple[float, float]]:
        return [(row[x], row[y]) for row in self.rows if len(row) > max(x, y)]

    def min_max(self, index: int = -1) -> tuple[float, float]:
        values = self.column(index)
        return (min(values), max(values)) if values else (0.0, 0.0)

    def peak(self, x: int = 0, y: int = -1) -> tuple[float, float] | None:
        points = self.to_points(x, y)
        return max(points, key=lambda p: p[1]) if points else None

    # ---------------------------------------------------------------- escritura
    def set(self, row: int, col: int, value: float) -> None:
        if not (0 <= row < len(self.rows)):
            return
        values = self.rows[row]
        if not (-len(values) <= col < len(values)):
            return
        if values[col] == value:
            return
        values[col] = float(value)
        # si la fila vuelve a como estaba en el fichero, deja de estar pendiente
        if self._original_rows[row] == values:
            self._dirty.discard(row)
        else:
            self._dirty.add(row)

    def scale(self, factor: float, col: int = -1) -> None:
        """Multiplica una columna (por defecto la ultima, el par en power.lut)."""
        for index, row in enumerate(self.rows):
            if -len(row) <= col < len(row):
                self.set(index, col, row[col] * factor)

    def set_rows(self, rows: list[list[float]]) -> None:
        """Reemplaza los valores manteniendo intactas las lineas de comentario."""
        for index, values in enumerate(rows):
            if index >= len(self.rows):
                break
            if len(values) != len(self.rows[index]):
                continue
            for col, value in enumerate(values):
                self.set(index, col, value)

    @property
    def changed(self) -> bool:
        return bool(self._dirty)

    def save(self, backup: bool = True) -> Path | None:
        if not self._dirty:
            return None
        out = list(self._lines)
        for row_index in sorted(self._dirty):
            line_index = self._row_line[row_index]
            body = self._row_sep[row_index].join(
                fmt_number(v) for v in self.rows[row_index]
            )
            out[line_index] = f"{self._row_indent[row_index]}{body}{self._row_tail[row_index]}"

        text = self._nl.join(out) + self._nl
        if backup and self._exists:
            backup_path = self.path.with_name(self.path.name + _BACKUP_SUFFIX)
            if not backup_path.exists():
                shutil.copy2(self.path, backup_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        _write_text(tmp, text)
        os.replace(tmp, self.path)

        saved = self.path
        self.__init__(self.path)  # noqa: PLC2801
        return saved


# ----------------------------------------------------------------------
# Ficheros .rto (conjuntos de relaciones de cambio / grupos finales)
# ----------------------------------------------------------------------
@dataclass
class RtoInfo:
    """Informacion de un ratios.rto / final.rto (de momento, solo lectura).

    En AC estos ficheros son un *catalogo* de relaciones: el setup del coche
    permite elegir entre las que aparecen aqui (secciones [GEARSET_x] de
    setup.ini). Por eso no se editan desde el editor de marchas normal.
    """

    path: Path
    entries: list[tuple[str, float | None]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def ratios(self) -> list[float]:
        return [value for _text, value in self.entries if value is not None]

    @property
    def uses_teeth(self) -> bool:
        return any("//" in text for text, _value in self.entries)

    def best_match(self, ratio: float) -> int | None:
        """Indice de la entrada del catalogo mas parecida a `ratio`."""
        best: tuple[float, int] | None = None
        for index, value in enumerate(self.ratios):
            distance = abs(value - ratio)
            if best is None or distance < best[0]:
                best = (distance, index)
        return best[1] if best else None


def read_rto(path: str | Path) -> RtoInfo | None:
    path = Path(path)
    if not path.is_file():
        return None
    info = RtoInfo(path=path)
    for raw in _read_text(path).splitlines():
        line = raw.strip()
        if not line or COMMENT_RE.match(line):
            continue
        tokens = [t.strip() for t in line.split("|")]
        value: float | None = None
        for token in reversed(tokens):
            try:
                value = float(token)
                break
            except ValueError:
                continue
        info.entries.append((line, value))
    return info
