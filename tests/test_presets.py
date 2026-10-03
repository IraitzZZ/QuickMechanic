"""Pruebas de los perfiles locales de setup."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quickmechanic import presets


class PresetStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="qm_presets_")
        self.addCleanup(self.temp.cleanup)
        self.settings_patch = mock.patch.object(
            presets.settings, "settings_path", return_value=Path(self.temp.name) / "settings.json"
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.snapshot = {
            "version": 1,
            "values": {"car.ini": {"BASIC": {"TOTALMASS": "1000"}}},
            "turbos": [],
            "power_curve": [[1000, 80], [2000, 100]],
        }

    def test_guarda_y_carga_presets_fuera_de_la_carpeta_del_juego(self):
        saved = presets.save_preset("car_test", "GT seco", self.snapshot)
        self.assertEqual(saved.parent.parent.name, "presets")
        self.assertEqual(presets.list_presets("car_test"), ["GT seco"])
        self.assertEqual(presets.load_preset("car_test", "GT seco"), self.snapshot)
        self.assertTrue(presets.delete_preset("car_test", "GT seco"))
        self.assertEqual(presets.list_presets("car_test"), [])

    def test_rechaza_nombres_de_ruta_y_formato_invalido(self):
        with self.assertRaises(ValueError):
            presets.save_preset("../../outside", "setup", self.snapshot)
        with self.assertRaises(ValueError):
            presets.save_preset("car", "setup", {"version": 99})

    def test_exporta_e_importa_json(self):
        target = Path(self.temp.name) / "export.json"
        presets.export_preset(target, self.snapshot)
        self.assertEqual(presets.import_preset(target), self.snapshot)
        target.write_text(json.dumps({"version": 1, "values": []}), encoding="utf-8")
        with self.assertRaises(ValueError):
            presets.import_preset(target)


if __name__ == "__main__":
    unittest.main()
