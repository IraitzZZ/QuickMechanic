"""Lectura y escritura de los .ini de Assetto Corsa.

Los .ini de AC son el formato clasico de Windows, con detalles propios::

    [ENGINE_DATA]
    INERTIA=0.120                 ; engine inertia
    LIMITER=6500                  ; engine rev limiter. 0 no limiter

    [BASIC]
    GRAPHICS_OFFSET=0,-0.545,-0.06
    INERTIA=1.6,1.30,4.02

Este modulo NO reescribe el archivo con un parser generico: eso borraria todos
los comentarios, el orden de las claves y el formato original. Aqui se guardan
las lineas tal cual y en `save()` se sustituyen **solo** las lineas de las
claves que el usuario ha tocado. Asi el coche sigue siendo exactamente igual de
valido para AC (y para cualquier otro programa que lea esos .ini).

Ejemplo::

    ini = ACIni(car.data_dir / "engine.ini")
    ini.get_int("ENGINE_DATA", "LIMITER")       # 6500
    ini.set_value("ENGINE_DATA", "LIMITER", 7200)
    ini.save()                                  # crea engine.ini.bak la primera vez
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

__all__ = ["ACIni", "fmt_value", "read_ui_car_name"]

# [SECCION]  (puede llevar un comentario detras)
SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]*)\]\s*(?P<tail>[;#].*)?$")
#         indentation   CLAVE   =   valor
KEY_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<key>[^=;#\s][^=]*?)[ \t]*=(?P<value>.*)$")
COMMENT_RE = re.compile(r"^\s*(?:[;#]|//)")

_BACKUP_SUFFIX = ".bak"


def _read_text(path: Path) -> str:
    # newline="": sin traducir los finales de linea, para poder devolver el
    # archivo tal cual lo escribio AC (CRLF incluidos).
    # surrogateescape: si el archivo trae bytes raros (mods) no se corrompen al
    # volver a escribirlo.
    with path.open("r", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        return fh.read()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
        fh.write(text)


def fmt_value(value: float | int | str) -> str:
    """Convierte un valor de Python al texto que espera AC."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text if text and text != "-" else "0"
    return str(value)


