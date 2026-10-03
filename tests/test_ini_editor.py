"""Tests del editor de .ini: leer, editar y guardar sin romper el archivo."""
from __future__ import annotations

import unittest

from quickmechanic import ini_editor
from tests.support import TEST_CAR_DATA, TempCarMixin


class ACIniReadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ini = ini_editor.ACIni(TEST_CAR_DATA / "engine.ini")

    def test_valores_con_comentario_al_final(self):
        self.assertEqual(self.ini.get_int("ENGINE_DATA", "LIMITER"), 6500)
        self.assertAlmostEqual(self.ini.get_float("ENGINE_DATA", "INERTIA"), 0.120, places=3)

    def test_lectura_del_turbo(self):
        self.assertTrue(self.ini.has_section("TURBO_0"))
        self.assertAlmostEqual(self.ini.get_float("TURBO_0", "MAX_BOOST"), 1.38, places=2)
        self.assertEqual(self.ini.get_float("DAMAGE", "TURBO_BOOST_THRESHOLD"), 1.40)

    def test_valores_separados_por_comas(self):
        car_ini = ini_editor.ACIni(TEST_CAR_DATA / "car.ini")
        self.assertEqual(car_ini.get_list("BASIC", "INERTIA"), [1.6, 1.30, 4.02])
        self.assertEqual(car_ini.get_int("BASIC", "TOTALMASS"), 1050)

    def test_mayusculas_y_minusculas(self):
        self.assertEqual(self.ini.get("engine_data", "limiter"), "6500")

    def test_clave_inexistente_devuelve_el_valor_por_defecto(self):
        self.assertFalse(self.ini.has("ENGINE_DATA", "NO_EXISTE"))
        self.assertEqual(self.ini.get_int("ENGINE_DATA", "NO_EXISTE", 4242), 4242)

    def test_secciones_y_claves(self):
        self.assertIn("ENGINE_DATA", self.ini.sections())
        self.assertIn("LIMITER", self.ini.keys("ENGINE_DATA"))


