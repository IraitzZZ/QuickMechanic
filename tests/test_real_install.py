"""Tests contra la instalacion real de Assetto Corsa.

Solo leen: el unico test que escribe lo hace sobre una copia temporal de la
carpeta data de un coche, nunca sobre el fichero del juego.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from quickmechanic import ac_scanner, car_data

AC_ROOT = ac_scanner.find_ac_root()

try:  # las pruebas de interfaz necesitan Qt, en modo sin pantalla
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from quickmechanic.tabs import AdvancedTab, ChassisTab, GearboxTab, MotorTab

    GUI = True
except Exception:  # pragma: no cover
    GUI = False


@unittest.skipIf(AC_ROOT is None, "Assetto Corsa no esta instalado")
class RealInstallTest(unittest.TestCase):
    def test_escaner(self):
        cars = ac_scanner.list_cars(AC_ROOT)
        self.assertGreater(len(cars), 0)
        editable = [car for car in cars if car.editable]
        self.assertGreater(len(editable), 0, "no hay ningun coche con carpeta data/")
        for car in cars[:5]:
            self.assertIn(car.status, ("editable", "data.acd", "sin datos"))
            self.assertTrue(car.folder.is_dir())

    def test_lectura_de_coches_reales(self):
        editable = [car for car in ac_scanner.list_cars(AC_ROOT) if car.editable]
        problems = []
        checked = 0
        for car in editable[:5]:
            data = car_data.CarData.from_car(car)
            checked += 1
            if data.limiter <= 0:
                problems.append(f"{car.name}: sin LIMITER")
            if not data.power_points(scaled=False):
                problems.append(f"{car.name}: sin curva de potencia ({data.power_curve_file})")
            if data.gear_count < 1:
                problems.append(f"{car.name}: sin marchas")
            if data.mass <= 0:
                problems.append(f"{car.name}: sin masa")
            if data.gear_count >= 2:
                speeds = data.gear_top_speeds()
                if speeds != sorted(speeds):
                    problems.append(f"{car.name}: velocidades por marcha no ordenadas")
            if data.changed:
                problems.append(f"{car.name}: leer el coche lo ha marcado como modificado")
            self.assertTrue(data.summary())
        self.assertEqual(checked, min(5, len(editable)))
        self.assertEqual(problems, [])

    def test_edicion_sobre_una_copia_real(self):
        editable = [car for car in ac_scanner.list_cars(AC_ROOT) if car.editable]
        source = editable[0]
        engine = source.data_dir / "engine.ini"
        before = engine.read_bytes()
        before_comments = _comments(engine)

        workdir = Path(tempfile.mkdtemp(prefix="qm_real_"))
        self.addCleanup(shutil.rmtree, workdir, ignore_errors=True)
        copy_dir = workdir / "data"
        shutil.copytree(source.data_dir, copy_dir)

        copy = car_data.CarData(copy_dir, name=source.name)
        old_limiter = copy.limiter
        copy.limiter = old_limiter + 100
        copy.set_gear(1, copy.gear_ratios()[0] * 0.99)
        copy.set_power_scale(1.05)
        self.assertTrue(copy.save())

        reloaded = car_data.CarData(copy_dir, name=source.name)
        self.assertEqual(reloaded.limiter, old_limiter + 100)
        self.assertGreaterEqual(_comments(copy_dir / "engine.ini"), before_comments)
        self.assertEqual(engine.read_bytes(), before, "el fichero del juego se ha modificado")
        self.assertTrue((copy_dir / "engine.ini.bak").is_file())


@unittest.skipIf(AC_ROOT is None, "Assetto Corsa no esta instalado")
@unittest.skipUnless(GUI, "PyQt6 no esta disponible")
class RealCarsTabsTest(unittest.TestCase):
    """Abre las pestanas con coches reales: asi salen los formatos y unidades raras."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_las_pestanas_abren_coches_reales(self):
        cars = [car for car in ac_scanner.list_cars(AC_ROOT) if car.editable][:25]
        self.assertTrue(cars)
        failures = []
        for car in cars:
            data = car_data.CarData.from_car(car)
            tabs = (MotorTab(), GearboxTab(), ChassisTab(), AdvancedTab())
            for tab in tabs:
                try:
                    tab.load(data)
                except Exception as error:  # noqa: BLE001
                    failures.append(f"{car.name} / {type(tab).__name__}: {error}")
            if data.changed:
                failures.append(f"{car.name}: abrir la pestana ha marcado cambios")
            for tab in tabs:
                tab.deleteLater()
        self.assertEqual(failures, [])


def _comments(path: Path) -> int:
    """Lineas con comentario, contando tambien los que van al final de la linea."""
    return sum(
        1
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ";" in line or line.strip().startswith(("#", "//"))
    )


if __name__ == "__main__":
    unittest.main()
