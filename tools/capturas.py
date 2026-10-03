"""Genera las capturas de la documentacion (``docs/*.png`` y ``docs/capturas.html``).

Uso::

    python tools/capturas.py                      # coche por defecto
    python tools/capturas.py --car bmw_e36_320i_berlina --ac-root "D:\\...\\assettocorsa"

Necesita una instalacion de Assetto Corsa de verdad: las capturas son de la
ventana real con un coche real. Las imagenes se embeben en base64 dentro del
HTML, asi que el resultado es un unico fichero que se puede abrir en cualquier
navegador.
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from quickmechanic import theme  # noqa: E402
from quickmechanic.main import MainWindow  # noqa: E402

WIDTH, HEIGHT = 1400, 880
DOCS = ROOT / "docs"
DEFAULT_CAR = "350z_tea_hair"

VIEWS = (
    ("motor", 0, "Motor", "Par, potencia y turbo: la curva sale de power.lut, no de un .ini."),
    ("cambios", 1, "Cambios", "Marchas, grupo final y diferencial con velocidades teoricas en tabla."),
    ("chasis", 2, "Chasis", "Muelles, amortiguadores, barras, frenos y peso en unidades del garaje."),
    ("diagnostico", 3, "Diagnostico", "Ficha del coche, avisos y estado de los ficheros de fisica."),
)

_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Quick Mechanic · capturas</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; padding: 32px 24px 64px; background: #0f1115; color: #e9edf2;
         font-family: "Segoe UI", Inter, system-ui, sans-serif; }}
  header {{ max-width: 1180px; margin: 0 auto 28px; border-left: 4px solid #ff6a13;
            padding-left: 16px; }}
  h1 {{ margin: 0; font-size: 26px; font-style: italic; letter-spacing: 3px; }}
  p.sub {{ margin: 4px 0 0; color: #8d97a8; letter-spacing: 2px; font-size: 12px;
           text-transform: uppercase; }}
  figure {{ max-width: 1180px; margin: 0 auto 34px; }}
  img {{ width: 100%; border: 1px solid #2b323d; border-top: 3px solid #ff6a13;
         border-radius: 10px; display: block; }}
  figcaption {{ margin-top: 10px; color: #8d97a8; font-size: 13px; }}
  figcaption b {{ color: #ff6a13; text-transform: uppercase; letter-spacing: 1px;
                  font-size: 11px; margin-right: 8px; }}
</style></head>
<body>
<header>
  <h1>QUICK MECHANIC</h1>
  <p class="sub">capturas · {car}</p>
</header>
{figures}
</body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera docs/*.png y docs/capturas.html")
    parser.add_argument("--car", default=DEFAULT_CAR, help="carpeta del coche a fotografiar")
    parser.add_argument("--ac-root", help="ruta de la instalacion de Assetto Corsa")
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    theme.apply(app)

    window = MainWindow(ac_root=args.ac_root)
    window.resize(WIDTH, HEIGHT)
    window.show()
    app.processEvents()

    row = next(
        (index for index, car in enumerate(window._shown) if car.name == args.car), None
    )
    if row is None:
        print(f"No se ha encontrado el coche '{args.car}'.", file=sys.stderr)
        return 1
    window.car_list.setCurrentRow(row)
    app.processEvents()

    if window._car is None:
        print(
            f"'{args.car}' no tiene carpeta data/ editable: las capturas saldrian vacias.",
            file=sys.stderr,
        )
        return 1

    DOCS.mkdir(exist_ok=True)
    figures = []
    for name, index, title, caption in VIEWS:
        window.tabs.setCurrentIndex(index)
        app.processEvents()
        path = DOCS / f"{name}.png"
        window.grab().save(str(path))
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        figures.append(
            f'<figure><img alt="{title}" src="data:image/png;base64,{encoded}">'
            f"<figcaption><b>{title}</b>{caption}</figcaption></figure>"
        )
        print(f"{path.name}: {path.stat().st_size // 1024} KB")

    (DOCS / "capturas.html").write_text(
        _HTML.format(
            car=f"{window._source.ui_name} ({window._source.name})",
            figures="\n".join(figures),
        ),
        encoding="utf-8",
    )
    print(f"capturas.html: {(DOCS / 'capturas.html').stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
