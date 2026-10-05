"""Tests del idioma: tabla de traducciones, cobertura y cambio en caliente."""
from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from quickmechanic import i18n, locales


class TranslatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(i18n.set_language, "es")
        i18n.set_language("es")

    def test_es_devuelve_el_texto_original(self) -> None:
        self.assertEqual(i18n.translate("Guardar todo"), "Guardar todo")
        self.assertEqual(i18n.tr("Guardar todo"), "Guardar todo")

    def test_en_traduce_frases_completas(self) -> None:
        i18n.set_language("en")
        self.assertEqual(i18n.translate("Guardar todo"), "Save all")
        self.assertEqual(i18n.translate("Caja de cambios"), "Gearbox")

    def test_en_traduce_mayusculas_de_los_titulos(self) -> None:
        i18n.set_language("en")
        self.assertEqual(i18n.translate("MARCHAS"), "GEARS")
        self.assertEqual(i18n.translate("COLECCIÓN DE VEHÍCULOS"), "CAR COLLECTION")

    def test_en_traduce_mensajes_con_valores(self) -> None:
        i18n.set_language("en")
        self.assertEqual(i18n.translate("Biblioteca lista · 12 coches revisados"), "Library ready · 12 cars scanned")
        self.assertEqual(i18n.translate("5 marchas"), "5 gears")
        self.assertEqual(i18n.translate("Guardar (3)"), "Save (3)")

    def test_texto_desconocido_o_datos_no_se_tocan(self) -> None:
        i18n.set_language("en")
        for text in ("ks_mazda_mx5", "engine.ini", "RWD", "3.55", "/ruta/del/coche"):
            self.assertEqual(i18n.translate(text), text)

    def test_tr_formatea_con_argumentos(self) -> None:
        i18n.set_language("en")
        self.assertEqual(i18n.tr("Guardar ({})", 7), "Save (7)")
        self.assertEqual(i18n.tr("Texto sin traducir: {}", 3), "Texto sin traducir: 3")

    def test_codigo_desconocido_vuelve_al_español(self) -> None:
        self.assertEqual(i18n.set_language("de"), "es")
        self.assertEqual(i18n.get_language(), "es")

    def test_idioma_se_guarda_con_persistencia(self) -> None:
        with mock.patch.object(i18n.settings, "set_value") as writer:
            i18n.set_language("en", persist=True)
        writer.assert_called_once_with("language", "en")

    def test_idioma_guardado_se_lee_de_settings(self) -> None:
        with mock.patch.object(i18n.settings, "get", return_value="en"):
            self.assertEqual(i18n.load_saved_language(), "en")
        self.assertEqual(i18n.load_saved_language({"language": "EN"}), "en")
        self.assertEqual(i18n.load_saved_language({}), "es")

    def test_etiquetas_de_idioma_legibles(self) -> None:
        self.assertEqual(i18n.language_label("es"), "Español")
        self.assertEqual(i18n.language_label("en"), "English")


class TranslationTableTest(unittest.TestCase):
    def test_no_hay_traducciones_vacias_ni_repetidas(self) -> None:
        for source, target in locales.EN_EXACT.items():
            self.assertTrue(source.strip(), "clave vacia en la tabla")
            self.assertTrue(target.strip(), f"traduccion vacia para {source!r}")
        for source, target in locales.EN_TEMPLATES.items():
            self.assertEqual(
                source.count("{}"), target.count("{}"),
                f"numero de huecos distinto en {source!r}",
            )

    def test_las_plantillas_no_rompen_textos_con_llaves(self) -> None:
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, "es")
        self.assertEqual(i18n.translate("{raro} 3 coches revisados"), "{raro} 3 coches revisados")

    def test_lista_de_ignorados_no_es_traducible(self) -> None:
        for token in locales.UI_IGNORED:
            self.assertNotIn(token, locales.EN_EXACT, f"{token!r} no deberia traducirse")


class CoverageTest(unittest.TestCase):
    """La interfaz entera tiene que estar en la tabla: si se anade texto nuevo
    en español a un modulo visible, este test falla y dice cual falta."""

    def test_toda_la_interfaz_esta_traducida(self) -> None:
        missing = i18n.scan_missing_translations()
        if missing:
            detalle = "\n".join(f"  {module}: {text}" for module, text in missing)
            self.fail(
                "Sin traduccion en quickmechanic/locales.py "
                f"(o anadelos a UI_IGNORED si son identificadores):\n{detalle}"
            )


if __name__ == "__main__":
    unittest.main()
