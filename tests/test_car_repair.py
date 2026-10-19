"""Tests de diagnostico y reparacion de coches (car_repair).

Cada prueba crea su propio coche temporal, asi no depende de fixtures.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from quickmechanic import car_repair as cr
from quickmechanic.ac_lut import LUTCurve

CAR_INI_OK = "[BASIC]\nNAME=Test\n\n[HEADER]\nVERSION=2\n"
AERO_OK = "[WING_0]\nNAME=Rear\nLUT_AOA_CD=\nLUT_AOA_CL=\n"


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


class _CarMixin(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="qm_repair_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._counter = 0

    def make_car(
        self,
        car_ini: str = CAR_INI_OK,
        aero: str | None = AERO_OK,
        luts: dict[str, str] | None = None,
    ) -> Path:
        self._counter += 1
        car = self.tmp / f"car_{self._counter}"
        data = car / "data"
        data.mkdir(parents=True)
        (data / "car.ini").write_text(car_ini, encoding="utf-8")
        if aero is not None:
            (data / "aero.ini").write_text(aero, encoding="utf-8")
        for name, text in (luts or {}).items():
            (data / name).write_text(text, encoding="utf-8")
        return car

    def read(self, car: Path, name: str) -> str:
        return (car / "data" / name).read_text(encoding="utf-8")

    def backups_in(self, car: Path) -> list[Path]:
        return sorted((car / "data").glob("*.bak"))


class DiagnoseTest(_CarMixin):
    def test_coche_correcto_no_tiene_problemas(self):
        self.assertEqual(cr.diagnose(self.make_car()), [])

    def test_version_invalida_se_detecta(self):
        for value in ("", "abc", "0", "10"):
            with self.subTest(value=value):
                car = self.make_car(car_ini=f"[HEADER]\nVERSION={value}\n")
                issues = cr.diagnose(car)
                self.assertEqual([i.code for i in issues], [cr.CODE_CAR_VERSION])

    def test_version_valida_no_se_marca(self):
        for value in ("1", "9", "extended-1"):
            with self.subTest(value=value):
                car = self.make_car(car_ini=f"[HEADER]\nVERSION={value}\n")
                self.assertEqual(cr.diagnose(car), [])

    def test_seccion_data_obsoleta_en_aero(self):
        car = self.make_car(aero="[DATA]\nX=1\n" + AERO_OK)
        issues = cr.diagnose(car)
        self.assertEqual([i.code for i in issues], [cr.CODE_AERO_DATA])
        self.assertEqual(issues[0].files, ("aero.ini",))

    def test_lut_inexistente_y_vacio_se_detectan(self):
        aero = "[WING_0]\nLUT_AOA_CD=missing.lut\nLUT_AOA_CL=empty.lut\n"
        car = self.make_car(aero=aero, luts={"empty.lut": ""})
        issues = cr.diagnose(car)
        self.assertEqual([i.code for i in issues], [cr.CODE_AERO_LUT])
        self.assertEqual(set(issues[0].files), {"missing.lut", "empty.lut"})

    def test_lut_con_puntos_no_se_marca(self):
        aero = "[WING_0]\nLUT_AOA_CD=ok.lut\n"
        car = self.make_car(aero=aero, luts={"ok.lut": "0|0\n1|1\n"})
        self.assertEqual(cr.diagnose(car), [])

    def test_lut_inline_y_rutas_externas_no_se_tocan(self):
        aero = "[WING_0]\nLUT_AOA_CD=0=0.8|1000=0.9\nLUT_AOA_CL=../evil.lut\n"
        car = self.make_car(aero=aero)
        self.assertEqual(cr.diagnose(car), [])

    def test_diagnose_no_modifica_nada(self):
        aero = "[DATA]\nX=1\n[WING_0]\nLUT_AOA_CD=missing.lut\n"
        car = self.make_car(car_ini="[HEADER]\nVERSION=abc\n", aero=aero)
        before = _snapshot(car)
        self.assertEqual(len(cr.diagnose(car)), 3)  # version, [DATA] y LUT inexistente
        self.assertEqual(_snapshot(car), before)
        self.assertEqual(self.backups_in(car), [])

    def test_codigo_desconocido_lanza_error(self):
        with self.assertRaises(ValueError):
            cr.diagnose(self.make_car(), ["no_existe"])

    def test_carpeta_no_valida_lanza_error(self):
        with self.assertRaises(ValueError):
            cr.diagnose(self.tmp / "nada")
        car = self.tmp / "sin_data"
        car.mkdir()
        with self.assertRaises(ValueError):
            cr.diagnose(car)


class RepairTest(_CarMixin):
    def test_sin_confirmacion_no_toca_nada(self):
        car = self.make_car(car_ini="[HEADER]\nVERSION=abc\n")
        before = _snapshot(car)
        with self.assertRaises(PermissionError):
            cr.repair(car)
        self.assertEqual(_snapshot(car), before)

    def test_repara_version_y_guarda_copia(self):
        car = self.make_car(car_ini="[HEADER]\nVERSION=abc\n")
        result = cr.repair(car, confirmed=True)
        self.assertEqual(result.applied, (cr.CODE_CAR_VERSION,))
        self.assertIn("VERSION=2", self.read(car, "car.ini"))
        self.assertEqual(result.remaining, ())
        backups = self.backups_in(car)
        self.assertEqual(len(backups), 1)
        self.assertIn("VERSION=abc", backups[0].read_text(encoding="utf-8"))

    def test_elimina_data_de_aero_y_conserva_wings(self):
        car = self.make_car(aero="[DATA]\nX=1\n" + AERO_OK)
        cr.repair(car, confirmed=True)
        text = self.read(car, "aero.ini")
        self.assertNotIn("[DATA]", text)
        self.assertIn("[WING_0]", text)
        self.assertEqual(len(self.backups_in(car)), 1)

    def test_crea_luts_con_un_punto(self):
        car = self.make_car(aero="[WING_0]\nLUT_AOA_CD=missing.lut\n")
        result = cr.repair(car, confirmed=True)
        self.assertEqual(result.applied, (cr.CODE_AERO_LUT,))
        lut_path = car / "data" / "missing.lut"
        self.assertEqual(len(LUTCurve(str(lut_path))), 1)
        self.assertEqual(self.backups_in(car), [])  # no existia: nada que copiar

    def test_sustituye_lut_vacio_con_copia(self):
        car = self.make_car(
            aero="[WING_0]\nLUT_AOA_CD=empty.lut\n", luts={"empty.lut": ""}
        )
        cr.repair(car, confirmed=True)
        self.assertEqual(len(LUTCurve(str(car / "data" / "empty.lut"))), 1)
        self.assertEqual(len(self.backups_in(car)), 1)

    def test_segunda_reparacion_no_hace_nada(self):
        car = self.make_car(car_ini="[HEADER]\nVERSION=abc\n", aero="[DATA]\nX=1\n")
        cr.repair(car, confirmed=True)
        before = _snapshot(car)
        again = cr.repair(car, confirmed=True)
        self.assertEqual(again.applied, ())
        self.assertEqual(again.backups, ())
        self.assertEqual(_snapshot(car), before)

    def test_solo_repara_lo_seleccionado(self):
        car = self.make_car(car_ini="[HEADER]\nVERSION=abc\n", aero="[DATA]\nX=1\n")
        result = cr.repair(car, [cr.CODE_CAR_VERSION], confirmed=True)
        self.assertEqual(result.applied, (cr.CODE_CAR_VERSION,))
        self.assertIn("[DATA]", self.read(car, "aero.ini"))
        self.assertEqual([i.code for i in result.remaining], [cr.CODE_AERO_DATA])

    def test_copias_nunca_se_sobrescriben(self):
        car = self.make_car(car_ini="[HEADER]\nVERSION=abc\n")
        path = car / "data" / "car.ini"
        first = cr._backup(path)
        second = cr._backup(path)
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists() and second.exists())

    def test_codigo_desconocido_en_repair_lanza_error(self):
        with self.assertRaises(ValueError):
            cr.repair(self.make_car(), ["no_existe"], confirmed=True)


if __name__ == "__main__":
    unittest.main()
