"""Skins, previsualizacion y ficha de un coche de Assetto Corsa.

Cada coche guarda una carpeta por skin en ``content/cars/<coche>/skins/<Skin>/``
y dentro deja una imagen de previsualizacion llamada ``preview``: casi siempre
``preview.jpg``, aunque algunos mods dejan ``preview.png`` o variantes. Esa es la
imagen que usa el juego (y Content Manager) para enseñar el coche, asi que es la
que muestra Quick Mechanic.

De la misma carpeta se saca tambien la ficha del coche (``ui/ui_car.json``:
marca, clase, especificaciones) y su escudo (``ui/badge.png`` o ``logo.png``).

Ejemplo::

    skins = list_skins(car.folder)
    skins[0].label            # "Tea Hair"
    skins[0].preview          # .../skins/Tea_hair/preview.jpg
    read_car_meta(car.folder).brand     # "Nissan"
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path

__all__ = [
    "Skin",
    "CarMeta",
    "PREVIEW_NAMES",
    "IMAGE_SUFFIXES",
    "find_preview",
    "list_skins",
    "car_badge",
    "read_car_meta",
    "storage_name",
    "strip_html",
]

# Nombres del fichero de preview, en orden de preferencia. AC y CSP generan
# preview.jpg; los mods viejos dejan PNG.
PREVIEW_NAMES = (
    "preview.jpg",
    "preview.jpeg",
    "preview.png",
    "preview.webp",
    "preview.bmp",
)
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")
# Copias que dejan algunos mods: no son la preview oficial del coche
SKIPPED_STEMS = {"preview_old", "preview_bak", "preview_backup", "preview_original"}

# Nombre largo -> etiqueta que se enseña en la ficha del coche
SPEC_LABELS = {
    "bhp": "Potencia",
    "torque": "Par",
    "weight": "Peso",
    "topspeed": "Velocidad maxima",
    "acceleration": "0-100 km/h",
    "pwratio": "Peso/potencia",
    "range": "Autonomia",
    "seatbelt": "Cinturon",
}
SPEC_ORDER = ("bhp", "torque", "weight", "pwratio", "topspeed", "acceleration", "range")

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def strip_html(text: str) -> str:
    """Convierte el HTML de ui_car.json en texto plano legible."""
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = _TAG_RE.sub("", text)
    text = unescape(text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_LINES_RE.sub("\n\n", text).strip()


def find_preview(folder: str | Path) -> Path | None:
    """Imagen de preview dentro de una carpeta (la skin o el propio coche).

    Se prueban primero los nombres habituales y, si no, cualquier ``preview*``
    que sea una imagen, ignorando las copias de seguridad.
    """
    folder = Path(folder)
    for name in PREVIEW_NAMES:
        candidate = folder / name
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    try:
        entries = sorted(folder.glob("preview*"))
    except OSError:
        return None
    for entry in entries:
        try:
            if (
                entry.is_file()
                and entry.suffix.lower() in IMAGE_SUFFIXES
                and entry.stem.lower() not in SKIPPED_STEMS
            ):
                return entry
        except OSError:
            continue
    return None


def storage_name(name: dict | str | None) -> str:
    """Los nombres de ui_car.json a veces son ``{"eng": "...", "ita": "..."}``."""
    if isinstance(name, dict):
        return str(name.get("eng") or next(iter(name.values()), "") or "")
    if isinstance(name, str):
        return name
    return ""


@dataclass
class Skin:
    """Una skin del coche (``skins/<carpeta>/``)."""

    folder: Path
    name: str
    display_name: str = ""
    preview: Path | None = None
    number: str = ""
    team: str = ""
    driver: str = ""
    priority: int = 0

    @property
    def label(self) -> str:
        return self.display_name or self.name

    @property
    def has_preview(self) -> bool:
        return self.preview is not None

    @property
    def details(self) -> list[str]:
        """Datos de la skin para enseñar bajo la imagen (solo los que hay)."""
        out = []
        if self.team:
            out.append(self.team)
        if self.driver:
            out.append(self.driver)
        if self.number:
            out.append(f"#{self.number}")
        return out


def _read_skin_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def list_skins(car_folder: str | Path) -> list[Skin]:
    """Skins de un coche, ordenadas por prioridad y luego por nombre."""
    skins_dir = Path(car_folder) / "skins"
    out: list[Skin] = []
    try:
        entries = sorted(skins_dir.iterdir(), key=lambda path: path.name.lower())
    except OSError:
        return out

    for entry in entries:
        try:
            if not entry.is_dir():
                continue
        except OSError:
            continue
        data = _read_skin_json(entry / "ui_skin.json")
        try:
            priority = int(data.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0
        out.append(
            Skin(
                folder=entry,
                name=entry.name,
                display_name=str(data.get("skinname") or "").strip(),
                preview=find_preview(entry),
                number=str(data.get("number") or "").strip(),
                team=str(data.get("team") or "").strip(),
                driver=str(data.get("drivername") or "").strip(),
                priority=priority,
            )
        )

    out.sort(key=lambda skin: (-skin.priority, skin.label.lower()))
    return out


def car_badge(car_folder: str | Path) -> Path | None:
    """Escudo/logotipo del coche (el de la ficha, no la foto del coche)."""
    folder = Path(car_folder)
    for candidate in (
        folder / "ui" / "badge.png",
        folder / "ui" / "badge.jpg",
        folder / "badge.png",
        folder / "logo.png",
        folder / "ui" / "logo.png",
    ):
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


@dataclass
class CarMeta:
    """Ficha del coche leida de ``ui/ui_car.json``."""

    name: str = ""
    brand: str = ""
    car_class: str = ""
    country: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    specs: list[tuple[str, str]] = field(default_factory=list)
    badge: Path | None = None

    @property
    def title(self) -> str:
        return self.name or self.brand

    @property
    def subtitle(self) -> str:
        return " · ".join(part for part in (self.brand, self.car_class.upper()) if part)

    def spec(self, key: str) -> str:
        wanted = key.lower()
        for label, value in self.specs:
            if label.lower() == wanted:
                return value
        for label, value in self.specs:
            if wanted in label.lower():
                return value
        return ""


def read_car_meta(car_folder: str | Path) -> CarMeta:
    """Lee ui/ui_car.json; si falta o esta roto devuelve una ficha vacia."""
    folder = Path(car_folder)
    raw = _read_skin_json(folder / "ui" / "ui_car.json")
    meta = CarMeta(badge=car_badge(folder))
    if not raw:
        meta.name = folder.name
        return meta

    meta.name = storage_name(raw.get("name")).strip()
    meta.brand = storage_name(raw.get("brand")).strip()
    meta.car_class = str(raw.get("class") or "").strip()
    meta.country = str(raw.get("country") or "").strip()
    meta.description = strip_html(str(raw.get("description") or ""))

    tags = raw.get("tags")
    if isinstance(tags, list):
        meta.tags = [str(tag).strip() for tag in tags if str(tag).strip()][:8]

    specs = raw.get("specs")
    if isinstance(specs, dict):
        known = [key for key in SPEC_ORDER if key in specs]
        extra = [key for key in specs if key not in SPEC_ORDER]
        for key in known + extra:
            value = str(specs[key]).strip()
            if value:
                meta.specs.append((SPEC_LABELS.get(key, key.replace("_", " ").title()), value))

    if not meta.name:
        meta.name = folder.name
    return meta
