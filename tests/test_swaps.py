"""Tests de los intercambios seguros entre coches Assetto Corsa."""
from __future__ import annotations

import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from quickmechanic import swaps
from tests.support import TEST_CAR_DATA


class SwapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qm_swap_"))
        self.donor = self.tmp / "donor"
        self.target = self.tmp / "target"
        (self.donor / "data").mkdir(parents=True)
        (self.target / "data").mkdir(parents=True)
        shutil.copytree(TEST_CAR_DATA, self.donor / "data", dirs_exist_ok=True)
        shutil.copytree(TEST_CAR_DATA, self.target / "data", dirs_exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def read(self, car: Path, name: str) -> str:
        return (car / "data" / name).read_text(encoding="utf-8")

    def test_motor_rechaza_limitador_superior_a_curva(self) -> None:
        engine_path = self.donor / "data" / "engine.ini"
        engine_path.write_text(self.read(self.donor, "engine.ini").replace("LIMITER=6500", "LIMITER=7200"), encoding="utf-8")
        with self.assertRaisesRegex(swaps.SwapError, "último punto de la curva"):
            swaps.prepare_swap("motor", self.donor, self.target)

    def test_intercambio_motor_respalda_destino_y_no_toca_donante(self) -> None:
        donor_engine = self.read(self.donor, "engine.ini").replace("LIMITER=6500", "LIMITER=6800")
        (self.donor / "data" / "engine.ini").write_text(donor_engine, encoding="utf-8")
        target_engine = self.read(self.target, "engine.ini").replace("LIMITER=6500", "LIMITER=6100")
        (self.target / "data" / "engine.ini").write_text(target_engine, encoding="utf-8")
        plan = swaps.prepare_swap("motor", self.donor, self.target)
        self.assertEqual(plan.kind, "motor")
        self.assertIn("data/power.lut", plan.files)
        self.assertIn("LIMITER=6100", self.read(self.target, "engine.ini"))

        archive = swaps.apply_swap(plan)

        self.assertTrue(archive.is_file())
        self.assertIn("LIMITER=6800", self.read(self.target, "engine.ini"))
        self.assertEqual(donor_engine, self.read(self.donor, "engine.ini"))
        self.assertIn("RPM_THRESHOLD=6700", self.read(self.target, "engine.ini"))
        with zipfile.ZipFile(archive) as zipped:
            self.assertIn("data/engine.ini", zipped.namelist())
            self.assertIn("LIMITER=6100", zipped.read("data/engine.ini").decode("utf-8"))
        self.assertTrue((self.target / "data" / "engine.ini.bak").is_file())

    def test_plan_de_swap_no_escribe_hasta_aplicar(self) -> None:
        donor = (self.donor / "data" / "drivetrain.ini").read_bytes()
        target = (self.target / "data" / "drivetrain.ini").read_bytes()
        plan = swaps.prepare_swap("transmisión", self.donor, self.target)
        self.assertNotEqual(plan.ini_updates, {})
        self.assertEqual((self.donor / "data" / "drivetrain.ini").read_bytes(), donor)
        self.assertEqual((self.target / "data" / "drivetrain.ini").read_bytes(), target)

    def test_intercambio_caja_rechaza_cambio_de_traccion(self) -> None:
        path = self.target / "data" / "drivetrain.ini"
        path.write_text(self.read(self.target, "drivetrain.ini").replace("TYPE=RWD", "TYPE=FWD"), encoding="utf-8")
        with self.assertRaisesRegex(swaps.SwapError, "Tracción incompatible"):
            swaps.prepare_swap("transmisión", self.donor, self.target)

    def test_intercambio_caja_copia_relaciones_pero_no_cambia_traccion(self) -> None:
        donor_path = self.donor / "data" / "drivetrain.ini"
        donor_path.write_text(self.read(self.donor, "drivetrain.ini").replace("GEAR_2=2.158", "GEAR_2=2.300"), encoding="utf-8")
        plan = swaps.prepare_swap("transmisión", self.donor, self.target)
        archive = swaps.apply_swap(plan)
        result = self.read(self.target, "drivetrain.ini")
        self.assertIn("GEAR_2=2.3", result)
        self.assertIn("TYPE=RWD", result)
        self.assertTrue(archive.is_file())
        self.assertTrue((self.target / "data" / "drivetrain.ini.bak").is_file())

    def test_fitment_copia_geometria_y_conserva_muelles_destino(self) -> None:
        donor_path = self.donor / "data" / "suspensions.ini"
        donor_path.write_text(self.read(self.donor, "suspensions.ini").replace("STATIC_CAMBER=-3.0", "STATIC_CAMBER=-5.5"), encoding="utf-8")
        target_path = self.target / "data" / "suspensions.ini"
        target_path.write_text(self.read(self.target, "suspensions.ini").replace("SPRING_RATE=90000", "SPRING_RATE=100000"), encoding="utf-8")
        plan = swaps.prepare_swap("fitment", self.donor, self.target)
        swaps.apply_swap(plan)
        result = self.read(self.target, "suspensions.ini")
        self.assertIn("STATIC_CAMBER=-5.5", result)
        self.assertIn("SPRING_RATE=100000", result)

    def test_intercambio_sonido_copia_solo_bancos_referenciados_y_guids(self) -> None:
        donor_sfx = self.donor / "sfx"
        donor_sfx.mkdir()
        (self.donor / "sfx.ini").write_text(
            "[SOUNDBANK_0]\nBANK=sfx/test.bank\nGUIDS=sfx/GUIDs.txt\n", encoding="utf-8"
        )
        (donor_sfx / "test.bank").write_bytes(b"donor-bank")
        (donor_sfx / "GUIDs.txt").write_text("{123} event:/cars/test/engine", encoding="utf-8")
        (self.target / "sfx").mkdir()
        (self.target / "sfx" / "old.bank").write_bytes(b"keep this")
        (self.target / "target.bank").write_bytes(b"existing target bank")

        plan = swaps.prepare_swap("sonido", self.donor, self.target)
        archive = swaps.apply_swap(plan)

        self.assertEqual((self.target / "sfx" / "test.bank").read_bytes(), b"donor-bank")
        self.assertTrue((self.target / "sfx" / "GUIDs.txt").is_file())
        self.assertTrue((self.target / "sfx" / "old.bank").is_file())
        self.assertTrue((self.target / "sfx.ini").is_file())
        self.assertTrue(archive.is_file())
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(zipped.read("target.bank"), b"existing target bank")

    def test_sonido_rechaza_bank_que_sale_de_sfx(self) -> None:
        (self.donor / "sfx.ini").write_text(
            "[SOUNDBANK_0]\nBANK=../outside.bank\nGUIDS=sfx/GUIDs.txt\n", encoding="utf-8"
        )
        with self.assertRaises(swaps.SwapError):
            swaps.prepare_swap("sonido", self.donor, self.target)

    def test_respaldo_de_sonido_incluye_sfx_destino(self) -> None:
        sfx_dir = self.target / "sfx"
        sfx_dir.mkdir()
        bank = sfx_dir / "target.bank"
        bank.write_bytes(b"existing target sounds")
        root_bank = self.target / "old.bank"
        root_bank.write_bytes(b"existing root bank")
        archive = swaps.create_backup(self.target, ("sfx.ini", "sfx/target.bank"))
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(zipped.read("sfx/target.bank"), b"existing target sounds")
            self.assertEqual(zipped.read("old.bank"), b"existing root bank")
        root_bank.write_bytes(b"overwritten")
        swaps.restore_backup(self.target, archive)
        self.assertEqual(root_bank.read_bytes(), b"existing root bank")

    def test_respaldo_incluye_data_acd_sin_modificarlo(self) -> None:
        acd = self.target / "data.acd"
        acd.write_bytes(b"proprietary data archive")
        archive = swaps.create_backup(self.target)
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(zipped.read("data.acd"), b"proprietary data archive")
        self.assertEqual(acd.read_bytes(), b"proprietary data archive")

    def test_restaurar_solo_rutas_permitidas_y_crea_backup_seguimiento(self) -> None:
        original = swaps.create_backup(self.target)
        (self.target / "data" / "engine.ini").write_text("[BROKEN]\\n", encoding="utf-8")
        safety = swaps.restore_backup(self.target, original)
        self.assertTrue(safety.is_file())
        self.assertEqual(self.read(self.target, "engine.ini"), self.read(self.donor, "engine.ini"))
        self.assertEqual(swaps.restore_backup(self.target, safety).is_file(), True)

        hostile = self.target / "quickmechanic_backups" / "hostile.zip"
        with zipfile.ZipFile(hostile, "w") as zipped:
            zipped.writestr("../../outside.txt", "no")
        with self.assertRaises(swaps.SwapError):
            swaps.restore_backup(self.target, hostile)
        with zipfile.ZipFile(hostile, "w") as zipped:
            zipped.writestr("data/engine.ini", "[MALICIOUS]\\n")
            zipped.writestr("data/evil.exe", "executable payload")
        with self.assertRaisesRegex(swaps.SwapError, "Extensión no permitida"):
            swaps.restore_backup(self.target, hostile)
        self.assertNotIn("MALICIOUS", self.read(self.target, "engine.ini"))
        self.assertFalse((self.tmp.parent / "outside.txt").exists())

    def test_swap_mismo_coche_se_rechaza(self) -> None:
        with self.assertRaisesRegex(swaps.SwapError, "distintos"):
            swaps.prepare_swap("motor", self.donor, self.donor)


if __name__ == "__main__":
    unittest.main()
