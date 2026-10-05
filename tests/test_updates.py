"""Tests del aviso de versiones y de la descarga desde GitHub Releases.

Ninguna prueba sale a internet: la red se sustituye por un `fetch` falso.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from quickmechanic import updates

RELEASE_JSON = {
    "tag_name": "v0.3.0",
    "name": "Quick Mechanic 0.3.0",
    "html_url": "https://github.com/IraitzZZ/QuickMechanic/releases/tag/v0.3.0",
    "body": "Idioma, AWD y auto-actualizaciones.",
    "draft": False,
    "prerelease": False,
    "assets": [
        {"name": "notes.txt", "browser_download_url": "https://example.test/notes.txt", "size": 10},
        {"name": "Setup.zip", "browser_download_url": "https://example.test/Setup.zip", "size": 5},
        {"name": "Setup.exe", "browser_download_url": "https://example.test/Setup.exe", "size": 4},
    ],
}


def payload(**changes) -> bytes:
    data = dict(RELEASE_JSON)
    data.update(changes)
    return json.dumps(data).encode("utf-8")


class VersionTest(unittest.TestCase):
    def test_parse_version(self) -> None:
        self.assertEqual(updates.parse_version("v0.2.10"), (0, 2, 10))
        self.assertEqual(updates.parse_version("Quick Mechanic 1.0"), (1, 0))
        self.assertEqual(updates.parse_version("sin numeros"), ())
        self.assertEqual(updates.parse_version(None), ())

    def test_comparacion_de_versiones(self) -> None:
        self.assertTrue(updates.is_newer((0, 3), (0, 2, 9)))
        self.assertTrue(updates.is_newer((0, 2, 1), (0, 2)))
        self.assertFalse(updates.is_newer((0, 2, 0), (0, 2)))
        self.assertFalse(updates.is_newer((0, 1, 9), (0, 2)))


class CheckForUpdateTest(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls) -> None:
        # Un unico QApplication para toda la clase: crear y destruir uno por test
        # mientras hay hilos de Qt vivos termina en un aborto del proceso.
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_detecta_version_mas_nueva_y_sus_assets(self) -> None:
        info = updates.check_for_update("0.2.0", fetch=lambda url, timeout=6: payload())
        self.assertIsNotNone(info)
        self.assertEqual(info.tag, "v0.3.0")
        self.assertEqual(info.version, (0, 3, 0))
        self.assertEqual(info.page_url, RELEASE_JSON["html_url"])
        self.assertIn("auto-actualizaciones", info.notes)

    def test_prioriza_setup_exe_y_descarta_otros_formatos(self) -> None:
        info = updates.check_for_update("0.2.0", fetch=lambda url, timeout=6: payload())
        names = [asset.name for asset in info.assets]
        self.assertEqual(names, ["Setup.zip", "Setup.exe"])
        self.assertEqual(updates.asset_candidates(info)[0].name, "Setup.exe")

    def test_no_avisa_si_la_version_es_la_misma_o_mas_vieja(self) -> None:
        self.assertIsNone(updates.check_for_update("0.3.0", fetch=lambda url, timeout=6: payload()))
        self.assertIsNone(updates.check_for_update("0.3.1", fetch=lambda url, timeout=6: payload()))

    def test_draft_y_prerelease_no_se_ofrecen(self) -> None:
        for change in ({"draft": True}, {"prerelease": True}, {"tag_name": "sin-version"}):
            with self.subTest(change=change):
                self.assertIsNone(
                    updates.check_for_update("0.2.0", fetch=lambda url, timeout=6, c=change: payload(**c))
                )

    def test_404_sin_conexion_o_json_raro_no_lanzan_error(self) -> None:
        def boom(url, timeout=6):
            raise updates.urllib.error.HTTPError(url, 404, "Not Found", None, None)

        def offline(url, timeout=6):
            raise updates.urllib.error.URLError("sin internet")

        self.assertIsNone(updates.check_for_update("0.2.0", fetch=boom))
        self.assertIsNone(updates.check_for_update("0.2.0", fetch=offline))
        self.assertIsNone(updates.check_for_update("0.2.0", fetch=lambda url, timeout=6: b"<html>"))
        self.assertIsNone(updates.check_for_update("0.2.0", fetch=lambda url, timeout=6: payload(tag_name="", name="")))
        self.assertIsNone(
            updates.check_for_update("0.2.0", fetch=lambda url, timeout=6: (_ for _ in ()).throw(RuntimeError("boom")))
        )

    def test_assets_hostiles_no_se_ofrecen(self) -> None:
        travesia = payload(assets=[
            {"name": "../../evil.exe", "browser_download_url": "https://example.test/evil.exe", "size": 1},
            {"name": "Setup.exe", "browser_download_url": "file:///C:/Windows/System32/cmd.exe", "size": 1},
        ])
        info = updates.check_for_update("0.2.0", fetch=lambda url, timeout=6: travesia)
        self.assertEqual(info.assets, ())

    def test_worker_en_hilo_da_el_mismo_resultado(self) -> None:
        worker = updates.UpdateWorker("0.2.0", fetch=lambda url, timeout=6: payload())
        resultado = []
        worker.finished.connect(resultado.append)
        worker.run()
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0].tag, "v0.3.0")

    def test_start_worker_entrega_la_senal_desde_su_hilo(self) -> None:
        from PyQt6.QtTest import QTest

        worker = updates.UpdateWorker("0.2.0", fetch=lambda url, timeout=6: payload())
        recibido = []
        worker.finished.connect(recibido.append)
        hilo = updates.start_worker(worker)  # noqa: F841 (se mantiene vivo a proposito)
        for _ in range(300):
            if recibido:
                break
            QTest.qWait(10)
        self.assertEqual(len(recibido), 1)
        self.assertEqual(recibido[0].tag, "v0.3.0")
        self.assertTrue(hilo.wait(2000))

    def test_worker_sin_red_avisa_por_senal_failed_y_no_por_finished(self) -> None:
        def boom(url, timeout=6):
            raise RuntimeError("sin red")

        worker = updates.UpdateWorker("0.2.0", fetch=boom)
        resultados, fallos = [], []
        worker.finished.connect(resultados.append)
        worker.failed.connect(fallos.append)
        worker.run()
        self.assertEqual(resultados, [])
        self.assertEqual(fallos, ["sin red"])

    def test_error_http_se_resume_en_el_mensaje(self) -> None:
        def not_found(url, timeout=6):
            raise updates.urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))

        mensajes = []
        self.assertIsNone(
            updates.check_for_update("0.2.0", fetch=not_found, on_error=mensajes.append)
        )
        self.assertEqual(mensajes, ["HTTP 404"])

    def test_worker_avisa_si_falla_algo_inesperado(self) -> None:
        with mock.patch.object(updates, "check_for_update", side_effect=RuntimeError("boom")):
            worker = updates.UpdateWorker("0.2.0")
            fallos = []
            worker.failed.connect(fallos.append)
            worker.run()
        self.assertEqual(fallos, ["boom"])


class DownloadTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qm_upd_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.asset = updates.UpdateAsset(
            name="Setup.exe", url="https://example.test/Setup.exe", size=4
        )

    def test_descarga_a_la_carpeta_indicada(self) -> None:
        with mock.patch.object(updates.QDesktopServices, "openUrl") as open_url:
            path = updates.download_asset(self.asset, self.tmp, fetch=lambda url, timeout=60: b"data")
        self.assertEqual(path, self.tmp / "Setup.exe")
        self.assertEqual(path.read_bytes(), b"data")
        # Descargar nunca abre ni ejecuta el instalador por su cuenta.
        open_url.assert_not_called()

    def test_rechaza_extensiones_no_permitidas(self) -> None:
        raro = updates.UpdateAsset(name="script.bat", url="https://example.test/x.bat")
        with self.assertRaises(updates.UpdateError):
            updates.download_asset(raro, self.tmp, fetch=lambda url, timeout=60: b"x")

    def test_detecta_descargas_vacias_o_incompletas(self) -> None:
        with self.assertRaises(updates.UpdateError):
            updates.download_asset(self.asset, self.tmp, fetch=lambda url, timeout=60: b"")
        with self.assertRaises(updates.UpdateError):
            updates.download_asset(self.asset, self.tmp, fetch=lambda url, timeout=60: b"da")

    def test_fallo_de_red_no_deja_archivos_a_medias(self) -> None:
        def offline(url, timeout=60):
            raise updates.urllib.error.URLError("sin internet")

        with self.assertRaises(updates.UpdateError):
            updates.download_asset(self.asset, self.tmp, fetch=offline)
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_el_nombre_del_asset_no_escapa_de_la_carpeta(self) -> None:
        proxy = updates.UpdateAsset(name="evil.exe", url="https://example.test/evil.exe")
        path = updates.download_asset(proxy, self.tmp, fetch=lambda url, timeout=60: b"abcd")
        self.assertEqual(path.parent, self.tmp)

    def test_un_zip_de_release_deja_el_instalador_listo(self) -> None:
        import zipfile

        origen = self.tmp / "Setup.zip"
        with zipfile.ZipFile(origen, "w") as bundle:
            bundle.writestr("Setup.exe", b"instalador")
            bundle.writestr("LEEME.txt", "notas")
            bundle.writestr("carpeta/otro.txt", "mas")
        ruta = updates.extract_setup(origen)
        self.assertEqual(ruta, self.tmp / "Setup.exe")
        self.assertEqual(ruta.read_bytes(), b"instalador")
        self.assertTrue((self.tmp / "LEEME.txt").is_file())

    def test_un_zip_traviesso_se_rechaza_sin_escribir_fuera(self) -> None:
        import zipfile

        origen = self.tmp / "Hostil.zip"
        with zipfile.ZipFile(origen, "w") as bundle:
            bundle.writestr("../../evil.exe", b"rm -rf")
            bundle.writestr("/absoluto.exe", b"rm -rf")
            bundle.writestr("normal.txt", "ok")
        ruta = updates.extract_setup(origen)
        self.assertEqual(ruta, origen)  # sin instalador: se queda el ZIP
        self.assertFalse((self.tmp.parent / "evil.exe").exists())
        self.assertTrue((self.tmp / "normal.txt").is_file())

    def test_un_zip_sin_instalador_no_se_ejecuta(self) -> None:
        import zipfile
        from unittest import mock as _mock

        origen = self.tmp / "solo_notas.zip"
        with zipfile.ZipFile(origen, "w") as bundle:
            bundle.writestr("notas.md", "hola")
        with _mock.patch.object(updates.QDesktopServices, "openUrl") as abrir:
            ruta = updates.download_installer(
                updates.UpdateAsset("solo_notas.zip", "https://example.test/solo_notas.zip"),
                self.tmp,
                fetch=lambda url, timeout=60: origen.read_bytes(),
            )
        abrir.assert_not_called()
        self.assertEqual(ruta.suffix, ".zip")

    def test_worker_de_descarga_avisa_del_archivo_o_del_error(self):
        # El worker nunca escribe en la carpeta real del usuario durante los tests.
        listos, fallos = [], []
        with mock.patch.object(updates, "download_installer", return_value=self.tmp / "Setup.exe"):
            worker = updates.DownloadWorker(self.asset, fetch=lambda url, timeout=60: b"abcd")
            worker.finished.connect(listos.append)
            worker.failed.connect(fallos.append)
            worker.run()
        self.assertEqual(listos, [self.tmp / "Setup.exe"])
        self.assertEqual(fallos, [])

        def boom(url, timeout=60):
            raise updates.urllib.error.URLError("sin internet")

        worker = updates.DownloadWorker(self.asset, fetch=boom)
        worker.finished.connect(listos.append)
        worker.failed.connect(fallos.append)
        worker.run()
        self.assertEqual(len(fallos), 1)
        self.assertIn("sin internet", fallos[0])


class UpdateNoticeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from quickmechanic import i18n

        i18n.set_language("es")
        self.addCleanup(i18n.set_language, "es")
        self.notice = updates.UpdateNotice()
        self.addCleanup(self.notice.deleteLater)
        self.info = updates.UpdateInfo(
            tag="v0.3.0",
            version=(0, 3, 0),
            name="Quick Mechanic 0.3.0",
            notes="Idioma y AWD.",
            page_url=RELEASE_JSON["html_url"],
            assets=(updates.UpdateAsset("Setup.exe", "https://example.test/Setup.exe", 4),),
        )

    def test_aviso_persistente_con_botones(self) -> None:
        self.notice.show_available(self.info)
        self.assertFalse(self.notice.isHidden())
        self.assertIn("0.3.0", self.notice.message.text())
        self.assertEqual(self.notice.download_button.text(), "Descargar e instalar")
        self.assertTrue(self.notice.download_button.isEnabled())

    def test_aviso_traducido_al_ingles(self) -> None:
        from quickmechanic import i18n

        i18n.set_language("en")
        aviso = updates.UpdateNotice()
        self.addCleanup(aviso.deleteLater)
        aviso.show_available(self.info)
        self.assertIn("new version", aviso.message.text().lower())
        self.assertEqual(aviso.download_button.text(), "Download and install")

    def test_error_de_descarga_se_queda_en_el_aviso(self) -> None:
        self.notice.show_available(self.info)
        self.notice.show_error("sin internet")
        self.assertFalse(self.notice.isHidden())
        self.assertIn("sin internet", self.notice.detail.text())
        self.assertEqual(self.notice.download_button.text(), "Reintentar descarga")

    def test_descarga_terminada_ofrece_abrir_el_instalador(self) -> None:
        destino = Path(tempfile.gettempdir()) / "Setup.exe"
        self.notice.show_downloaded(destino)
        self.assertEqual(self.notice.downloaded_path, destino)
        self.assertEqual(self.notice.download_button.text(), "Abrir instalador")

    def test_zip_sin_instalador_ofrece_abrir_la_carpeta(self) -> None:
        destino = Path(tempfile.gettempdir()) / "Setup.zip"
        self.notice.show_downloaded(destino)
        self.assertEqual(self.notice.download_button.text(), "Abrir carpeta de descargas")
        with mock.patch.object(updates.QDesktopServices, "openUrl") as abrir:
            self.notice.launch_downloaded()
        abrir.assert_called_once()
        # Un ZIP sin instalador solo abre la carpeta que lo contiene.
        self.assertEqual(abrir.call_args.args[0].toLocalFile(), str(destino.parent))

    def test_cerrar_emite_aviso(self) -> None:
        avisos = []
        self.notice.dismissed.connect(lambda: avisos.append(True))
        self.notice.show_available(self.info)
        self.notice.dismiss_button.click()
        self.assertTrue(self.notice.isHidden())
        self.assertEqual(avisos, [True])

    def test_abrir_el_instalador_requiere_pulsarlo(self) -> None:
        self.notice.show_available(self.info)
        with (
            mock.patch.object(updates.QDesktopServices, "openUrl") as open_url,
            mock.patch.object(updates.QMessageBox, "information", return_value=None) as aviso,
        ):
            self.notice.launch_downloaded()
        # Sin descarga previa solo se avisa: nunca se ejecuta nada.
        open_url.assert_not_called()
        self.assertEqual(aviso.call_count, 1)
        self.assertIsNone(self.notice.downloaded_path)


if __name__ == "__main__":
    unittest.main()
