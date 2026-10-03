"""Tests de la capa de datos del coche (lectura, edicion y guardado)."""
from __future__ import annotations

import unittest

from quickmechanic import car_data, units
from tests.support import TempCarMixin


class CarDataReadTest(TempCarMixin):
    def setUp(self) -> None:
        super().setUp()
        self.car = car_data.CarData(self.data_dir, name="ks_test_car", ui_name="Coche de prueba")

    def test_motor(self):
        self.assertEqual(self.car.limiter, 6500)
        self.assertEqual(self.car.idle_rpm, 1250)
        self.assertAlmostEqual(self.car.engine_inertia, 0.120, places=3)
        self.assertTrue(self.car.has_turbo)
        turbo = self.car.turbos()[0]
        self.assertAlmostEqual(turbo.max_boost, 1.38, places=2)
        self.assertAlmostEqual(turbo.wastegate, 1.10, places=2)
        self.assertFalse(turbo.cockpit_adjustable)
        self.assertAlmostEqual(self.car.damage["turbo_threshold"], 1.40, places=2)

    def test_curva_de_potencia(self):
        self.assertEqual(self.car.power_curve_file, "power.lut")
        self.assertIsNotNone(self.car.power_lut)
        rpm_torque, torque = self.car.peak_torque()
        self.assertEqual((rpm_torque, torque), (3250, 130))
        rpm_hp, hp = self.car.peak_power()
        self.assertAlmostEqual(hp, units.hp_from_torque(94, 5750), places=3)
        self.assertEqual(rpm_hp, 5750)

    def test_transmision(self):
        self.assertEqual(self.car.drive_type, "RWD")
        self.assertEqual(self.car.gear_count, 6)
        self.assertEqual(self.car.gear_ratios()[0], 3.818)
        self.assertEqual(self.car.gear_ratios()[-1], 0.744)
        self.assertEqual(self.car.final_drive, 4.176)
        self.assertEqual(self.car.reverse_ratio, -3.5)
        power, coast, preload = self.car.differential
        self.assertAlmostEqual(power, 0.30, places=3)
        self.assertAlmostEqual(coast, 0.45, places=3)
        self.assertEqual(preload, 10)
        self.assertEqual(self.car.clutch_max_torque, 450)

    def test_velocidades_por_marcha(self):
        speeds = self.car.gear_top_speeds()
        self.assertEqual(len(speeds), 6)
        self.assertEqual(speeds, sorted(speeds))
        self.assertAlmostEqual(speeds[0], 48.4, delta=1.0)
        self.assertAlmostEqual(speeds[-1], 248.5, delta=2.0)

    def test_neumaticos(self):
        self.assertAlmostEqual(self.car.wheel_radius(True), 0.305, places=3)
        self.assertAlmostEqual(self.car.wheel_radius(False), 0.315, places=3)
        self.assertAlmostEqual(self.car.driven_wheel_radius(), 0.315, places=3)
        compounds = self.car.compounds()
        self.assertEqual(len(compounds), 2)
        self.assertEqual(compounds[0][0], "Slicks")
        self.assertEqual(compounds[0][1], 17)

    def test_chasis_y_frenos(self):
        self.assertEqual(self.car.spring_rate(True), 90000)
        self.assertAlmostEqual(units.spring_to_nmm(self.car.spring_rate(True)), 90.0, places=3)
        self.assertEqual(self.car.damper(True, False), 5400)
        self.assertEqual(self.car.damper(False, True), 6200)
        self.assertEqual(self.car.arb(True), 52500)
        self.assertEqual(self.car.arb(False), 17500)
        self.assertEqual(self.car.brake_torque, 2400)
        self.assertAlmostEqual(self.car.brake_bias_percent, 75.0, places=3)
        self.assertEqual(self.car.mass, 1050)
        self.assertEqual(self.car.max_fuel, 35)
        self.assertAlmostEqual(self.car.cg_front_percent, 68.0, places=3)

    def test_rangos_del_setup(self):
        self.assertIsNone(self.car.setup_range("SPRING_RATE_LF"))
        self.assertEqual(self.car.setup_range("PRESSURE_LF"), (15.0, 40.0, 1.0))

    def test_gearset(self):
        self.assertTrue(self.car.has_gearset)
        self.assertEqual(self.car.ratios_rto.count, 6)
        self.assertEqual(self.car.final_rto.count, 3)

    def test_resumen_y_diagnostico(self):
        labels = [label for label, _value in self.car.summary()]
        self.assertIn("Potencia maxima", labels)
        self.assertIn("Velocidad teorica max.", labels)
        alerts = self.car.alerts()
        self.assertTrue(alerts)
        self.assertTrue(all(level in ("info", "aviso", "peligro") for level, _ in alerts))
        # el cohe con boost 1.38 y umbral 1.40 no debe avisar de dano
        self.assertFalse(any(level == "peligro" for level, _ in alerts))