class ACIniWriteTest(TempCarMixin):
    def test_guarda_solo_la_clave_tocada(self):
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.set_value("ENGINE_DATA", "LIMITER", 7200)
        self.assertTrue(ini.save())

        text = self.read("engine.ini")
        self.assertIn("LIMITER=7200", text)
        # el comentario de la linea se mantiene
        self.assertIn("LIMITER=7200\t\t\t\t\t; engine rev limiter", text)
        # y el resto del archivo sigue igual
        self.assertIn("MAX_BOOST=1.38", text)
        self.assertNotIn("COAST_CURVE=FROM_COAST_REF ; coast curve", text)

    def test_no_se_pierden_comentarios_ni_lineas(self):
        before_comments = self.comments_in("engine.ini")
        before_lines = self.read("engine.ini").splitlines()
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.set_value("ENGINE_DATA", "INERTIA", 0.2)
        ini.set_value("TURBO_0", "MAX_BOOST", 1.1)
        ini.save()
        self.assertEqual(self.comments_in("engine.ini"), before_comments)
        self.assertEqual(len(self.read("engine.ini").splitlines()), len(before_lines))

    def test_copia_de_seguridad_con_el_original(self):
        original = self.read("engine.ini")
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.set_value("ENGINE_DATA", "LIMITER", 7000)
        ini.save()
        backup = self.data_dir / "engine.ini.bak"
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_text(encoding="utf-8", errors="replace"), original)

        # el .bak no se sobrescribe en el segundo guardado
        ini.set_value("ENGINE_DATA", "LIMITER", 7100)
        ini.save()
        self.assertEqual(backup.read_text(encoding="utf-8", errors="replace"), original)

    def test_clave_nueva_dentro_de_su_seccion(self):
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.set_value("ENGINE_DATA", "NUEVA_CLAVE", 5)
        ini.save()
        text = self.read("engine.ini")
        self.assertIn("NUEVA_CLAVE=5", text)
        position = text.index("NUEVA_CLAVE=5")
        self.assertLess(position, text.index("[COAST_REF]"))
        self.assertGreater(position, text.index("[ENGINE_DATA]"))

    def test_seccion_nueva_al_final(self):
        ini = ini_editor.ACIni(self.data_dir / "drivetrain.ini")
        ini.set_value("NUEVA_SECCION", "VALOR", 1.5)
        ini.save()
        text = self.read("drivetrain.ini")
        self.assertIn("[NUEVA_SECCION]", text)
        self.assertIn("VALOR=1.5", text)
        self.assertLess(text.index("[NUEVA_SECCION]"), text.index("VALOR=1.5"))

    def test_quitar_clave_la_comenta(self):
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.remove_key("TURBO_0", "MAX_BOOST")
        ini.save()
        text = self.read("engine.ini")
        self.assertNotIn("\nMAX_BOOST=", text)
        self.assertIn(";MAX_BOOST=1.38", text)

    def test_valor_igual_no_es_un_cambio(self):
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.set_value("ENGINE_DATA", "LIMITER", 6500)
        self.assertFalse(ini.changed)
        self.assertIsNone(ini.save())

    def test_volver_al_valor_original_cancela_el_cambio(self):
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.set_value("ENGINE_DATA", "LIMITER", 8000)
        self.assertTrue(ini.changed)
        ini.set_value("ENGINE_DATA", "LIMITER", 6500)
        self.assertFalse(ini.changed)

    def test_fichero_nuevo_se_crea(self):
        target = self.data_dir / "nuevo.ini"
        ini = ini_editor.ACIni(target)
        ini.set_value("DATA", "VALOR", 3)
        ini.save()
        self.assertTrue(target.is_file())
        self.assertIn("[DATA]", target.read_text(encoding="utf-8"))
        self.assertIn("VALOR=3", target.read_text(encoding="utf-8"))

    def test_finales_de_linea_crlf_se_mantienen(self):
        target = self.data_dir / "crlf.ini"
        target.write_bytes(b"[DATA]\r\nVALOR=1\r\n")
        ini = ini_editor.ACIni(target)
        ini.set_value("DATA", "VALOR", 2)
        ini.save()
        raw = target.read_bytes()
        self.assertIn(b"\r\n", raw)
        self.assertEqual(raw.replace(b"\r\n", b"").count(b"\n"), 0)
        self.assertIn(b"VALOR=2", raw)

    def test_bytes_no_utf8_no_se_corrompen(self):
        target = self.data_dir / "raro.ini"
        target.write_bytes(b"[INFO]\r\nNAME=coche\xe7\xe9\r\n")
        ini = ini_editor.ACIni(target)
        ini.set_value("INFO", "NAME", "coche ok")
        ini.save()
        raw = target.read_bytes()
        self.assertIn(b"coche ok", raw)

    def test_diff_lista_los_cambios(self):
        ini = ini_editor.ACIni(self.data_dir / "engine.ini")
        ini.set_value("ENGINE_DATA", "LIMITER", 7000)
        diff = ini.diff()
        self.assertEqual(len(diff), 1)
        self.assertEqual(diff[0][0], "ENGINE_DATA")
        self.assertEqual(diff[0][1], "LIMITER")
        self.assertEqual(diff[0][2], "6500")
        self.assertEqual(diff[0][3], "7000")


class UiCarNameTest(unittest.TestCase):
    def test_quita_los_placeholders_de_porcentaje(self):
        from quickmechanic import ini_editor as editor

        path = TEST_CAR_DATA.parent / "ui" / "ui_car.json"
        self.assertEqual(editor.read_ui_car_name(path), "Quick Mechanic Test Car")
        self.assertIsNone(editor.read_ui_car_name(path.with_name("no_existe.json")))


if __name__ == "__main__":
    unittest.main()
