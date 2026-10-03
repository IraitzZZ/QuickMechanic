"""Tests de las curvas .lut, los catalogos .rto y las conversiones de unidades."""
from __future__ import annotations

import unittest

from quickmechanic import lut, units
from tests.support import TEST_CAR_DATA, TempCarMixin


class LutTest(TempCarMixin):
    def test_lee_los_puntos_de_la_curva(self):
        curve = lut.LUT(self.data_dir / "power.lut")
        self.assertEqual(curve.n_rows, 29)
        self.assertEqual(curve.n_cols, 2)
        self.assertEqual(curve.rows[0], [0.0, 98.0])
        self.assertEqual(curve.rows[-1], [7000.0, 68.0])

    def test_pico_de_par(self):
        curve = lut.LUT(self.data_dir / "power.lut")
        rpm, torque = curve.peak()
        self.assertEqual(rpm, 3250)
        self.assertEqual(torque, 130)

    def test_escala_solo_una_columna(self):
        curve = lut.LUT(self.data_dir / "power.lut")
        curve.scale(2.0)
        self.assertEqual(curve.rows[0], [0.0, 196.0])
        self.assertEqual(curve.rows[0][0], 0.0)

    def test_guarda_y_mantiene_comentarios(self):
        curve = lut.LUT(self.data_dir / "power.lut")
        curve.scale(1.5)
        self.assertTrue(curve.save())
        text = self.read("power.lut")
        self.assertTrue(text.startswith("; Quick Mechanic test curve: rpm|torque (Nm)"))
        self.assertEqual(len(text.splitlines()), 30)
        self.assertIn("3250|195", text)

        reloaded = lut.LUT(self.data_dir / "power.lut")
        rpm, torque = reloaded.peak()
        self.assertEqual(rpm, 3250)
        self.assertEqual(torque, 195)

    def test_copia_de_seguridad(self):
        original = (self.data_dir / "power.lut").read_bytes()
        curve = lut.LUT(self.data_dir / "power.lut")
        curve.scale(1.1)
        curve.save()
        self.assertEqual((self.data_dir / "power.lut.bak").read_bytes(), original)

    def test_set_rows_no_acumula_errores(self):
        curve = lut.LUT(self.data_dir / "power.lut")
        base = [list(row) for row in curve.rows]
        curve.set_rows([[row[0], row[1] * 1.3] for row in base])
        curve.set_rows([[row[0], row[1] * 0.5] for row in base])
        self.assertAlmostEqual(curve.peak()[1], 130 * 0.5, places=3)

    def test_fichero_inexistente_no_revienta(self):
        curve = lut.LUT(self.data_dir / "no_existe.lut")
        self.assertEqual(curve.n_rows, 0)
        self.assertIsNone(curve.save())


class RtoTest(unittest.TestCase):
    def test_gearset_con_dientes(self):
        info = lut.read_rto(TEST_CAR_DATA / "ratios.rto")
        self.assertIsNotNone(info)
        self.assertEqual(info.count, 6)
        self.assertTrue(info.uses_teeth)
        self.assertAlmostEqual(info.ratios[0], 2.64, places=3)
        self.assertEqual(info.best_match(2.20), 2)

    def test_final_rto(self):
        info = lut.read_rto(TEST_CAR_DATA / "final.rto")
        self.assertEqual(info.count, 3)
        self.assertAlmostEqual(info.ratios[0], 5.375, places=3)

    def test_fichero_inexistente(self):
        self.assertIsNone(lut.read_rto(TEST_CAR_DATA / "no_existe.rto"))

    def test_formato_de_numero(self):
        self.assertEqual(lut.fmt_number(6500.0), "6500")
        self.assertEqual(lut.fmt_number(3.818), "3.818")
        self.assertEqual(lut.fmt_number(-3.5), "-3.5")


class UnitsTest(unittest.TestCase):
    def test_muelles(self):
        self.assertAlmostEqual(units.spring_to_nmm(90000), 90.0, places=6)
        self.assertAlmostEqual(units.spring_from_nmm(94), 94000.0, places=6)

    def test_amortiguadores(self):
        self.assertAlmostEqual(units.damper_to_nsmm(5400), 5.4, places=6)
        self.assertAlmostEqual(units.damper_from_nsmm(5.4), 5400.0, places=6)

    def test_potencia_desde_par(self):
        # 300 Nm a 6000 rpm = 188.5 kW = 252.8 CV
        self.assertAlmostEqual(units.kw_from_torque(300, 6000), 188.496, places=2)
        self.assertAlmostEqual(units.hp_from_torque(300, 6000), 252.79, places=1)

    def test_velocidad_teorica(self):
        # 60 rpm de rueda, rueda de 1 m de radio: 2*pi*60 m/min = 22.62 km/h
        self.assertAlmostEqual(units.speed_kmh(60, 1.0, 1.0, 1.0), 22.619, places=2)
        # el grupo final mas corto reduce la velocidad
        self.assertLess(units.speed_kmh(60, 1.0, 4.0, 1.0), units.speed_kmh(60, 1.0, 2.0, 1.0))

    def test_velocidad_y_regimen_son_inversas(self):
        speed = units.speed_kmh(6500, 0.744, 4.176, 0.305)
        self.assertAlmostEqual(units.rpm_at_speed(speed, 0.744, 4.176, 0.305), 6500, places=3)

    def test_interpolacion_del_par(self):
        points = [(0, 100), (1000, 200), (2000, 150)]
        self.assertAlmostEqual(units.torque_at_rpm(points, 500), 150, places=6)
        self.assertAlmostEqual(units.torque_at_rpm(points, -100), 100, places=6)
        self.assertAlmostEqual(units.torque_at_rpm(points, 9000), 150, places=6)

    def test_relacion_peso_potencia(self):
        cv_per_tonne, kg_per_cv = units.power_weight(1050, 200)
        self.assertAlmostEqual(cv_per_tonne, 190.47, places=1)
        self.assertAlmostEqual(kg_per_cv, 5.25, places=2)
        self.assertEqual(units.power_weight(0, 0), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