class CarDataWriteTest(TempCarMixin):
    def setUp(self) -> None:
        super().setUp()
        self.car = car_data.CarData(self.data_dir, name="ks_test_car", ui_name="Coche de prueba")

    def test_editar_guardar_y_releer(self):
        self.car.limiter = 7000
        self.car.set_gear(1, 4.0)
        self.car.set_spring_rate(False, 100000)
        self.car.set_differential(0.5, 0.2, 30)
        self.car.brake_bias_percent = 70
        self.car.mass = 1000

        pending = self.car.dirty_files()
        self.assertIn("engine.ini", pending)
        self.assertIn("drivetrain.ini", pending)
        self.assertIn("suspensions.ini", pending)
        self.assertIn("brakes.ini", pending)
        self.assertIn("car.ini", pending)

        saved = self.car.save()
        self.assertEqual(len(saved), 5)
        self.assertFalse(self.car.changed)

        reloaded = car_data.CarData(self.data_dir, name="ks_test_car")
        self.assertEqual(reloaded.limiter, 7000)
        self.assertEqual(reloaded.gear_ratios()[0], 4.0)
        self.assertAlmostEqual(reloaded.spring_rate(False), 100000, places=1)
        self.assertAlmostEqual(reloaded.differential[0], 0.5, places=3)
        self.assertAlmostEqual(reloaded.differential[2], 30, places=3)
        self.assertAlmostEqual(reloaded.brake_bias_percent, 70, places=2)
        self.assertEqual(reloaded.mass, 1000)

    def test_guardado_crea_respaldo_zip_completo_antes_de_escribir(self):
        import zipfile
        from pathlib import Path
        backup_dir = Path(self.car.folder) / "quickmechanic_backups"
        self.car.limiter = 7200
        saved = self.car.save()
        self.assertIn("engine.ini", saved)
        backups = list(backup_dir.glob("data_backup_*.zip"))
        self.assertEqual(len(backups), 1)
        with zipfile.ZipFile(backups[0]) as archive:
            self.assertIn("data/engine.ini", archive.namelist())
            self.assertIn("LIMITER=6500", archive.read("data/engine.ini").decode("utf-8"))

    def test_guardado_no_rompe_los_comentarios(self):
        before = {
            name: self.comments_in(name)
            for name in ("engine.ini", "drivetrain.ini", "suspensions.ini", "car.ini")
        }
        self.car.limiter = 7000
        self.car.set_gear(2, 2.0)
        self.car.set_spring_rate(True, 95000)
        self.car.mass = 1100
        self.car.save()
        for name, count in before.items():
            self.assertGreaterEqual(self.comments_in(name), count, name)

    def test_multiplicador_de_par_no_se_acumula(self):
        self.car.set_power_scale(1.5)
        self.car.set_power_scale(0.5)
        self.car.save()
        reloaded = car_data.CarData(self.data_dir, name="ks_test_car")
        self.assertAlmostEqual(reloaded.peak_torque()[1], 65.0, places=3)

    def test_escalado_sin_guardar_no_toca_el_fichero(self):
        self.car.set_power_scale(2.0)
        self.assertTrue(self.car.power_scale_applied)
        self.assertIn("power.lut", self.car.dirty_files())
        # el fichero sigue como estaba
        self.assertIn("3250|130", self.read("power.lut"))

    def test_anadir_y_quitar_turbo(self):
        self.car.remove_turbo()
        self.assertFalse(self.car.has_turbo)
        self.car.save()

        reloaded = car_data.CarData(self.data_dir, name="ks_test_car")
        self.assertFalse(reloaded.has_turbo)

        section = reloaded.add_turbo()
        self.assertEqual(section, "TURBO_0")
        self.assertTrue(reloaded.has_turbo)
        self.assertAlmostEqual(reloaded.turbos()[0].max_boost, 1.0, places=3)
        reloaded.save()

        final = car_data.CarData(self.data_dir, name="ks_test_car")
        self.assertTrue(final.has_turbo)
        self.assertTrue(final.turbo_sections == ["TURBO_0"])

    def test_presiones_delanteras_traseras(self):
        self.assertAlmostEqual(self.car.tyre_pressure(True), 17.0)
        self.assertAlmostEqual(self.car.tyre_pressure(False), 17.0)
        self.car.set_tyre_pressure(False, 19.5)
        self.assertAlmostEqual(self.car.tyre_pressure(False), 19.5)
        self.assertTrue(self.car.changed)

    def test_asistencias_solo_edita_secciones_declaradas(self):
        self.assertTrue(self.car.driver_aids()["ABS"]["available"])
        self.assertFalse(self.car.driver_aids()["TC"]["active"])
        self.assertTrue(self.car.set_driver_aid("TC", active=True))
        self.assertTrue(self.car.driver_aids()["TC"]["active"])
        self.assertTrue(self.car.set_driver_aid("ABS", present=False))
        self.assertFalse(self.car.driver_aids()["ABS"]["active"])
        self.assertFalse(self.car.set_driver_aid("UNKNOWN", active=True))
        self.assertIn("electronics.ini", self.car.dirty_files())

    def test_snapshot_incluye_y_restaura_asistencias(self):
        original = self.car.setup_snapshot()
        self.car.set_driver_aid("TC", active=True)
        self.car.restore_setup(original)
        self.assertFalse(self.car.driver_aids()["TC"]["active"])
        self.assertFalse(self.car.changed)
        advanced = dict(original)
        advanced["advanced"] = {"engine.ini": {"DAMAGE": {"RPM_THRESHOLD": "not-a-number"}}}
        with self.assertRaises(ValueError):
            self.car.restore_setup(advanced)

    def test_alerta_de_dano_por_boost(self):
        self.car.set_turbo(0, MAX_BOOST=1.9)
        levels = [level for level, _text in self.car.alerts()]
        self.assertIn("peligro", levels)

    def test_editor_avanzado_solo_cambia_parametros_numericos_existentes(self):
        settings = self.car.advanced_settings()
        identities = {setting.identity for setting in settings}
        self.assertIn(("ENGINE.INI", "DAMAGE", "RPM_THRESHOLD"), identities)
        self.assertIn(("CAR.INI", "CONTROLS", "FFMULT"), identities)
        self.assertFalse(self.car.set_advanced_value("car.ini", "UNKNOWN", "KEY", 1.0))
        self.assertTrue(self.car.set_advanced_value("suspensions.ini", "FRONT", "DAMP_FAST_BUMP", 2000))
        self.assertEqual(self.car.ini("suspensions.ini").get_float("FRONT", "DAMP_FAST_BUMP"), 2000)
        self.assertTrue(self.car.changed)

    def test_preset_drift_aplica_solo_campos_presentes_y_no_guarda(self):
        original = self.read("drivetrain.ini")
        result = self.car.apply_drift_preset()
        self.assertGreater(result.changed_count, 0)
        self.assertTrue(self.car.changed)
        self.assertIn("drivetrain.ini", self.car.dirty_files())
        self.assertAlmostEqual(self.car.ini("drivetrain.ini").get_float("GEARS", "FINAL"), 4.176 * 1.05)
        self.assertEqual(self.read("drivetrain.ini"), original)

    def test_preset_drift_rechaza_fwd_y_limita_campos_ausentes(self):
        drivetrain = self.car.ini("drivetrain.ini")
        drivetrain.set_value("TRACTION", "TYPE", "FWD")
        self.car.save()
        self.car = car_data.CarData(self.data_dir, name="ks_test_car")
        result = self.car.apply_drift_preset()
        self.assertEqual(result.changed_count, 0)
        self.assertIn("FWD", result.reason)
        self.assertFalse(self.car.changed)

    def test_cambiar_numero_de_marchas(self):
        self.car.set_gear_count(8)
        self.car.save()
        reloaded = car_data.CarData(self.data_dir, name="ks_test_car")
        self.assertEqual(reloaded.gear_count, 8)
        self.assertIn("GEAR_8=", self.read("drivetrain.ini"))
        self.assertIn("COUNT=8", self.read("drivetrain.ini"))

    def test_recargar_descarta_los_cambios(self):
        self.car.limiter = 8000
        self.car.reload()
        self.assertFalse(self.car.changed)
        self.assertEqual(self.car.limiter, 6500)

    def test_snapshot_restaura_configuracion_y_curva(self):
        original = self.car.setup_snapshot()
        self.car.limiter = 7100
        self.car.set_gear(2, 2.0)
        self.car.set_tyre_pressure(True, 22.0)
        self.car.set_power_scale(1.2)
        self.assertTrue(self.car.changed)
        self.car.restore_setup(original)
        self.assertEqual(self.car.limiter, 6500)
        self.assertAlmostEqual(self.car.gear_ratios()[1], 2.158, places=3)
        self.assertAlmostEqual(self.car.tyre_pressure(True), 17.0, places=2)
        self.assertFalse(self.car.changed)

    def test_snapshot_rechaza_datos_no_validos_sin_inyectarlos(self):
        before = self.car.setup_snapshot()
        malicious = {
            "version": 1,
            "values": {"engine.ini": {"ENGINE_DATA": {"LIMITER": "7200\\n[HACK]"}}},
            "turbos": [],
            "power_curve": [],
        }
        self.car.restore_setup(malicious)
        self.assertEqual(self.car.limiter, 6500)
        self.assertFalse(self.car.ini("engine.ini").has_section("HACK"))
        self.car.restore_setup(before)
        with self.assertRaises(ValueError):
            self.car.restore_setup({"version": 999})

    def test_coche_sin_ficheros_no_es_editable(self):
        empty = car_data.CarData(self.tmp / "vacia", name="vacia")
        self.assertFalse(empty.editable)


if __name__ == "__main__":
    unittest.main()
