"""Test de humo de la interfaz.

Se ejecuta en modo sin pantalla (offscreen), asi que sirve tambien para
comprobar que el .exe compilado arranca en cualquier maquina.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # pragma: no cover - depende del entorno
    from PyQt6.QtWidgets import QApplication

    from quickmechanic import branding, guide, main, theme, widgets

    GUI = True
except Exception as error:  # pragma: no cover
    GUI = False
    GUI_ERROR = str(error)

from tests.support import FIXTURES, make_car_preview, make_skin


@unittest.skipUnless(GUI, "PyQt6 no esta disponible")
class GuiSmokeTest(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qm_gui_"))
        shutil.copytree(FIXTURES / "content", self.tmp / "content")
        self.car_dir = self.tmp / "content" / "cars" / "ks_test_car"
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        # Skins como las del juego: una con prioridad (se muestra primero), otra
        # normal y una sin preview; mas una preview suelta en la raiz del coche.
        make_skin(self.car_dir, "default", display_name="Default")
        make_skin(
            self.car_dir,
            "Quick_Orange",
            display_name="Quick Orange",
            number="27",
            team="QM Racing",
            priority=5,
        )
        make_skin(self.car_dir, "Sin_Preview", display_name="Sin Preview", preview=False)
        make_car_preview(self.car_dir)

        # no tocar la configuracion real del usuario desde los tests
        patcher = mock.patch.object(main.settings, "set_value")
        self.settings_mock = patcher.start()
        self.addCleanup(patcher.stop)
        # y no leer la que ya tenga guardada (eleccion de skin, ruta de AC...)
        getter = mock.patch.object(main.settings, "get", return_value=None)
        getter.start()
        self.addCleanup(getter.stop)
        # El taller (historial, versiones, setups) tampoco escribe en el perfil real:
        # guardar desde un test no debe dejar rastro en %APPDATA%\QuickMechanic.
        taller = mock.patch.object(main.garage, "root_dir", return_value=self.tmp / "perfil")
        taller.start()
        self.addCleanup(taller.stop)

        self.window = main.MainWindow(ac_root=self.tmp)
        self.addCleanup(self.window.deleteLater)
        # Una carga en segundo plano no puede seguir viva cuando se destruye la ventana.
        self.addCleanup(self._wait_for_car_load)
        from PyQt6.QtTest import QTest
        for _ in range(500):
            scan = self.window._scan_thread  # noqa: SLF001
            if self.window.car_list.isEnabled() and (scan is None or not scan.isRunning()):
                break
            QTest.qWait(10)

    def _wait_for_car_load(self) -> None:
        """Espera a que termine el desempaquetado en segundo plano (si lo hay)."""
        from PyQt6.QtTest import QTest
        for _ in range(1000):
            if self.window._load_thread is None:  # noqa: SLF001
                break
            QTest.qWait(10)

    def select(self, name: str) -> None:
        self._wait_for_car_load()
        for row, car in enumerate(self.window._shown):  # noqa: SLF001
            if car.name == name:
                self.window.car_list.setCurrentRow(row)
                self._wait_for_car_load()
                return
        raise AssertionError(f"no se ha encontrado {name}")

    def read(self, name: str) -> str:
        car_dir = self.tmp / "content" / "cars" / "ks_test_car" / "data" / name
        return car_dir.read_text(encoding="utf-8", errors="replace")

    def pills(self) -> list[str]:
        out = []
        for index in range(self.window.pill_slot.count()):  # noqa: SLF001
            widget = self.window.pill_slot.itemAt(index).widget()  # noqa: SLF001
            if widget is not None:
                out.append(widget.text())
        return out

    # ------------------------------------------------------------------ tests
    def test_lista_de_coches(self):
        self.assertEqual(self.window.car_list.count(), 2)
        self.assertIn("2 de 2 coches", self.window.list_status.text())

    def test_filtro_de_coches_editables(self):
        self.window.editable_filter.setChecked(True)
        self.window._apply_filter()  # noqa: SLF001
        self.assertEqual(self.window.car_list.count(), 1)
        self.assertIn("ks_test_car", self.window.car_list.item(0).toolTip())
        self.assertIn("editables", self.window.list_status.text())

    def test_carga_asincrona_mantiene_activa_la_ventana(self):
        original_scan = main.ac_scanner.list_cars

        def slow_scan(root):
            time.sleep(0.15)
            return original_scan(root)

        with mock.patch.object(main.ac_scanner, "list_cars", side_effect=slow_scan):
            self.window._reload_cars()  # noqa: SLF001
            self.assertFalse(self.window.car_list.isEnabled())
            self.assertIn("segundo plano", self.window.footer_status.text())
            self.assertIsNotNone(self.window._scan_thread)  # noqa: SLF001
            from PyQt6.QtTest import QTest
            for _ in range(100):
                scan = self.window._scan_thread  # noqa: SLF001
                if self.window.car_list.isEnabled() and (scan is None or not scan.isRunning()):
                    break
                QTest.qWait(10)
        self.assertTrue(self.window.car_list.isEnabled())
        self.assertEqual(self.window.car_list.count(), 2)

    def test_discord_de_cabecera_abre_invite_oficial(self):
        from PyQt6.QtCore import QUrl
        with mock.patch.object(main.QDesktopServices, "openUrl", return_value=True) as open_url:
            main.MainWindow._open_discord()
        open_url.assert_called_once_with(QUrl(guide.DISCORD_URL))

    def test_aviso_discord_es_no_modal_y_se_puede_descartar(self):
        self.window.show()
        self.window._show_discord_notification()  # noqa: SLF001
        self.assertTrue(self.window.community_notification.isVisible())
        self.assertEqual(self.window._community_notification_timer.interval(), 9000)  # noqa: SLF001
        self.assertFalse(self.window.community_notification.isWindow())
        self.window._hide_discord_notification()  # noqa: SLF001
        self.assertFalse(self.window.community_notification.isVisible())

    def test_sonido_se_puede_intercambiar_en_coche_data_acd(self):
        self.select("acd_only_car")
        self.assertIsNone(self.window._car)  # noqa: SLF001
        self.assertTrue(self.window.swap_button.isEnabled())
        self.assertEqual(self.window.swap_button.text(), "Swaps")

    def test_seleccionar_coche_editable(self):
        self.select("ks_test_car")
        self.assertIsNotNone(self.window._car)  # noqa: SLF001
        self.assertEqual(self.window.motor_tab.limiter.value(), 6500)
        self.assertEqual(self.window.gear_tab.count.value(), 6)
        self.assertAlmostEqual(self.window.chassis_tab.spring_front.value(), 90.0, places=1)
        self.assertTrue(self.window.tabs.isTabEnabled(0))
        self.assertIn("Avisos", self.window.info_tab.view.toPlainText())
        self.assertTrue(self.window.banner.isHidden())

    def test_cabecera_con_los_datos_del_coche(self):
        self.select("ks_test_car")
        self.assertEqual(self.window.car_name.text(), "Quick Mechanic Test Car")
        self.assertIn("Quick Mechanic", self.window.car_brand.text())
        labels = self.pills()
        self.assertIn("RWD", labels)
        self.assertIn("6 marchas", labels)
        self.assertTrue(any(label.endswith("CV") for label in labels), labels)
        self.assertTrue(any(label.endswith("kg") for label in labels), labels)

    def test_logo_de_app_usa_el_icono_del_proyecto(self):
        icon_path = branding.logo_path()
        self.assertIsNotNone(icon_path)
        self.assertEqual(icon_path.name, "icono.ico")
        self.assertFalse(branding.app_icon().isNull())
        self.assertFalse(branding.brand_pixmap(64).isNull())

    def test_splash_anima_transiciones_sin_inventar_progreso(self):
        splash = branding.LoadingSplash()
        self.addCleanup(splash.deleteLater)
        initial_progress = splash._progress  # noqa: SLF001
        splash._tick()  # noqa: SLF001
        self.assertEqual(splash._progress, initial_progress)  # noqa: SLF001
        splash.set_status("LEYENDO DATOS", 45)
        from PyQt6.QtTest import QTest
        QTest.qWait(650)
        self.assertEqual(splash._status, "LEYENDO DATOS")  # noqa: SLF001
        self.assertEqual(round(splash._progress), 45)  # noqa: SLF001
        self.assertAlmostEqual(splash.statusOpacity, 1.0, places=2)

    def test_fuente_de_interfaz_prefiere_sans_modernas_disponibles(self):
        from PyQt6.QtGui import QFont
        chosen = theme.preferred_font_family()
        self.assertTrue(chosen)
        app = QApplication.instance()
        original = app.font()
        theme.apply(app)
        self.assertEqual(app.font().family(), chosen)
        app.setFont(original)

    def test_navegacion_de_guia_y_preferencia_de_inicio(self):
        dialog = guide.QuickGuideDialog(first_run=True, show_on_start=True)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(len(dialog.PAGES), 5)
        self.assertEqual(dialog.progress.text(), "GUÍA  01 / 05")
        self.assertEqual(guide.DISCORD_URL, "https://discord.gg/pWE5yEKexW")
        self.assertEqual(dialog.discord_button.text(), "Abrir Discord  ↗")
        dialog.show_on_start_check.setChecked(False)
        self.assertFalse(dialog.show_on_start)
        for _ in range(4):
            dialog._next()
        self.assertEqual(dialog.progress.text(), "GUÍA  05 / 05")
        self.assertEqual(dialog.next_button.text(), "Empezar a trabajar")

    def test_tema_carbon_y_oro_ignora_preferencias_legacy(self):
        with (
            mock.patch.object(theme, "ensure_assets", return_value={}),
            mock.patch.object(main.settings, "get", return_value="#36a3ff"),
        ):
            theme.apply(self.app)
        self.assertEqual(theme.ACCENT, "#c6a45a")
        self.assertEqual(self.app.palette().highlight().color().name(), "#c6a45a")
        self.assertNotIn("#36a3ff", self.app.styleSheet())
        self.assertIn("#c6a45a", self.app.styleSheet())

    def test_previsualizacion_del_coche(self):
        self.select("ks_test_car")
        preview = self.window.preview
        self.assertEqual(preview.title.text(), "Quick Mechanic Test Car")
        # la skin con mas prioridad sale primero
        self.assertEqual(preview.current_skin, "Quick_Orange")
        self.assertEqual(preview.skin_count.text(), "3 skins")
        self.assertIn("QM Racing", preview.detail.text())
        self.assertIn("#27", preview.detail.text())
        self.assertIsNotNone(preview.image.pixmap())
        self.assertFalse(preview.image.pixmap().isNull())
        self.assertEqual(preview.zoom_slider.minimum(), 100)
        self.assertEqual(preview.zoom_slider.maximum(), 200)
        self.assertEqual(preview.zoom_value.text(), "100%")

    def test_cambiar_de_skin_cambia_la_imagen_y_se_recuerda(self):
        self.select("ks_test_car")
        preview = self.window.preview
        first = preview.image.pixmap().cacheKey()

        preview.skin_box.setCurrentIndex(2)  # Sin_Preview (sin imagen propia)
        self.assertEqual(preview.current_skin, "Sin_Preview")
        self.assertIn("sin imagen preview", preview.detail.text())
        # tira de la preview suelta de la raiz del coche, no del marcador
        self.assertNotEqual(preview.image.pixmap().cacheKey(), first)

        self.settings_mock.assert_any_call("skin_choices", {"ks_test_car": "Sin_Preview"})

    def test_elegir_otro_coche_olvida_la_previsualizacion_anterior(self):
        self.select("ks_test_car")
        self.select("acd_only_car")
        self.assertIsNone(self.window._car)  # noqa: SLF001
        self.assertEqual(self.window.preview.current_skin, "")
        self.assertEqual(self.window.preview.title.text(), "Coche bloqueado (data.acd)")
        self.assertIn("solo data.acd", self.pills())

    def test_editar_y_guardar(self):
        self.select("ks_test_car")
        self.window.motor_tab.limiter.setValue(7200)
        self.window.motor_tab.scale.setValue(1.2)
        self.assertIn("cambios sin guardar", self.window.footer_status.text())

        self.window._save()  # noqa: SLF001
        self.assertIn("LIMITER=7200", self.read("engine.ini"))
        self.assertIn("3250|156", self.read("power.lut"))
        self.assertNotIn("cambios sin guardar", self.window.footer_status.text())

        backup = (self.tmp / "content" / "cars" / "ks_test_car" / "data" / "engine.ini.bak")
        self.assertTrue(backup.is_file())
        self.assertIn("LIMITER=6500", backup.read_text(encoding="utf-8", errors="replace"))
        snapshots = list((self.tmp / "content" / "cars" / "ks_test_car" / "quickmechanic_backups").glob("data_backup_*.zip"))
        self.assertEqual(len(snapshots), 1)
        import zipfile
        with zipfile.ZipFile(snapshots[0]) as archive:
            self.assertIn("data/engine.ini", archive.namelist())
            self.assertIn("LIMITER=6500", archive.read("data/engine.ini").decode("utf-8"))

    def test_restaurar_curva(self):
        self.select("ks_test_car")
        self.window.motor_tab.scale.setValue(1.2)
        self.assertAlmostEqual(self.window._car.power_scale, 1.2, places=3)  # noqa: SLF001
        self.window.motor_tab.reset_curve.click()
        self.assertAlmostEqual(self.window._car.power_scale, 1.0, places=3)  # noqa: SLF001
        self.assertFalse(self.window._car.changed)  # noqa: SLF001

    def test_el_deslizador_mueve_el_multiplicador(self):
        self.select("ks_test_car")
        self.window.motor_tab.scale_slider.setValue(150)
        self.assertAlmostEqual(self.window.motor_tab.scale.value(), 1.5, places=3)
        self.assertAlmostEqual(self.window._car.power_scale, 1.5, places=3)  # noqa: SLF001
        self.assertAlmostEqual(self.window.motor_tab.scale_slider.value(), 150)

    def test_los_tiles_muestran_los_datos_clave(self):
        self.select("ks_test_car")
        motor = self.window.motor_tab.stats
        self.assertNotEqual(motor.tiles["torque"].value_label.text(), "—")
        self.assertEqual(motor.tiles["cut"].value_label.text(), "6500")

        gears = self.window.gear_tab.stats
        self.assertEqual(gears.tiles["drive"].value_label.text(), "RWD")
        self.assertEqual(gears.tiles["gears"].value_label.text(), "6")
        self.assertNotEqual(gears.tiles["top"].value_label.text(), "—")

        chassis = self.window.chassis_tab.stats
        self.assertEqual(chassis.tiles["mass"].value_label.text(), "1050")
        self.assertNotEqual(chassis.tiles["front_hz"].value_label.text(), "—")

    def test_cambiar_numero_de_marchas(self):
        self.select("ks_test_car")
        self.window.gear_tab.count.setValue(7)
        self.window.gear_tab._gear_fields[6].setValue(0.700)  # noqa: SLF001
        self.window._save()  # noqa: SLF001
        text = self.read("drivetrain.ini")
        self.assertIn("COUNT=7", text)
        self.assertIn("GEAR_7=0.7", text)

    def test_editar_suspension_en_nmm(self):
        self.select("ks_test_car")
        self.window.chassis_tab.spring_front.setValue(100.0)
        self.window._save()  # noqa: SLF001
        self.assertIn("SPRING_RATE=100000", self.read("suspensions.ini"))

    def test_coche_bloqueado_muestra_el_aviso(self):
        self.select("acd_only_car")
        self.assertIsNone(self.window._car)  # noqa: SLF001
        self.assertTrue(self.window.tabs.isTabEnabled(0))
        self.assertFalse(self.window.tabs.isTabEnabled(1))
        self.assertFalse(self.window.banner.isHidden())
        texto = self.window.info_tab.view.toPlainText()
        self.assertIn("data.acd", texto)
        self.assertIn("Unpack", texto)

    def test_buscador(self):
        self.window.search.setText("acd")
        self.window._apply_filter()  # noqa: SLF001
        self.assertEqual(self.window.car_list.count(), 1)

    def test_descartar_cambios(self):
        self.select("ks_test_car")
        self.window.motor_tab.limiter.setValue(8000)
        with mock.patch.object(self.window, "_confirm_discard", return_value=True):
            self.window._reload_current()  # noqa: SLF001
        self.assertEqual(self.window.motor_tab.limiter.value(), 6500)
        self.assertFalse(self.window._car.changed)  # noqa: SLF001

    def test_aviso_de_dano_por_boost(self):
        self.select("ks_test_car")
        self.window.motor_tab._turbo_fields["MAX_BOOST"].setValue(2.0)  # noqa: SLF001
        self.assertIn("umbral de dano", self.window.motor_tab.turbo_warning.text())

    def test_favorito_filtrado_y_teclas_de_atajo(self):
        self.select("ks_test_car")
        self.window._toggle_favorite()  # noqa: SLF001
        self.assertIn("ks_test_car", self.window._favorites)  # noqa: SLF001
        self.window.favorite_filter.setChecked(True)
        self.window._apply_filter()  # noqa: SLF001
        self.assertEqual(self.window.car_list.count(), 1)
        self.assertIn("★", self.window.car_list.item(0).text())

    def test_ctrl_numero_cambia_de_pestana_y_alt_flechas_cambian_de_coche(self):
        self.select("ks_test_car")
        self.assertTrue(self.window.tabs.isTabEnabled(2))
        self.window._go_to_tab(2)  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 2)
        self.window._go_to_tab(999)  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 2)
        self.window.car_list.setCurrentRow(0)
        self._wait_for_car_load()  # el coche de la fila 0 se desempaqueta en segundo plano
        self.window._step_car(1)  # noqa: SLF001
        self.assertEqual(self.window.car_list.currentRow(), 1)
        self._wait_for_car_load()  # el coche de la fila 1 puede necesitar desempaquetarse
        self.window._step_car(1)  # noqa: SLF001
        self.assertEqual(self.window.car_list.currentRow(), 0)
        self.window._step_car(-1)  # noqa: SLF001
        self.assertEqual(self.window.car_list.currentRow(), 1)

    def test_los_atajos_ctrl_numero_estan_registrados(self):
        from PyQt6.QtGui import QKeySequence, QShortcut

        keys = {
            shortcut.key().toString()
            for shortcut in self.window.findChildren(QShortcut)
        }
        for number in range(1, 10):
            self.assertIn(QKeySequence(f"Ctrl+{number}").toString(), keys)
        self.assertIn(QKeySequence("Alt+Up").toString(), keys)
        self.assertIn(QKeySequence("Alt+Down").toString(), keys)

    def test_atajos_nuevos_estan_registrados(self):
        from PyQt6.QtGui import QKeySequence, QShortcut

        keys = {shortcut.key().toString() for shortcut in self.window.findChildren(QShortcut)}
        for sequence in ("Ctrl+Tab", "Ctrl+Shift+Tab", "F1", "Ctrl+Shift+F", "Ctrl+Shift+C",
                         "Ctrl+L", "Ctrl+Shift+H"):
            self.assertIn(QKeySequence(sequence).toString(), keys)

    def test_ctrl_tab_recorre_pestanas_saltando_las_deshabilitadas(self):
        # Sin coche, las pestanas 1, 2, 3, 5, 6 y 7 estan deshabilitadas.
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.window._cycle_tab(1)  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 4)
        self.window._cycle_tab(1)  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 8)
        self.window._cycle_tab(1)  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.window._cycle_tab(-1)  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 8)

    def test_pistas_de_atajo_en_los_tooltips_de_pestanas(self):
        self.assertIn("(Ctrl+1)", self.window.tabs.tabToolTip(0))
        self.assertIn("(Ctrl+9)", self.window.tabs.tabToolTip(8))

    def test_ctrl_shift_f_limpia_busqueda_y_filtros(self):
        self.window.search.setText("quick")
        self.window.favorite_filter.setChecked(True)
        self.window.editable_filter.setChecked(True)
        self.window._clear_filters()  # noqa: SLF001
        self.assertEqual(self.window.search.text(), "")
        self.assertFalse(self.window.favorite_filter.isChecked())
        self.assertFalse(self.window.editable_filter.isChecked())
        self.assertEqual(self.window.car_list.count(), 2)
        self.assertEqual(self.window.footer_status.text(), "Filtros borrados")

    def test_ctrl_shift_c_copia_el_nombre_del_coche(self):
        self.window._copy_car_name()  # noqa: SLF001
        self.assertEqual(self.window.footer_status.text(), "No hay ning\u00fan coche seleccionado")
        self.select("ks_test_car")
        self.window._copy_car_name()  # noqa: SLF001
        from PyQt6.QtWidgets import QApplication

        self.assertEqual(QApplication.clipboard().text(), self.window._source.ui_name)  # noqa: SLF001

    def test_coches_recientes_se_recuerdan_y_se_reabren_aunque_esten_filtrados(self):
        self.window._recent_cars = []  # noqa: SLF001
        self.window._show_recent_cars()  # noqa: SLF001
        self.assertIn("Todav\u00eda no has abierto", self.window.footer_status.text())

        self.select("ks_test_car")
        self.assertEqual(self.window._recent_cars, [str(self.car_dir)])  # noqa: SLF001
        self.settings_mock.assert_any_call("recent_cars", [str(self.car_dir)])
        self.window._show_recent_cars()  # noqa: SLF001
        self.assertEqual(len(self.window._recent_menu.actions()), 1)  # noqa: SLF001

        # Con un filtro que oculta el coche, abrirlo desde recientes quita el filtro.
        self.window.favorite_filter.setChecked(True)
        self.assertEqual(self.window.car_list.count(), 0)
        self.window._open_car_by_folder(str(self.car_dir))  # noqa: SLF001
        self.assertFalse(self.window.favorite_filter.isChecked())
        self.assertEqual(str(self.window._source.folder), str(self.car_dir))  # noqa: SLF001

    def test_atajos_de_lista_y_recientes_estan_registrados(self):
        from PyQt6.QtGui import QKeySequence, QShortcut

        keys = {shortcut.key().toString() for shortcut in self.window.findChildren(QShortcut)}
        for sequence in ("Ctrl+Shift+D", "Ctrl+Shift+E", "Ctrl+Shift+O", "Ctrl+Shift+P", "F5",
                         "Esc", "Alt+Shift+Up", "Alt+Shift+Down", "Ctrl+Shift+N",
                         "Ctrl+Shift+S", "Ctrl+Shift+L"):
            self.assertIn(QKeySequence(sequence).toString(), keys)

    def test_ctrl_shift_l_borra_el_historial_de_recientes(self):
        self.window._recent_cars = [str(self.car_dir)]  # noqa: SLF001
        self.window._clear_recent_cars()  # noqa: SLF001
        self.assertEqual(self.window._recent_cars, [])  # noqa: SLF001
        self.settings_mock.assert_any_call("recent_cars", [])
        self.assertEqual(
            self.window.footer_status.text(), "Historial de coches recientes borrado"
        )

    def test_atajos_de_ventana_y_lista_del_segundo_lote_estan_registrados(self):
        from PyQt6.QtGui import QKeySequence, QShortcut

        keys = {shortcut.key().toString() for shortcut in self.window.findChildren(QShortcut)}
        for sequence in ("Ctrl+Home", "Ctrl+End", "Ctrl+Q", "Ctrl+,", "Ctrl+Shift+M",
                         "Ctrl+Shift+A", "Ctrl+Shift+G", "Ctrl+Shift+K", "Ctrl+Shift+U",
                         "Ctrl+Shift+Y", "Delete"):
            self.assertIn(QKeySequence(sequence).toString(), keys)

    def test_ctrl_home_y_end_van_al_primer_y_ultimo_coche(self):
        self.window._go_edge_car(False)  # noqa: SLF001
        self.assertEqual(self.window.car_list.currentRow(), self.window.car_list.count() - 1)
        self.window._go_edge_car(True)  # noqa: SLF001
        self.assertEqual(self.window.car_list.currentRow(), 0)

    def test_ctrl_shift_k_cambia_el_orden_y_se_recuerda(self):
        self.assertEqual(self.window._sort_mode, "name")  # noqa: SLF001
        self.window._cycle_sort()  # noqa: SLF001
        self.assertEqual(self.window._sort_mode, "favorites")  # noqa: SLF001
        self.settings_mock.assert_any_call("sort_mode", "favorites")
        self.assertIn(self.window.SORT_LABELS["favorites"], self.window.footer_status.text())

    def test_orden_por_editables_pone_primero_los_coches_editables(self):
        self.window._sort_mode = "editable"  # noqa: SLF001
        self.window._apply_filter()  # noqa: SLF001
        self.assertTrue(self.window._shown[0].editable)  # noqa: SLF001

    def test_marca_de_cambios_sin_guardar_en_lista_y_titulo(self):
        self.select("ks_test_car")
        self.assertFalse(self.window.car_list.currentItem().text().startswith("\u25cf"))
        self.window.motor_tab.limiter.setValue(7200)
        self.assertTrue(self.window.car_list.currentItem().text().startswith("\u25cf "))
        self.assertTrue(self.window.windowTitle().startswith("\u25cf "))

        self.window._save()  # noqa: SLF001
        self.assertFalse(self.window.car_list.currentItem().text().startswith("\u25cf"))
        self.assertFalse(self.window.windowTitle().startswith("\u25cf "))

    def test_guardar_muestra_la_hora_del_guardado_en_el_pie(self):
        self.select("ks_test_car")
        self.window.motor_tab.limiter.setValue(7200)
        self.window._save()  # noqa: SLF001
        self.assertRegex(self.window.footer_status.text(), r"^Guardado a las \d{2}:\d{2}: ")

    def test_doble_clic_alterna_el_favorito(self):
        self.select("ks_test_car")
        # El manejador ignora el elemento: basta con emitir la senal de doble clic.
        self.window.car_list.itemDoubleClicked.emit(None)
        self.assertIn("ks_test_car", self.window._favorites)  # noqa: SLF001
        self.window.car_list.itemDoubleClicked.emit(None)
        self.assertNotIn("ks_test_car", self.window._favorites)  # noqa: SLF001

    def test_menu_contextual_del_coche_se_construye(self):
        self.select("ks_test_car")
        rect = self.window.car_list.visualItemRect(self.window.car_list.currentItem())
        with mock.patch.object(main.QMenu, "exec") as run:
            self.window._car_list_menu(rect.center())  # noqa: SLF001
        run.assert_called_once()

    def test_ctrl_shift_u_quita_el_coche_actual_de_recientes(self):
        self.select("ks_test_car")
        self.assertIn(str(self.car_dir), self.window._recent_cars)  # noqa: SLF001
        self.window._forget_recent_car()  # noqa: SLF001
        self.assertNotIn(str(self.car_dir), self.window._recent_cars)  # noqa: SLF001
        self.assertEqual(self.window.footer_status.text(), "Coche quitado de recientes")

    def test_ctrl_shift_y_avisa_si_no_hay_coche_anterior(self):
        with mock.patch.object(main.settings, "get", return_value=""):
            self.window._open_last_car()  # noqa: SLF001
        self.assertIn("Todav\u00eda no hay", self.window.footer_status.text())

    def test_ctrl_shift_m_oculta_a_la_bandeja_y_ctrl_q_sale(self):
        self.window._tray = mock.Mock()  # noqa: SLF001
        with mock.patch.object(self.window, "hide") as hide:
            self.window._minimize_to_tray()  # noqa: SLF001
        hide.assert_called_once()
        with mock.patch.object(self.window, "_exit_from_tray") as leave:
            self.window._quit_app()  # noqa: SLF001
        leave.assert_called_once()

    def test_ctrl_shift_a_abre_la_carpeta_de_assetto_corsa(self):
        with mock.patch.object(main.QDesktopServices, "openUrl") as opener:
            self.window._open_ac_folder()  # noqa: SLF001
        opener.assert_called_once()

    def test_enter_en_el_buscador_pasa_el_foco_a_la_lista(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest

        self.window.show()
        self.addCleanup(self.window.hide)
        self.window.activateWindow()
        QTest.qWaitForWindowActive(self.window, 2000)
        self.window.search.setFocus()
        self.assertTrue(self.window.search.hasFocus())
        QTest.keyClick(self.window.search, Qt.Key.Key_Return)
        self.assertTrue(self.window.car_list.hasFocus())

    def test_busqueda_y_filtros_se_guardan_y_se_restauran(self):
        self.window.search.setText("quick")
        self.window.favorite_filter.setChecked(True)
        self.window.editable_filter.setChecked(False)
        self.window._save_filters()  # noqa: SLF001
        self.settings_mock.assert_any_call("search_text", "quick")
        self.settings_mock.assert_any_call("filter_favorites", True)
        self.settings_mock.assert_any_call("filter_editable", False)

        saved = {"search_text": "ks", "filter_favorites": False, "filter_editable": True}
        self.window.search.clear()
        self.window.favorite_filter.setChecked(True)
        self.window.editable_filter.setChecked(False)
        with mock.patch.object(main.settings, "get", side_effect=lambda key, default=None: saved.get(key, default)):
            self.window._restore_filters()  # noqa: SLF001
        self.assertEqual(self.window.search.text(), "ks")
        self.assertFalse(self.window.favorite_filter.isChecked())
        self.assertTrue(self.window.editable_filter.isChecked())

    def test_el_ultimo_coche_abierto_se_selecciona_al_volver(self):
        self.window.car_list.setCurrentRow(-1)
        with mock.patch.object(main.settings, "get", return_value=str(self.car_dir)):
            self.window._select_last_car()  # noqa: SLF001
        self.assertEqual(str(self.window._source.folder), str(self.car_dir))  # noqa: SLF001

    def test_ultima_pestana_se_restaura_al_arrancar(self):
        self.window.tabs.setCurrentIndex(0)
        with mock.patch.object(main.settings, "get", return_value=4):
            self.window._restore_last_tab()  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 4)
        # Una pestana deshabilitada (sin coche) no se restaura.
        self.window.tabs.setCurrentIndex(0)
        with mock.patch.object(main.settings, "get", return_value=2):
            self.window._restore_last_tab()  # noqa: SLF001
        self.assertEqual(self.window.tabs.currentIndex(), 0)

    def test_cerrar_va_a_bandeja_pero_salir_es_explicito(self):
        tray = mock.Mock()
        self.window._tray = tray  # noqa: SLF001
        self.window._close_to_tray = True  # noqa: SLF001
        event = mock.Mock()
        app_mock = mock.Mock()
        with (
            mock.patch.object(self.window, "hide") as hide,
            mock.patch.object(main.QApplication, "instance", return_value=app_mock),
            mock.patch.object(main.settings, "load", return_value={}),
            mock.patch.object(main.settings, "save"),
        ):
            self.window.closeEvent(event)
        hide.assert_called_once()
        event.ignore.assert_called_once()
        event.accept.assert_not_called()

        self.window._exit_requested = True  # noqa: SLF001
        event = mock.Mock()
        with (
            mock.patch.object(main.QApplication, "instance", return_value=app_mock),
            mock.patch.object(main.settings, "load", return_value={}),
            mock.patch.object(main.settings, "save"),
        ):
            self.window.closeEvent(event)
        event.accept.assert_called_once()
        tray.hide.assert_called_once()

    def test_deshacer_y_rehacer_ediciones(self):
        self.select("ks_test_car")
        self.window.motor_tab.limiter.setValue(7200)
        self.assertEqual(self.window._car.limiter, 7200)  # noqa: SLF001
        self.window._undo()  # noqa: SLF001
        self.assertEqual(self.window.motor_tab.limiter.value(), 6500)
        self.assertFalse(self.window._car.changed)  # noqa: SLF001
        self.window._redo()  # noqa: SLF001
        self.assertEqual(self.window.motor_tab.limiter.value(), 7200)
        self.assertTrue(self.window._car.changed)  # noqa: SLF001

    def test_presion_de_neumaticos_se_guarda(self):
        self.select("ks_test_car")
        self.window.chassis_tab.pressure_front.setValue(21.5)
        self.window._save()  # noqa: SLF001
        self.assertIn("PRESSURE_STATIC=21.5", self.read("tyres.ini"))

    def test_info_muestra_creditos_y_licencia(self):
        from PyQt6.QtWidgets import QDialog, QTextBrowser
        from quickmechanic import license as app_license
        with mock.patch.object(QDialog, "exec", return_value=0):
            self.window._show_info()
        dialogs = self.window.findChildren(QDialog)
        self.assertGreaterEqual(len(dialogs), 1)
        license_content = " ".join(widget.toPlainText() for widget in dialogs[-1].findChildren(QTextBrowser))
        self.assertIn("SuperIraitz", license_content)
        self.assertIn("CC BY-NC-SA 4.0", license_content)
        self.assertIn("CompartirIgual", license_content)
        self.assertIn(app_license.LICENSE_URL, license_content)

    def test_navegacion_lateral_y_conexion_local_con_cm(self):
        self.select("ks_test_car")
        self.assertEqual(self.window.tabs.tabText(0), "Resumen")
        self.assertEqual(self.window.tabs.count(), 10)
        self.assertFalse(hasattr(self.window.dashboard_tab, "power_plot"))
        self.assertFalse(hasattr(self.window.gear_tab, "plot"))
        self.assertFalse(hasattr(self.window.motor_tab, "plot"))
        self.window.nav_group.button(6).click()
        self.assertEqual(self.window.tabs.currentIndex(), 6)
        self.assertGreater(self.window.advanced_tab.table.rowCount(), 0)
        self.assertGreater(self.window.motor_tab.curve_table.rowCount(), 0)
        self.window.nav_group.button(5).click()
        self.assertEqual(self.window.tabs.currentIndex(), 5)
        self.window.nav_group.button(8).click()
        self.assertEqual(self.window.tabs.currentIndex(), 8)
        self.assertEqual(self.window.cm_panel.open_button.isEnabled(), self.window.content_manager_path is not None)
        if self.window.content_manager_path is None:
            self.assertIn("No encontrado", self.window.cm_panel.path_label.text())
        else:
            self.assertIn("DETECTADO", self.window.cm_panel.status.text())

    def test_pestana_circuitos_muestra_layout_y_configuracion_sin_escribir(self):
        import json
        from PyQt6.QtTest import QTest

        track = self.tmp / "content" / "tracks" / "test_track"
        (track / "ui").mkdir(parents=True)
        (track / "club" / "data").mkdir(parents=True)
        (track / "ui" / "ui_track.json").write_text(
            json.dumps({"name": "Test Track", "country": "Spain"}), encoding="utf-8"
        )
        (track / "models_club.ini").write_text("[MODEL_0]\nFILE=club.kn5\n", encoding="utf-8")
        (track / "club" / "data" / "surfaces.ini").write_text(
            "[SURFACE_0]\nKEY=ROAD\nFRICTION=0.95\n", encoding="utf-8"
        )
        original = (track / "club" / "data" / "surfaces.ini").read_bytes()

        self.window._refresh_tracks()  # noqa: SLF001
        tab = self.window.track_tab
        self.assertEqual(tab.track_list.count(), 1)
        self.assertEqual(tab.track_title.text(), "Test Track")
        self.assertEqual(tab.layout_list.count(), 1)
        self.assertEqual(tab.file_list.count(), 2)
        self.assertIn("ROAD", tab.ini_view.toPlainText())
        tab.ini_filter.setText("FRICTION")
        QTest.qWait(180)
        self.assertIn("FRICTION", tab.ini_view.toPlainText())
        self.assertTrue(tab.value_spin.isEnabled())
        self.assertEqual(tab.value_spin.value(), 0.95)
        # La lectura/filtrado no vuelve a cargar ni cambia la firma del archivo.
        stale_hash = tab._ini_sha256  # noqa: SLF001
        (track / "club" / "data" / "surfaces.ini").write_text(
            "[SURFACE_0]\nKEY=ROAD\nFRICTION=0.97\n", encoding="utf-8"
        )
        tab.ini_filter.setText("KEY")
        QTest.qWait(180)
        self.assertEqual(tab._ini_sha256, stale_hash)  # noqa: SLF001
        tab.ini_filter.setText("FRICTION")
        QTest.qWait(180)
        self.assertEqual(tab.value_spin.value(), 0.95)
        tab.value_spin.setValue(1.05)
        self.assertTrue(tab.save_value_button.isEnabled())
        from quickmechanic import track_tab
        with mock.patch.object(track_tab.QMessageBox, "warning") as warning:
            tab.save_value_button.click()
        warning.assert_called_once()
        ini_path = track / "club" / "data" / "surfaces.ini"
        self.assertIn("FRICTION=0.97", ini_path.read_text(encoding="utf-8"))
        tab._select_ini(tab.file_list.currentRow())  # noqa: SLF001
        self.assertEqual(tab.value_spin.value(), 0.97)
        tab.value_spin.setValue(1.05)
        tab.save_value_button.click()
        self.assertIn("FRICTION=1.05", ini_path.read_text(encoding="utf-8"))
        self.assertEqual(len(list(ini_path.parent.glob("surfaces.ini.qm-*.bak"))), 1)
        self.window.nav_group.button(8).click()
        self.assertEqual(self.window.tabs.currentIndex(), 8)
        from PyQt6.QtCore import QUrl
        with mock.patch.object(main.QDesktopServices, "openUrl", return_value=True) as open_url:
            tab.open_ini_button.click()
        open_url.assert_called_once()
        self.assertEqual(open_url.call_args.args[0], QUrl.fromLocalFile(str(track / "club" / "data" / "surfaces.ini")))
        self.assertNotEqual(ini_path.read_bytes(), original)

        # Refrescar conserva el circuito recien instalado sin bloquear el usuario.
        second = self.tmp / "content" / "tracks" / "second_track"
        (second / "data").mkdir(parents=True)
        (second / "data" / "surfaces.ini").write_text("[SURFACE_0]\nFRICTION=0.9\n", encoding="utf-8")
        tab.refresh_button.click()
        self.assertEqual(tab.track_list.count(), 2)

    def test_asistencias_de_coche_se_muestran_y_se_guardan(self):
        self.select("ks_test_car")
        self.window.tabs.setCurrentWidget(self.window.aids_tab)
        self.assertEqual(self.window.aids_tab.overview.tiles["abs"].value_label.text(), "Compatible")
        self.window.aids_tab.tc_active.setChecked(True)
        self.assertIn("electronics.ini", self.window._car.dirty_files())  # noqa: SLF001
        self.window._save()  # noqa: SLF001
        self.assertIn("[TRACTION]", self.read("electronics.ini"))
        self.assertIn("ACTIVE=1", self.read("electronics.ini"))

    # ---------------------------------------------------------- idioma ingles
    def test_interfaz_en_ingles_se_construye_traducida(self):
        from quickmechanic import i18n

        i18n.set_language("en")
        self.addCleanup(i18n.set_language, "es")
        ventana = main.MainWindow(ac_root=self.tmp)
        self.addCleanup(ventana.deleteLater)
        from PyQt6.QtTest import QTest
        for _ in range(500):
            if ventana.car_list.isEnabled():
                break
            QTest.qWait(10)
        self.assertEqual(ventana.tabs.tabText(0), "Overview")
        self.assertEqual(ventana.tabs.tabText(2), "Gearbox")
        self.assertEqual(ventana.save_button.text(), "Save all")
        self.assertEqual(ventana.language_button.text(), "Language")
        self.assertIn("Search cars", ventana.search.placeholderText())
        # El estado del pie tambien se traduce aunque se componga con valores.
        self.assertIn("cars scanned", ventana.footer_status.text())
        self.assertNotIn("coches", ventana.footer_status.text())

    def test_selector_de_idioma_guarda_la_preferencia(self):
        from quickmechanic import i18n
        from quickmechanic.qt_i18n import QMessageBox

        self.addCleanup(i18n.set_language, "es")
        with mock.patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel
        ):
            self.window._set_language("en")  # noqa: SLF001
        self.assertEqual(i18n.get_language(), "en")
        self.settings_mock.assert_any_call("language", "en")
        # El aviso sale ya en el idioma nuevo (la interfaz se reconstruye al reiniciar).
        self.assertIn("Language saved", self.window.footer_status.text())

    def test_elegir_reiniciar_relanza_la_app_con_el_idioma_nuevo(self):
        from quickmechanic import i18n
        from quickmechanic.qt_i18n import QMessageBox

        self.addCleanup(i18n.set_language, "es")
        with (
            mock.patch.object(
                QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
            ),
            mock.patch.object(main, "restart_application", return_value=True) as relanzar,
        ):
            self.window._set_language("en")  # noqa: SLF001
        relanzar.assert_called_once()
        self.assertEqual(i18n.get_language(), "en")

    def test_relanzar_reutiliza_ejecutable_y_argumentos(self):
        import sys

        programa, argumentos = main.relaunch_command(["--ac-root", "C:\\AC", "--background"])
        self.assertEqual(programa, sys.executable)
        self.assertIn("--ac-root", argumentos)
        self.assertNotIn("--background", argumentos)
        self.assertNotIn("--selftest", main.relaunch_command(["--selftest"])[1])

    # ------------------------------------------------------- traccion total AWD
    def test_awd_solo_aparece_si_el_coche_declara_secciones(self):
        self.select("ks_test_car")
        self.assertTrue(self.window.gear_tab.awd_panel.isHidden())
        drivetrain = self.car_dir / "data" / "drivetrain.ini"
        drivetrain.write_text(
            drivetrain.read_text(encoding="utf-8")
            + "\n[AWD]\nFRONT_SHARE=40\nFRONT_DIFF_POWER=0.25\nREAR_DIFF_COAST=0.30\n",
            encoding="utf-8",
        )
        self.window._reload_current()  # noqa: SLF001
        panel = self.window.gear_tab
        self.assertFalse(panel.awd_panel.isHidden())
        campos = panel._awd_fields  # noqa: SLF001
        self.assertEqual(sorted(campos), [("AWD", "FRONT_DIFF_POWER"), ("AWD", "FRONT_SHARE"), ("AWD", "REAR_DIFF_COAST")])
        # los bloqueos se muestran en % aunque el fichero guarde fracciones
        self.assertEqual(campos[("AWD", "FRONT_DIFF_POWER")].value(), 25.0)
        campos[("AWD", "FRONT_SHARE")].setValue(55.0)
        self.assertIn("drivetrain.ini", self.window._car.dirty_files())  # noqa: SLF001
        self.window._save()  # noqa: SLF001
        guardado = self.read("drivetrain.ini")
        self.assertIn("FRONT_SHARE=55", guardado)
        self.assertNotIn("AWD2", guardado)


@unittest.skipUnless(GUI, "PyQt6 no esta disponible")
class PlaceholderTest(unittest.TestCase):
    """La imagen de relleno: se dibuja sin depender de que el coche traiga foto."""

    app = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_monograma(self):
        self.assertEqual(widgets.CarPreview._monogram("Nissan 350Z"), "NI")  # noqa: SLF001
        self.assertEqual(widgets.CarPreview._monogram("BMW M3"), "BM")  # noqa: SLF001
        self.assertEqual(widgets.CarPreview._monogram("ks_test_car"), "KT")  # noqa: SLF001
        self.assertEqual(widgets.CarPreview._monogram("ks_mazda_mx5_nd"), "KM")  # noqa: SLF001
        self.assertEqual(widgets.CarPreview._monogram(""), "AC")  # noqa: SLF001

    def test_marcador_sin_coche(self):
        preview = widgets.CarPreview()
        self.addCleanup(preview.deleteLater)
        preview.clear()
        self.assertEqual(preview.current_skin, "")
        self.assertEqual(preview.detail.text(), "")

    def test_carpeta_sin_skins_usa_el_marcador(self):
        tmp = Path(tempfile.mkdtemp(prefix="qm_ph_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        preview = widgets.CarPreview()
        self.addCleanup(preview.deleteLater)
        preview.load(tmp, title="Coche sin skins")
        self.assertEqual(preview.current_skin, "")
        self.assertEqual(preview.skin_count.text(), "")
        self.assertFalse(preview.skin_box.isEnabled())
        self.assertIn("Sin carpeta skins", preview.subtitle.text())


if __name__ == "__main__":
    unittest.main()
