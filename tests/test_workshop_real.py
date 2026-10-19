"""Prueba real del Taller contra un coche de verdad de Assetto Corsa.

Se salta solo si no hay instalacion de AC. **Nunca escribe en el coche real**:
copia su carpeta ``data/`` a temporal y trabaja ahi, que es justo el camino que
sigue el usuario cuando edita y guarda.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from quickmechanic import ac_scanner, analysis, car_data, garage


def _real_car() -> ac_scanner.Car | None:
    root = ac_scanner.find_ac_root([])
    if root is None:
        return None
    for car in ac_scanner.list_cars(root):
        if car.editable:
            return car
    return None


class RealCarWorkshopTest(unittest.TestCase):
    """Recorre el Taller completo sobre un coche real, en una copia temporal."""

    car_info: ac_scanner.Car | None = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.car_info = _real_car()
        if cls.car_info is None:
            raise unittest.SkipTest("no hay instalacion de Assetto Corsa con coches editables")

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qm_real_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        source = self.car_info.folder / "data"
        self.data_dir = self.tmp / "data"
        shutil.copytree(source, self.data_dir)
        self.car = car_data.CarData(self.data_dir, name=self.car_info.name, ui_name=self.car_info.ui_name)
        self.addCleanup(lambda: setattr(self, "car", None))

    # -------------------------------------------------------------- lectura
    def test_se_lee_el_coche_y_se_calculan_prestaciones(self) -> None:
        self.assertTrue(self.car.editable)
        estimate = analysis.estimate_performance(self.car)
        self.assertIsNotNone(estimate, "el coche real no da estimacion de prestaciones")
        assert estimate is not None
        self.assertGreater(estimate.power_hp, 20)
        self.assertGreater(estimate.top_speed_kmh, 60)
        gears = analysis.gear_speeds(self.car)
        self.assertTrue(gears, "sin velocidades por marcha")
        self.assertEqual(gears, sorted(gears, key=lambda gear: gear.shift_kmh))

    def test_diagnostico_e_inspector_no_modifican_nada(self) -> None:
        before = {name: (self.data_dir / name).read_bytes() for name in self.car.dirty_files()}
        findings = analysis.diagnostics(self.car, analysis.estimate_performance(self.car))
        self.assertTrue(findings)
        self.assertTrue(all(finding.icon for finding in findings))
        rows = []
        for filename in ("engine.ini", "drivetrain.ini", "suspensions.ini", "tyres.ini", "brakes.ini", "car.ini"):
            if not self.car.has_file(filename):
                continue
            ini = self.car.ini(filename)
            for section in ini.sections():
                for key in ini.keys(section):
                    rows.append((filename, section, key, ini.get(section, key)))
        self.assertGreater(len(rows), 20, "el inspector deberia ver claves del coche real")
        self.assertFalse(self.car.changed)
        after = {name: (self.data_dir / name).read_bytes() for name in before}
        self.assertEqual(before, after, "leer el coche no puede tocar los .ini")

    # --------------------------------------------------------------- edicion
    def test_editar_curva_gearing_y_presets_y_guardar(self) -> None:
        files = [name for name in car_data.PHYSICS_FILES if self.car.has_file(name)]
        comentarios = {
            name: sum(1 for line in (self.data_dir / name).read_text(encoding="utf-8", errors="replace").splitlines()
                      if ";" in line or line.strip().startswith(("#", "//")))
            for name in files
        }
        puntos = self.car.power_points()
        self.assertGreater(len(puntos), 3)
        self.assertTrue(self.car.set_power_point(1, puntos[1][1] * 1.05))

        plan = analysis.optimal_gearing(self.car, 260.0)
        self.assertIsNotNone(plan, "sin plan de gearing para el coche real")
        assert plan is not None
        self.assertGreaterEqual(analysis.apply_gearing(self.car, plan), 2)

        for style in ("street", "track", "gt3", "drag", "rally"):
            with self.subTest(style=style):
                analysis.apply_style(self.car, style)

        self.assertTrue(self.car.changed)
        guardados = self.car.save()
        self.assertTrue(guardados)
        # Los comentarios del .ini original siguen ahi: no se reescribe el fichero entero.
        for name, total in comentarios.items():
            if not total or name not in guardados:
                continue
            ahora = sum(1 for line in (self.data_dir / name).read_text(encoding="utf-8", errors="replace").splitlines()
                        if ";" in line or line.strip().startswith(("#", "//")))
            self.assertEqual(ahora, total, f"se perdieron comentarios en {name}")
        self.assertFalse(self.car.changed)

    def test_guardar_crea_respaldo_y_deja_restaurar_un_fichero(self) -> None:
        self.car.set_power_point(1, self.car.power_points()[1][1] * 1.1)
        self.car.save()
        backups = garage.list_backups(self.tmp)
        self.assertTrue(backups, "guardar tiene que dejar un respaldo ZIP")
        backup = backups[0]
        self.assertTrue(backup.data_members, "el respaldo deberia contener data/")
        member = next(name for name in backup.members if name.startswith("data/"))
        objetivo = self.data_dir / Path(member).name
        antes = objetivo.read_bytes()
        objetivo.write_bytes(b"basura")
        restaurado = garage.restore_member(backup.path, member, self.tmp)
        self.assertEqual(restaurado, objetivo)
        self.assertEqual(restaurado.read_bytes(), antes)
        self.assertGreaterEqual(len(garage.list_backups(self.tmp)), 2, "restaurar debe crear otro respaldo")

    def test_setups_versiones_e_historial_en_la_copia(self) -> None:
        with mock.patch("quickmechanic.garage.root_dir", return_value=self.tmp / "perfil"):
            snapshot = self.car.setup_snapshot()
            garage.save_setup(self.car.name, "Monza seco", snapshot, circuit="Monza", conditions="seco")
            info = garage.list_setups(self.car.name)
            self.assertEqual(len(info), 1)
            self.assertEqual(info[0].circuit, "Monza")
            exportado = self.tmp / "compartido.qmsetup"
            garage.export_setup(self.car.name, "Monza seco", exportado)
            self.assertTrue(exportado.is_file())
            _nombre, importado = garage.import_setup(exportado)
            self.assertEqual(importado["values"], snapshot["values"])

            import json as _json
            manipulado = _json.loads(exportado.read_text(encoding="utf-8"))
            manipulado["name"] = "Otro nombre"
            exportado.write_text(_json.dumps(manipulado), encoding="utf-8")
            with self.assertRaises(garage.GarageError):
                garage.import_setup(exportado)

            garage.save_version(self.car.name, "antes del cambio", snapshot)
            self.assertEqual(len(garage.list_versions(self.car.name)), 1)
            self.car.set_power_point(2, self.car.power_points()[2][1] * 1.2)
            garage.record_changes(self.car.name, garage.changes_between(snapshot, self.car.setup_snapshot()))
            historial = garage.read_history(self.car.name)
            self.assertTrue(historial)
            self.assertTrue(any(change.before != change.after for change in historial))

            self.car.restore_setup(garage.load_version(self.car.name, garage.list_versions(self.car.name)[0].version_id))
            self.assertEqual(self.car.power_points()[2][1], snapshot["power_curve"][2][-1])

    def test_informe_del_coche_real(self) -> None:
        texto = analysis.report(self.car, analysis.estimate_performance(self.car))
        self.assertIn(self.car.ui_name, texto)
        self.assertIn("Velocidad punta", texto)
        html = analysis.report(self.car, analysis.estimate_performance(self.car), fmt="html")
        self.assertIn("<!DOCTYPE html>", html)

    def test_clonado_no_toca_el_original(self) -> None:
        cars_root = self.tmp / "cars"
        original = cars_root / "coche_real"
        (original / "data").mkdir(parents=True)
        for name in ("engine.ini", "car.ini", "tyres.ini"):
            if (self.car_info.folder / "data" / name).is_file():
                shutil.copy2(self.car_info.folder / "data" / name, original / "data" / name)
        (original / "ui").mkdir()
        (original / "ui" / "ui_car.json").write_text("{}", encoding="utf-8")
        sugerido = garage.suggest_clone_name(original, cars_root)
        self.assertTrue(sugerido.startswith("coche_real"), sugerido)
        resultado = garage.clone_car(original, cars_root)
        self.assertEqual(resultado.name, sugerido)
        self.assertTrue((resultado.folder / "data").is_dir())
        self.assertEqual(
            len(list(resultado.folder.rglob("*"))), len(list(original.rglob("*"))),
            "el clon deberia tener los mismos ficheros que el original",
        )
        # Un segundo clon no pisa el primero y recibe otro nombre.
        segundo = garage.clone_car(original, cars_root)
        self.assertNotEqual(segundo.name, resultado.name)
        # Un nombre vacio significa "ponme uno tu"; lo que no vale es pisar otro coche
        # ni intentar salirse de content/cars.
        for nombre in (resultado.name, "../fuera", "  "):
            with self.subTest(nombre=nombre):
                with self.assertRaises(garage.GarageError):
                    garage.clone_car(original, cars_root, nombre)
        self.assertTrue((original / "data").is_dir(), "el original sigue intacto")


if __name__ == "__main__":
    unittest.main()
