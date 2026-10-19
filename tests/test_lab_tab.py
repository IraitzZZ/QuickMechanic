"""Tests de la pestana Taller: curva editable, presets, listas y ajustes."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest import mock

from quickmechanic import analysis, car_data, i18n
from quickmechanic.tabs.lab_tab import LabTab
from tests.support import TempCarMixin


class LabTabTest(TempCarMixin):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        super().setUp()
        i18n.set_language("es")
        # Ni perfiles, ni versiones, ni historial tocan la carpeta real del usuario.
        self._settings_root = self.tmp / "appdata"
        self._root_patch = mock.patch("quickmechanic.garage.root_dir", return_value=self._settings_root)
        self._root_patch.start()
        self.addCleanup(self._root_patch.stop)
        self.car = car_data.CarData(self.data_dir, name="ks_test_car", ui_name="Coche de prueba")
        self.tab = LabTab()
        self.addCleanup(self.tab.deleteLater)
        self.tab.load(self.car)

    def test_la_curva_se_puede_arrastrar_y_escribe_el_lut(self) -> None:
        puntos = self.tab.curve.points()
        self.assertGreater(len(puntos), 3)
        cambiado = []
        self.tab.changed.connect(lambda: cambiado.append(True))
        self.tab._on_curve_point(1, 111.5)
        self.assertEqual(self.car.power_points()[1][1], 111.5)
        self.assertEqual(cambiado, [True])
        # La vista de potencia no deja editar: solo dibuja lo que hay.
        self.tab.curve_mode.setCurrentIndex(1)
        self.assertFalse(self.tab.curve.isEnabled())
        self.tab.curve_mode.setCurrentIndex(2)
        self.assertGreater(len(self.tab.curve.points()), 2)

    def test_las_prestaciones_aparecen_en_las_estadisticas(self) -> None:
        estimate = analysis.estimate_performance(self.car)
        self.assertIsNotNone(estimate)
        assert estimate is not None
        from PyQt6.QtWidgets import QLabel

        textos = " ".join(label.text() for label in self.tab.stats.findChildren(QLabel))
        self.assertIn(f"{estimate.top_speed_kmh:.0f}", textos)

    def test_el_diagnostico_pinta_los_tres_niveles(self) -> None:
        self.tab._refresh_diagnostics()
        texto = self.tab.diagnostic_view.toPlainText()
        self.assertIn("correctos", texto)
        self.assertTrue("🟢" in texto or "🟡" in texto or "🔴" in texto)

    def test_los_presets_de_estilo_cambian_el_coche(self) -> None:
        self.tab._apply_style("track")
        self.assertIn("presion", self.tab.style_note.text().lower())
        self.assertTrue(self.car.changed)

    def test_los_ajustes_rapidos_escriben_presiones_y_frenos(self) -> None:
        self.tab.pressure_front.setValue(26.0)
        self.tab.brake_bias.setValue(64.0)
        self.assertAlmostEqual(self.car.tyre_pressure(True), 26.0, places=2)
        self.assertAlmostEqual(self.car.brake_bias_percent, 64.0, places=2)

    def test_setup_manager_guarda_carga_y_exporta(self) -> None:
        destino = self._settings_root
        self.tab.setup_name.setText("Monza seco")
        self.tab.setup_circuit.setCurrentText("Monza")
        self.tab.setup_conditions.setText("seco")
        self.tab._save_setup()
        self.assertEqual(self.tab.setup_list.count(), 1)
        self.car.mass = 1111.0
        self.tab.setup_list.setCurrentRow(0)
        self.tab._load_setup()
        self.assertNotAlmostEqual(self.car.mass, 1111.0)
        exportado = destino / "compartido.qmsetup"
        self.tab.setup_list.setCurrentRow(0)
        with mock.patch(
            "quickmechanic.tabs.lab_tab.QFileDialog.getSaveFileName",
            return_value=(str(exportado), "*.qmsetup"),
        ):
            self.tab._export_setup()
        self.assertTrue(exportado.is_file())

    def test_respaldos_y_clonado_desde_la_pestana(self) -> None:
        self.tab.car_folder = self.tmp
        self.tab._create_backup()
        self.assertEqual(self.tab.backup_list.count(), 1)
        self.assertIn("1 respaldo", self.tab.backup_note.text())

    def test_informe_de_texto_se_escribe_en_disco(self) -> None:
        destino = self.tmp / "informe.txt"
        with mock.patch(
            "quickmechanic.tabs.lab_tab.QFileDialog.getSaveFileName",
            return_value=(str(destino), "*.txt"),
        ):
            self.tab._export_report("txt")
        self.assertTrue(destino.is_file())
        contenido = destino.read_text(encoding="utf-8")
        self.assertIn("QUICK MECHANIC", contenido)
        self.assertIn("Velocidad punta", contenido)

    def test_el_historial_empieza_vacio_y_se_rellena(self) -> None:
        from quickmechanic import garage

        self.assertIn("Aun no hay cambios", self.tab.history_view.toPlainText())
        with mock.patch("quickmechanic.garage.root_dir", return_value=self._settings_root):
            before = self.car.setup_snapshot()
            self.car.mass = 1300.0
            garage.record_changes("ks_test_car", garage.changes_between(before, self.car.setup_snapshot()))
            self.tab._refresh_history()
            self.assertIn("MASS", self.tab.history_view.toPlainText())

    def test_la_pestana_se_ve_en_ingles(self) -> None:
        from PyQt6.QtWidgets import QGroupBox, QLabel

        i18n.set_language("en")
        try:
            tab = LabTab()
            self.addCleanup(tab.deleteLater)
            tab.load(self.car)
            textos = " ".join(
                widget.text() for widget in tab.findChildren(QLabel) if hasattr(widget, "text")
            )
            titulos = " ".join(box.title() for box in tab.findChildren(QGroupBox))
            self.assertIn("Optimal gearing", titulos)
            self.assertIn("Engine curve", titulos)
            self.assertIn("Front pressure", textos)
            self.assertIn("POWER/WEIGHT", textos)
            self.assertNotIn("Gearing optimo", titulos)
            self.assertNotIn("Presion delantera", textos)
        finally:
            i18n.set_language("es")

    def test_sin_coche_la_pestana_no_falla(self) -> None:
        self.tab.load(None)
        self.assertEqual(self.tab.curve.points(), [])
        self.assertEqual(self.tab.gear_chart.series(), [])
        self.tab._refresh_diagnostics()
        self.tab._compare()
        self.tab._apply_style("street")
        self.tab._calculate_gearing()


if __name__ == "__main__":
    unittest.main()
