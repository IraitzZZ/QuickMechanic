"""Pruebas de los módulos portados de AC Car Editor (RTO, ui_car, biblioteca, data.acd)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quickmechanic import acd
from quickmechanic.component_library import ComponentLibrary
from quickmechanic.rto import RTOParser
from quickmechanic.ui_car import UIManager


class RtoTest(unittest.TestCase):
    def test_guardar_y_recargar_mantiene_las_relaciones(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ratios.rto"
            parser = RTOParser(str(path))
            parser.load()
            parser.set_ratios([3.5, 2.1, 1.4])
            parser.save(backup=False)
            reloaded = RTOParser(str(path))
            reloaded.load()
            self.assertEqual(reloaded.get_ratios(), [3.5, 2.1, 1.4])

    def test_ordenar_y_anadir_relaciones(self):
        with tempfile.TemporaryDirectory() as tmp:
            parser = RTOParser(str(Path(tmp) / "ratios.rto"))
            parser.load()
            parser.set_ratios([1.0, 3.0])
            parser.add_ratio(2.0)
            parser.sort_ratios(reverse=True)
            self.assertEqual(parser.get_ratios(), [3.0, 2.0, 1.0])


class UiCarTest(unittest.TestCase):
    def test_ficha_se_guarda_y_se_recarga(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = UIManager(tmp)
            manager.create_default_ui_car_json("prueba")
            manager.set_name("Nombre nuevo")
            manager.set_year(1999)
            self.assertTrue(manager.save(backup=False))
            reloaded = UIManager(tmp)
            self.assertTrue(reloaded.load())
            self.assertEqual(reloaded.get_name(), "Nombre nuevo")
            self.assertEqual(reloaded.get_year(), 1999)


class ComponentLibraryTest(unittest.TestCase):
    def test_anadir_buscar_y_borrar_componente(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = ComponentLibrary(str(Path(tmp) / "library.json"))
            component = {"id": "test_motor", "name": "Motor de prueba", "tags": ["test"]}
            self.assertTrue(library.add_component("engine", component))
            self.assertIsNotNone(library.get_component("engine", "test_motor"))
            self.assertTrue(library.delete_component("engine", "test_motor"))
            self.assertIsNone(library.get_component("engine", "test_motor"))


class AcdTest(unittest.TestCase):
    def test_necesita_desempaquetar_solo_si_hay_acd_sin_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            car = Path(tmp)
            self.assertFalse(acd.needs_unpack(car))
            (car / "data.acd").write_bytes(b"x")
            self.assertTrue(acd.needs_unpack(car))
            (car / "data").mkdir()
            self.assertFalse(acd.needs_unpack(car))

    def test_disable_acd_renombra_a_bak_sin_borrar(self):
        with tempfile.TemporaryDirectory() as tmp:
            car = Path(tmp)
            (car / "data.acd").write_bytes(b"original")
            self.assertTrue(acd.disable_acd(car))
            self.assertFalse((car / "data.acd").exists())
            self.assertEqual((car / "data.acd.bak").read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
