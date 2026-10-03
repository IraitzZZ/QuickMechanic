"""Autotest de Quick Mechanic.

Comprueba, sin abrir la ventana:

1. Que se encuentra la instalacion de Assetto Corsa.
2. Que se leen los datos reales de un coche (motor, marchas, chasis).
3. Que el ciclo completo editar -> guardar -> releer funciona **sobre una copia**
   de un coche real, sin tocar nunca el fichero del juego.
4. Que los comentarios y el formato del .ini original se mantienen.

Se puede lanzar desde el .exe::

    QuickMechanic.exe --selftest --report informe.txt
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from . import ac_scanner, car_data, units

__all__ = ["run"]


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0

    def ok(self, text: str) -> None:
        self.lines.append(f"[ok]    {text}")

    def fail(self, text: str, error: str = "") -> None:
        self.failures += 1
        self.lines.append(f"[FALLO] {text}")
        if error:
            self.lines.append(f"        {error}")

    def info(self, text: str) -> None:
        self.lines.append(f"        {text}")

    def text(self) -> str:
        header = "Quick Mechanic - autotest"
        footer = (
            "TODO CORRECTO"
            if not self.failures
            else f"{self.failures} comprobacion(es) fallidas"
        )
        return "\n".join([header, "=" * len(header), *self.lines, "", footer])


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _comment_lines(path: Path) -> int:
    """Lineas con comentario. AC comenta casi siempre al final de la linea
    ("LIMITER=6500  ; engine rev limiter"), asi que se cuentan las dos formas."""
    return sum(
        1
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ";" in line or line.strip().startswith(("#", "//"))
    )


_comments = _comment_lines  # alias corto para el resto del modulo


def run(ac_root: str | Path | None = None, report: str | Path | None = None, cars: int = 3) -> int:
    log = Report()

    # 1 ------------------------------------------------------------ instalacion
    extra = [ac_root] if ac_root else []
    root = ac_scanner.find_ac_root(extra=extra)
    if root is None:
        log.fail("No se encuentra la instalacion de Assetto Corsa", "usa --ac-root RUTA")
        return _finish(log, report)
    log.ok(f"Instalacion encontrada: {root}")

    installed = ac_scanner.list_cars(root)
    editable = [car for car in installed if car.editable]
    log.ok(f"{len(installed)} coches instalados, {len(editable)} con carpeta data/ editable")
    if not editable:
        log.fail("Ningun coche con datos editables", "extrae algun data.acd para poder probar")
        return _finish(log, report)

    # 2 ------------------------------------------------------------------ lectura
    # se prefiere un coche con comentarios en los .ini: asi el test comprueba de
    # verdad que el guardado no los borra
    sample = next((car for car in editable if _comments(car.engine_ini) > 5), editable[0])
    data = car_data.CarData.from_car(sample)
    if data.limiter <= 0:
        log.fail(f"{sample.name}: LIMITER no se ha leido")
    else:
        log.ok(f"Lectura de {sample.name}: limitador {data.limiter} rpm")
    points = data.power_points(scaled=False)
    if not points:
        log.fail(f"{sample.name}: sin curva de potencia ({data.power_curve_file})")
    else:
        rpm_torque, torque = data.peak_torque(scaled=False)
        rpm_hp, hp = data.peak_power(scaled=False)
        log.ok(
            f"Curva de potencia: {len(points)} puntos · {torque:.0f} Nm a {rpm_torque:.0f} rpm · "
            f"{hp:.0f} CV a {rpm_hp:.0f} rpm"
        )
    ratios = data.gear_ratios()
    tops = data.gear_top_speeds()
    log.ok(
        f"Marchas ({data.drive_type}): "
        + " · ".join(f"{r:.3f} = {v:.0f} km/h" for r, v in zip(ratios, tops))
    )
    log.ok(
        f"Chasis: muelles {units.spring_to_nmm(data.spring_rate(True)):.0f}/"
        f"{units.spring_to_nmm(data.spring_rate(False)):.0f} N/mm · "
        f"ARB {data.arb(True):.0f}/{data.arb(False):.0f} Nm · "
        f"frenos {data.brake_torque:.0f} Nm al {data.brake_bias_percent:.0f}% delante"
    )
    log.info(f"Avisos del diagnostico: {len(data.alerts())}")

    # 3 ------------------------------------------------- ciclo completo en copia
    workdir = Path(tempfile.mkdtemp(prefix="quickmechanic_"))
    try:
        original_engine = sample.data_dir / "engine.ini"
        before_hash = _digest(original_engine)
        before_comments = _comments(original_engine)
        log.info(f"Coche de prueba: {sample.name} ({before_comments} lineas de comentario en engine.ini)")

        copy_dir = workdir / "coche_prueba"
        shutil.copytree(sample.data_dir, copy_dir)
        copy = car_data.CarData(copy_dir, name="coche_prueba", ui_name="Coche de prueba")

        old_limiter = copy.limiter
        copy.limiter = old_limiter + 250
        copy.set_gear(1, copy.gear_ratios()[0] * 0.98)
        copy.set_spring_rate(True, copy.spring_rate(True) * 1.05)
        copy.set_power_scale(1.10)

        base_torque = max(row[-1] for row in copy._power_base or [[0, 0]])  # noqa: SLF001
        saved = copy.save()
        log.ok(f"Guardado en copia: {', '.join(saved)}")

        backup = Path(str(original_engine.name) + ".bak")
        if not (copy_dir / backup).is_file():
            log.fail("No se ha creado la copia .bak")
        else:
            log.ok("Copia de seguridad .bak creada")

        reloaded = car_data.CarData(copy_dir, name="coche_prueba")
        if reloaded.limiter != old_limiter + 250:
            log.fail(f"El limitador no se ha guardado ({reloaded.limiter})")
        else:
            log.ok(f"Limitador guardado y releido: {reloaded.limiter} rpm")
        new_torque = max(row[-1] for row in reloaded.power_lut.rows if reloaded.power_lut)
        if abs(new_torque / base_torque - 1.10) > 0.02:
            log.fail(f"El multiplicador de par no cuadra: {new_torque / base_torque:.3f}")
        else:
            log.ok(f"Multiplicador de par x1.10 aplicado (par maximo {new_torque:.0f} Nm)")

        after_comments = _comments(copy_dir / "engine.ini")
        if after_comments < before_comments:
            log.fail(
                f"Se han perdido comentarios al guardar ({before_comments} -> {after_comments})"
            )
        else:
            log.ok(f"Comentarios intactos tras guardar ({after_comments})")

        if _digest(original_engine) != before_hash:
            log.fail("Se ha modificado el fichero del juego (no deberia pasar)")
        else:
            log.ok("El coche original del juego sigue intacto")

        # 4 ---------------------------------------------------- escala de la curva
        # el multiplicador siempre se aplica sobre la curva que hay en el fichero,
        # asi que al reabrir el coche se puede volver atras sin acumular errores
        stage2 = car_data.CarData(copy_dir)
        stage2.set_power_scale(0.5)
        stage2.save()
        half = car_data.CarData(copy_dir)
        half_torque = max(row[-1] for row in half.power_lut.rows if half.power_lut)
        if abs(half_torque / new_torque - 0.5) > 0.02:
            log.fail(
                "El multiplicador no es reversible (se acumulan escalados)",
                f"esperado {new_torque * 0.5:.1f} Nm, leido {half_torque:.1f} Nm",
            )
        else:
            log.ok(
                "El multiplicador se aplica sobre la curva del fichero, no se acumula "
                f"({half_torque:.0f} Nm = 0.5 x {new_torque:.0f} Nm)"
            )
    except Exception as error:  # noqa: BLE001 (informe de fallos para el usuario)
        log.fail("Error inexperado en el ciclo de edicion", f"{type(error).__name__}: {error}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return _finish(log, report)


def _finish(log: Report, report: str | Path | None) -> int:
    text = log.text()
    if report:
        Path(report).write_text(text, encoding="utf-8")
    try:
        print(text)
    except Exception:  # noqa: BLE001 (el .exe --windowed no tiene consola)
        pass
    return 0 if log.failures == 0 else 1
