"""Tests de la capa de datos del coche (lectura, edicion y guardado)."""
from __future__ import annotations

import shutil
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


class AwdTest(TempCarMixin):
    """Traccion total: solo se editan las claves que el coche ya trae escritas.

    El coche de pruebas es RWD y no tiene [AWD]; se le anaden las dos secciones
    tal y como las escriben los coches reales de Assetto Corsa (AWD y AWD2).
    """

    AWD_SECTION = """
[AWD]
FRONT_SHARE=35
FRONT_DIFF_POWER=0.10
FRONT_DIFF_COAST=0.00
FRONT_DIFF_PRELOAD=0
CENTRE_DIFF_POWER=0.02
CENTRE_DIFF_COAST=0.02
CENTRE_DIFF_PRELOAD=0
REAR_DIFF_POWER=0.00
REAR_DIFF_COAST=0.28
REAR_DIFF_PRELOAD=0
"""

    AWD2_SECTION = """
[AWD2]
FRONT_DIFF_POWER=0.01
CENTRE_RAMP_TORQUE=100.0
CENTRE_MAX_TORQUE=1000.0
REAR_DIFF_POWER=0.50
"""

    def setUp(self) -> None:
        super().setUp()
        # Copia intacta (sin [AWD]) para comprobar que no se inventan parametros.
        shutil.copytree(self.data_dir, self.tmp / "sin_awd")
        self.sin_awd = car_data.CarData(
            self.tmp / "sin_awd", name="ks_test_car", ui_name="Coche de prueba"
        )
        drivetrain = self.data_dir / "drivetrain.ini"
        drivetrain.write_text(
            drivetrain.read_text(encoding="utf-8") + self.AWD_SECTION + self.AWD2_SECTION,
            encoding="utf-8",
        )
        self.car = car_data.CarData(self.data_dir, name="ks_test_car", ui_name="Coche de prueba")

    def test_coche_sin_secciones_awd_no_ofrece_parametros(self):
        self.assertEqual(self.sin_awd.awd_sections, ())
        self.assertFalse(self.sin_awd.has_awd)
        self.assertEqual(self.sin_awd.awd_values(), {})
        self.assertEqual(self.sin_awd.awd_mode, "")
        self.assertFalse(self.sin_awd.set_awd_value("AWD", "FRONT_SHARE", 50))
        intacto = (self.tmp / "sin_awd" / "drivetrain.ini").read_text(encoding="utf-8")
        self.assertNotIn("[AWD]", intacto)
        self.assertFalse(self.sin_awd.changed)

    def test_lee_awd_y_awd2_solo_lo_que_existe(self):
        self.assertEqual(self.car.awd_sections, ("AWD", "AWD2"))
        self.assertTrue(self.car.has_awd)
        self.assertEqual(self.car.awd_mode, "AWD2")
        self.assertAlmostEqual(self.car.awd_value("AWD", "FRONT_SHARE"), 35.0, places=3)
        self.assertAlmostEqual(self.car.awd_value("AWD2", "CENTRE_RAMP_TORQUE"), 100.0, places=3)
        # CENTRE_RAMP_TORQUE solo vive en [AWD2] y FRONT_SHARE solo en [AWD]
        self.assertIsNone(self.car.awd_value("AWD", "CENTRE_RAMP_TORQUE"))
        self.assertIsNone(self.car.awd_value("AWD2", "FRONT_SHARE"))
        self.assertIsNone(self.car.awd_value("AWD", "INVENTADO"))

    def test_escribe_solo_claves_existentes_y_valores_validos(self):
        self.assertTrue(self.car.set_awd_value("AWD", "FRONT_SHARE", 55))
        self.assertTrue(self.car.set_awd_value("AWD", "REAR_DIFF_COAST", 0.45))
        self.assertTrue(self.car.set_awd_value("AWD2", "CENTRE_MAX_TORQUE", 850.0))
        self.assertEqual(self.car.awd_value("AWD", "FRONT_SHARE"), 55.0)
        self.assertIn("drivetrain.ini", self.car.dirty_files())
        self.assertEqual(self.car.save(), ["drivetrain.ini"])
        guardado = self.read("drivetrain.ini")
        self.assertIn("FRONT_SHARE=55", guardado)
        self.assertIn("REAR_DIFF_COAST=0.45", guardado)
        self.assertIn("CENTRE_MAX_TORQUE=850", guardado)
        # el resto de claves AWD que no se han tocado queda como estaba
        self.assertIn("REAR_DIFF_POWER=0.00", guardado)
        self.assertIn("CENTRE_RAMP_TORQUE=100.0", guardado)

    def test_rechaza_claves_inexistentes_sin_crearlas(self):
        antes = self.read("drivetrain.ini")
        self.assertFalse(self.car.set_awd_value("AWD2", "FRONT_SHARE", 50))
        self.assertFalse(self.car.set_awd_value("AWD", "CENTRE_RAMP_TORQUE", 120))
        self.assertFalse(self.car.set_awd_value("AWD3", "FRONT_SHARE", 50))
        self.assertFalse(self.car.set_awd_value("AWD", "FRONT_SHARE", float("nan")))
        self.assertEqual(self.read("drivetrain.ini"), antes)
        self.assertNotIn("CENTRE_RAMP_TORQUE", self.read("drivetrain.ini").split("[AWD2]")[0])

    def test_valida_rangos_reales_del_juego(self):
        for section, key, value in (
            ("AWD", "FRONT_SHARE", 140.0),
            ("AWD", "FRONT_SHARE", -5.0),
            ("AWD", "FRONT_DIFF_POWER", 1.5),
            ("AWD", "REAR_DIFF_COAST", -0.1),
            ("AWD2", "CENTRE_RAMP_TORQUE", 99999.0),
            ("AWD2", "CENTRE_MAX_TORQUE", -1.0),
        ):
            with self.subTest(key=key, value=value):
                self.assertFalse(self.car.set_awd_value(section, key, value))
        self.assertFalse(self.car.changed)

    def test_snapshot_y_restore_llevan_los_ajustes_awd(self):
        original = self.car.setup_snapshot()
        self.assertIn("AWD", original["values"]["drivetrain.ini"])
        self.assertTrue(self.car.set_awd_value("AWD", "FRONT_SHARE", 20))
        self.assertTrue(self.car.set_awd_value("AWD2", "CENTRE_RAMP_TORQUE", 250.0))
        self.car.restore_setup(original)
        self.assertAlmostEqual(self.car.awd_value("AWD", "FRONT_SHARE"), 35.0, places=3)
        self.assertAlmostEqual(self.car.awd_value("AWD2", "CENTRE_RAMP_TORQUE"), 100.0, places=3)

    def test_restore_no_inyecta_claves_awd_inexistentes(self):
        snapshot = self.car.setup_snapshot()
        snapshot["values"]["drivetrain.ini"]["AWD"]["HACKED"] = "1"
        snapshot["values"]["drivetrain.ini"]["AWD2"]["FRONT_SHARE"] = "90"
        self.car.restore_setup(snapshot)
        self.assertFalse(self.car.ini("drivetrain.ini").has("AWD", "HACKED"))
        self.assertFalse(self.car.ini("drivetrain.ini").has("AWD2", "FRONT_SHARE"))

    def test_resumen_awd_usa_porcentajes_y_newtons(self):
        resumen = dict(self.car.awd_summary())
        self.assertEqual(resumen["Reparto delantero"], "35%")
        self.assertEqual(resumen["AWD · REAR_DIFF_COAST"], "28%")
        self.assertEqual(resumen["AWD2 · CENTRE_RAMP_TORQUE"], "100 Nm")


if __name__ == "__main__":
    unittest.main()
