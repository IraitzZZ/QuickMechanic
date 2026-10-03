"""Tests de la lectura de skins, previsualizaciones y ficha del coche.

Las imagenes se generan al vuelo (ver tests/support.py), asi que no hace falta
guardar binarios en el repositorio ni tener Qt instalado.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from quickmechanic import ac_scanner, skins
from tests.support import FIXTURES, TEST_CAR, make_skin, write_png


class SkinDiscoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qm_skins_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.car = self.tmp / "car"
        self.car.mkdir(parents=True)

    # ------------------------------------------------------------------ vacios
    def test_coche_sin_carpeta_skins(self):
        self.assertEqual(skins.list_skins(self.car), [])
        self.assertIsNone(skins.find_preview(self.car))

    def test_preview_de_carpeta_inexistente(self):
        self.assertIsNone(skins.find_preview(self.tmp / "no_existe"))

    # ---------------------------------------------------------------- previews
    def test_prefiere_preview_jpg_sobre_otros(self):
        write_png(self.car / "preview.png")
        (self.car / "preview.jpg").write_bytes(b"\xff\xd8\xff\xe0 foto de verdad")
        self.assertEqual(skins.find_preview(self.car).name, "preview.jpg")

    def test_ignora_las_copias_de_la_preview(self):
        write_png(self.car / "preview_original.jpg")
        self.assertIsNone(skins.find_preview(self.car))

    def test_usa_cualquier_preview_como_ultimo_recurso(self):
        write_png(self.car / "preview_2024.png")
        self.assertEqual(skins.find_preview(self.car).name, "preview_2024.png")

    def test_ignora_ficheros_que_no_son_imagen(self):
        (self.car / "preview.txt").write_text("no soy una imagen", encoding="utf-8")
        self.assertIsNone(skins.find_preview(self.car))

    # ------------------------------------------------------------------- skins
    def test_lista_de_skins_con_nombre_y_detalles(self):
        make_skin(self.car, "default", display_name="Default")
        make_skin(
            self.car,
            "Quick_Orange",
            display_name="Quick Orange",
            number="27",
            team="QM Racing",
            priority=2,
        )
        # la carpeta skins/ con un fichero suelto no debe romper nada
        (self.car / "skins" / "leeme.txt").write_text("hola", encoding="utf-8")
        write_png(self.car / "skins" / "Sin_Preview" / "livery.png")
        (self.car / "skins" / "Sin_Preview" / "ui_skin.json").write_text(
            json.dumps({"skinname": "Sin Preview"}), encoding="utf-8"
        )

        found = skins.list_skins(self.car)
        self.assertEqual(
            [skin.name for skin in found], ["Quick_Orange", "default", "Sin_Preview"]
        )
        orange = found[0]
        self.assertEqual(orange.label, "Quick Orange")
        self.assertTrue(orange.has_preview)
        self.assertEqual(orange.preview.name, "preview.png")
        self.assertEqual(orange.details, ["QM Racing", "#27"])
        self.assertEqual(orange.priority, 2)

        self.assertFalse(found[2].has_preview)
        self.assertIsNone(found[2].preview)

    def test_skin_sin_ui_skin_json(self):
        folder = self.car / "skins" / "Solo_Pintura"
        write_png(folder / "preview.png")
        found = skins.list_skins(self.car)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].label, "Solo_Pintura")
        self.assertEqual(found[0].details, [])
        self.assertTrue(found[0].has_preview)

    def test_ui_skin_json_roto_no_rompe(self):
        folder = self.car / "skins" / "Rota"
        write_png(folder / "preview.png")
        (folder / "ui_skin.json").write_text("{ esto no es json", encoding="utf-8")
        found = skins.list_skins(self.car)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "Rota")

    # -------------------------------------------------------------- ficha/badge
    def test_ficha_del_coche_desde_ui_car_json(self):
        car = FIXTURES / "content" / "cars" / "ks_test_car"
        meta = skins.read_car_meta(car)
        self.assertEqual(meta.name, "Quick Mechanic Test Car")
        self.assertEqual(meta.brand, "Quick Mechanic")
        self.assertEqual(meta.car_class, "race")
        self.assertEqual(meta.subtitle, "Quick Mechanic · RACE")
        spec_keys = [label for label, _value in meta.specs]
        self.assertIn("Potencia", spec_keys)
        self.assertIn("Peso", spec_keys)
        self.assertEqual(meta.spec("potencia"), "195bhp")

    def test_ficha_vacia_si_no_hay_ui_car_json(self):
        meta = skins.read_car_meta(self.car)
        self.assertEqual(meta.name, "car")
        self.assertEqual(meta.specs, [])
        self.assertEqual(meta.subtitle, "")

    def test_nombre_en_varios_idiomas(self):
        ui = self.car / "ui"
        ui.mkdir(parents=True)
        (ui / "ui_car.json").write_text(
            json.dumps({"name": {"ita": "Panda", "eng": "Panda 4x4"}}), encoding="utf-8"
        )
        self.assertEqual(skins.read_car_meta(self.car).name, "Panda 4x4")

    def test_escudo_del_coche(self):
        ui = self.car / "ui"
        ui.mkdir(parents=True)
        write_png(ui / "badge.png")
        self.assertEqual(skins.car_badge(self.car).name, "badge.png")

    def test_strip_html_de_la_descripcion(self):
        text = skins.strip_html("Linea uno<br><br>Linea &amp; dos <b>gras</b>")
        self.assertEqual(text, "Linea uno\n\nLinea & dos gras")


class RealSkinsTest(unittest.TestCase):
    """Comprueba el formato real de la instalacion de AC (solo lectura)."""

    AC_ROOT = ac_scanner.find_ac_root()

    @unittest.skipIf(AC_ROOT is None, "Assetto Corsa no esta instalado")
    def test_los_coches_reales_traen_preview(self):
        cars = ac_scanner.list_cars(self.AC_ROOT)
        self.assertTrue(cars)

        checked = 0
        with_preview = 0
        duplicates = []
        for car in cars[:120]:
            found = skins.list_skins(car.folder)
            if not found:
                continue
            checked += 1
            if any(skin.has_preview for skin in found):
                with_preview += 1
            if len(found) != len({skin.name for skin in found}):
                duplicates.append(car.name)

        self.assertGreater(checked, 0, "ningun coche con carpeta skins/")
        self.assertEqual(duplicates, [])
        self.assertGreater(
            with_preview / checked,
            0.9,
            f"solo {with_preview} de {checked} coches con skins traen preview",
        )

    @unittest.skipIf(AC_ROOT is None, "Assetto Corsa no esta instalado")
    def test_la_preview_real_se_puede_leer(self):
        """La imagen que se enseña en el panel existe y tiene bytes de verdad."""
        cars = ac_scanner.list_cars(self.AC_ROOT)
        for car in cars[:200]:
            for skin in skins.list_skins(car.folder):
                if skin.preview is None:
                    continue
                self.assertTrue(skin.preview.is_file())
                self.assertGreater(skin.preview.stat().st_size, 1024)
                self.assertIn(skin.preview.suffix.lower(), skins.IMAGE_SUFFIXES)
                return
        self.skipTest("no se ha encontrado ninguna preview real")

    def test_el_coche_de_ejemplo_del_usuario(self):
        """D:\...\content\cars\350z_tea_hair\skins\Tea_hair (si esta instalado)."""
        if self.AC_ROOT is None:
            self.skipTest("Assetto Corsa no esta instalado")
        folder = self.AC_ROOT / "content" / "cars" / "350z_tea_hair"
        if not folder.is_dir():
            self.skipTest("el 350z del ejemplo no esta instalado")
        found = skins.list_skins(folder)
        self.assertEqual([skin.name for skin in found], ["Tea_hair"])
        self.assertEqual(found[0].label, "Tea Hair")
        self.assertIsNotNone(found[0].preview)
        self.assertEqual(found[0].preview.name, "preview.jpg")


if __name__ == "__main__":
    unittest.main()
