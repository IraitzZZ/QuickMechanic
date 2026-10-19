"""Tests del motor de calculo: prestaciones, gearing, presets y diagnostico."""
from __future__ import annotations

import unittest

from quickmechanic import analysis
from unittest import mock

from quickmechanic import car_data
from tests.support import TempCarMixin


class BaseTest(TempCarMixin):
    """Coche de prueba recien leido para cada test."""

    def setUp(self) -> None:
        super().setUp()
        self._car = lambda: car_data.CarData(self.data_dir, name="ks_test_car", ui_name="Coche de prueba")


class PerformanceTest(BaseTest):
    def test_estima_prestaciones_coherentes(self) -> None:
        car = self._car()
        estimate = analysis.estimate_performance(car)
        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertGreater(estimate.power_hp, 50)
        self.assertGreater(estimate.top_speed_kmh, 100)
        self.assertLess(estimate.top_speed_kmh, 500)
        self.assertGreater(estimate.max_accel_g, 0.1)
        if estimate.zero_100 is not None:
            self.assertGreater(estimate.zero_100, 1.0)
            self.assertLess(estimate.zero_100, 60.0)
        if estimate.zero_100 is not None and estimate.zero_200 is not None:
            self.assertLess(estimate.zero_100, estimate.zero_200)
        self.assertTrue(estimate.assumptions)

    def test_sin_curva_no_hay_estimacion(self) -> None:
        car = self._car()
        with mock.patch.object(car, "power_points", return_value=[]):
            self.assertIsNone(analysis.estimate_performance(car))

    def test_la_velocidad_de_cada_marcha_es_creciente(self) -> None:
        gears = analysis.gear_speeds(self._car())
        self.assertTrue(gears)
        speeds = [gear.shift_kmh for gear in gears]
        self.assertEqual(speeds, sorted(speeds))
        self.assertTrue(all(gear.shift_kmh > 0 for gear in gears))


class GearingTest(BaseTest):
    def test_el_gearing_optimo_llega_a_la_velocidad_pedida(self) -> None:
        car = self._car()
        plan = analysis.optimal_gearing(car, 300.0)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(len(plan.ratios), len(car.gear_ratios()))
        self.assertLess(abs(plan.top_speed_kmh - 300.0), 12.0)
        ratios = list(plan.ratios)
        self.assertEqual(ratios, sorted(ratios, reverse=True))

    def test_aplicar_el_plan_escribe_las_relaciones(self) -> None:
        car = self._car()
        plan = analysis.optimal_gearing(car, 260.0)
        assert plan is not None
        applied = analysis.apply_gearing(car, plan)
        self.assertEqual(applied, len(plan.ratios))
        self.assertEqual(car.gear_ratios(), list(plan.ratios))
        self.assertTrue(car.changed)

    def test_sin_velocidad_objetivo_usa_la_potencia(self) -> None:
        plan = analysis.optimal_gearing(self._car())
        assert plan is not None
        self.assertGreater(plan.top_speed_kmh, 120.0)


class StyleTest(BaseTest):
    def test_los_presets_solo_tocan_claves_existentes(self) -> None:
        for style in ("street", "track", "gt3", "drag", "rally", "drift"):
            with self.subTest(style=style):
                car = self._car()
                before = car.setup_snapshot()
                result = analysis.apply_style(car, style)
                self.assertTrue(result.notes)
                self.assertTrue(result.applied or result.skipped)
                # Lo que se aplica cambia de verdad el coche; lo que no existe no lo inventa.
                for _filename, sections in car.setup_snapshot()["values"].items():
                    for _section, keys in sections.items():
                        for _key, value in keys.items():
                            self.assertIsInstance(value, str)
                if result.applied:
                    self.assertNotEqual(before, car.setup_snapshot())

    def test_un_preset_desconocido_no_cambia_nada(self) -> None:
        car = self._car()
        result = analysis.apply_style(car, "inexistente")
        self.assertEqual(result.applied, ())
        self.assertFalse(car.changed)


class DiagnosticTest(BaseTest):
    def test_detecta_valores_imposibles(self) -> None:
        car = self._car()
        car.mass = 12.0
        findings = analysis.diagnostics(car)
        levels = {finding.level for finding in findings}
        self.assertIn("warn", levels)
        self.assertTrue(any(finding.area == "Peso" for finding in findings))
        ok, warn, error = analysis.severity_counts(findings)
        self.assertEqual(ok + warn + error, len(findings))

    def test_detecta_relaciones_imposibles(self) -> None:
        car = self._car()
        car.set_gear(1, 0.2)
        findings = analysis.diagnostics(car)
        self.assertTrue(any(finding.level == "error" and finding.area == "Transmision" for finding in findings))

    def test_el_diagnostico_nunca_revienta_con_un_coche_limpio(self) -> None:
        car = self._car()
        findings = analysis.diagnostics(car, analysis.estimate_performance(car))
        self.assertTrue(findings)
        self.assertTrue(all(finding.icon for finding in findings))


class CompareAndReportTest(BaseTest):
    def test_comparador_enseña_las_dos_columnas(self) -> None:
        first = self._car()
        second = self._car()
        second.mass = first.mass * 1.2
        rows = analysis.compare_cars([first, second])
        self.assertEqual([label for label, _values in rows], list(analysis._COMPARE_ROWS))
        mass_row = dict(rows)["Peso"]
        self.assertEqual(len(mass_row), 2)
        self.assertNotEqual(mass_row[0], mass_row[1])

    def test_informe_en_texto_y_html(self) -> None:
        car = self._car()
        text = analysis.report(car, analysis.estimate_performance(car))
        self.assertIn("INFORME", text)
        self.assertIn("Velocidad punta", text)
        html = analysis.report(car, analysis.estimate_performance(car), fmt="html")
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn(car.ui_name, html)

    def test_estadisticas_globales(self) -> None:
        car = self._car()
        stats = analysis.library_stats([car], {}, ())
        labels = [label for label, _value in stats]
        self.assertIn("Coches en la biblioteca", labels)
        self.assertIn("1", [value for label, value in stats if label == "Coches en la biblioteca"])


if __name__ == "__main__":
    unittest.main()