class ACIni:
    """Un .ini de AC que se puede editar sin destruir el archivo."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._exists = self.path.is_file()
        self._raw = _read_text(self.path) if self._exists else ""
        self._nl = "\r\n" if "\r\n" in self._raw else "\n"
        self._lines: list[str] = self._raw.splitlines()

        self._sections: list[str] = []
        self._values: dict[str, dict[str, str]] = {}
        # (SECCION, CLAVE) en mayusculas -> (seccion escrita, clave escrita)
        self._index: dict[tuple[str, str], tuple[str, str]] = {}
        # (SECCION, CLAVE) -> (clave escrita, valor nuevo, valor viejo)
        self._changes: dict[tuple[str, str], tuple[str, str, str]] = {}
        self._removals: set[tuple[str, str]] = set()
        self._section_removals: set[str] = set()
        self._parse()
        # copia de los valores del archivo, para detectar si un valor vuelve a su
        # estado original y entonces no hay nada que guardar
        self._file_values: dict[str, dict[str, str]] = {
            section: dict(values) for section, values in self._values.items()
        }

    # ---------------------------------------------------------------- lectura
    def _parse(self) -> None:
        section: str | None = None
        for raw in self._lines:
            m = SECTION_RE.match(raw)
            if m and not COMMENT_RE.match(raw):
                section = m.group("name").strip()
                if section not in self._sections:
                    self._sections.append(section)
                self._values.setdefault(section, {})
                continue
            if section is None or COMMENT_RE.match(raw):
                continue
            km = KEY_RE.match(raw)
            if not km:
                continue
            key = km.group("key").strip()
            value = self._clean(km.group("value"))
            # si una clave sale repetida se usa la primera, que es la que save()
            # reescribe, para que lectura y escritura cuenten lo mismo
            self._values[section].setdefault(key, value)
            self._index.setdefault((section.upper(), key.upper()), (section, key))

    @staticmethod
    def _clean(value: str) -> str:
        """Quita el comentario de final de linea y los espacios sobrantes."""
        return value.split(";", 1)[0].strip()

    def _resolve(self, section: str) -> str | None:
        upper = section.strip().upper()
        for name in self._sections:
            if name.upper() == upper:
                return name
        return None

    def sections(self) -> list[str]:
        return [
            name for name in self._sections if name.upper() not in self._section_removals
        ]

    def keys(self, section: str) -> list[str]:
        resolved = self._resolve(section)
        if resolved is None or resolved.upper() in self._section_removals:
            return []
        return list(self._values.get(resolved, {}))

    def has_section(self, section: str) -> bool:
        resolved = self._resolve(section)
        return resolved is not None and resolved.upper() not in self._section_removals

    def section(self, section: str) -> dict[str, str]:
        resolved = self._resolve(section)
        return dict(self._values.get(resolved, {})) if resolved else {}

    def has(self, section: str, key: str) -> bool:
        return (section.strip().upper(), key.strip().upper()) in self._index

    def get(self, section: str, key: str, default: str = "") -> str:
        try:
            section_written, key_written = self._index[
                (section.strip().upper(), key.strip().upper())
            ]
        except KeyError:
            return default
        return self._values.get(section_written, {}).get(key_written, default)

    def get_float(self, section: str, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(section, key, ""))
        except (TypeError, ValueError):
            return default

    def get_int(self, section: str, key: str, default: int = 0) -> int:
        try:
            return int(float(self.get(section, key, "")))
        except (TypeError, ValueError):
            return default

    def get_bool(self, section: str, key: str, default: bool = False) -> bool:
        text = self.get(section, key, "")
        if text == "":
            return default
        try:
            return float(text) != 0.0
        except ValueError:
            return text.strip().lower() in ("true", "yes", "on")

    def get_list(self, section: str, key: str, cast=float) -> list:
        """Valores separados por comas: '1.6,1.30,4.02' -> [1.6, 1.3, 4.02]."""
        out = []
        for chunk in self.get(section, key, "").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                out.append(cast(chunk))
            except ValueError:
                pass
        return out

    # --------------------------------------------------------------- escritura
    def set_value(self, section: str, key: str, value: float | int | str) -> None:
        text = fmt_value(value)
        token = (section.strip().upper(), key.strip().upper())
        found = self._index.get(token)
        if found is not None:
            section_written, key_written = found
        else:
            section_written = self._resolve(section) or section.strip()
            key_written = key.strip()
            self._index[token] = (section_written, key_written)
            if section_written not in self._sections:
                self._sections.append(section_written)

        old = self._file_values.get(section_written, {}).get(key_written, "")
        self._values.setdefault(section_written, {})[key_written] = text
        self._removals.discard(token)
        self._section_removals.discard(token[0])  # volver a escribir en ella la reactiva
        if old == text:
            # ha vuelto al valor del archivo: ya no es un cambio pendiente
            self._changes.pop(token, None)
            return
        self._changes[token] = (key_written, text, old)

    def remove_key(self, section: str, key: str) -> None:
        """Desactiva una clave comentandola (no borra la informacion del coche)."""
        token = (section.strip().upper(), key.strip().upper())
        if token not in self._index:
            return
        section_written, key_written = self._index[token]
        self._values.get(section_written, {}).pop(key_written, None)
        self._changes.pop(token, None)
        self._removals.add(token)

    def remove_section(self, section: str) -> None:
        """Comenta una seccion entera con sus claves (para quitar, por ejemplo, el turbo)."""
        resolved = self._resolve(section)
        if resolved is None or resolved.upper() in self._section_removals:
            return
        for key in list(self._values.get(resolved, {})):
            self.remove_key(resolved, key)
        self._section_removals.add(resolved.upper())

    @property
    def changed(self) -> bool:
        return bool(self._changes or self._removals or self._section_removals)

    def diff(self) -> list[tuple[str, str, str, str]]:
        """[(seccion, clave, valor_viejo, valor_nuevo)] de lo que se va a guardar."""
        return [(token[0], key, old, new) for token, (key, new, old) in self._changes.items()]

    # ------------------------------------------------------------------ guardar
    def save(self, backup: bool = True) -> Path | None:
        """Escribe solo las lineas cambiadas. Devuelve la ruta, o None si no habia nada."""
        if not self.changed:
            return None

        out: list[str] = []
        current: str | None = None
        # seccion -> indice en `out` donde insertar claves nuevas (tras su ultima clave)
        insert_at: dict[str, int] = {}
        done: set[tuple[str, str]] = set()

        for raw in self._lines:
            m = SECTION_RE.match(raw)
            if m and not COMMENT_RE.match(raw):
                current = m.group("name").strip().upper()
                if current in self._section_removals:
                    # seccion desactivada: se comenta su cabecera (las claves ya
                    # las comenta remove_key)
                    out.append(self._comment_line(raw))
                    continue
                out.append(raw)
                insert_at.setdefault(current, len(out))
                continue

            token = None
            if current is not None and not COMMENT_RE.match(raw):
                km = KEY_RE.match(raw)
                if km:
                    token = (current, km.group("key").strip().upper())

            if token is not None and token not in done:
                change = self._changes.get(token)
                if change is not None:
                    done.add(token)
                    out.append(self._rewrite_line(raw, change[0], change[1]))
                    insert_at[current or ""] = len(out)
                    continue
                if token in self._removals:
                    done.add(token)
                    out.append(self._comment_line(raw))
                    insert_at[current or ""] = len(out)
                    continue

            out.append(raw)
            if token is not None:
                insert_at[current or ""] = len(out)

        # claves que no existian en el archivo
        pending: dict[str, list[tuple[str, str]]] = {}
        for token, (key_written, text, _old) in self._changes.items():
            if token in done:
                continue
            pending.setdefault(token[0], []).append((key_written, text))

        inserts: list[tuple[int, list[str]]] = []
        appended: list[str] = []
        for section, entries in pending.items():
            block = [f"{key}={text}" for key, text in entries]
            if section in insert_at:
                inserts.append((insert_at[section], block))
            else:
                if out or appended:
                    appended.append("")
                appended.append(f"[{section}]")
                appended.extend(block)

        # de abajo hacia arriba para que los indices no se muevan
        for index, block in sorted(inserts, key=lambda item: -item[0]):
            out[index:index] = block
        out.extend(appended)

        text = self._nl.join(out) + self._nl

        if backup and self._exists:
            backup_path = self.path.with_name(self.path.name + _BACKUP_SUFFIX)
            if not backup_path.exists():
                # el .bak conserva el archivo ORIGINAL aunque se guarde varias veces
                shutil.copy2(self.path, backup_path)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        _write_text(tmp, text)
        os.replace(tmp, self.path)

        saved = self.path
        self._reload()
        return saved

    def _reload(self) -> None:
        self.__init__(self.path)  # noqa: PLC2801  (reinicia el estado desde disco)

    @staticmethod
    def _rewrite_line(raw: str, key: str, text: str) -> str:
        km = KEY_RE.match(raw)
        if km is None:  # no deberia pasar
            return f"{key}={text}"
        indent = km.group("indent")
        value = km.group("value")
        tail = ""
        if ";" in value:
            head, comment = value.split(";", 1)
            spacing = head[len(head.rstrip()):] or " "
            tail = f"{spacing};{comment}"
        return f"{indent}{key}={text}{tail}"

    @staticmethod
    def _comment_line(raw: str) -> str:
        indent = raw[: len(raw) - len(raw.lstrip())]
        return f"{indent};{raw.strip()}"


# ----------------------------------------------------------------------
# Utilidad: nombre bonito del coche desde ui_car.json
# ----------------------------------------------------------------------
def read_ui_car_name(ui_json: Path) -> str | None:
    try:
        data = json.loads(ui_json.read_text(encoding="utf-8", errors="replace"))
        name = data.get("name")
        if isinstance(name, dict):  # algunos traen {"eng": "...", ...}
            return name.get("eng") or next(iter(name.values()), None)
        if isinstance(name, str):
            return re.sub(r"%(.+?)%", r"\1", name)  # AC usa placeholders %Porsche%
    except Exception:
        pass
    return None
