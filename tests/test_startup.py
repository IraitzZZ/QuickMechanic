"""Pruebas aisladas de inicio automático, sin modificar el registro real."""
from __future__ import annotations

import sys
import unittest
from unittest import mock

from quickmechanic import startup


class StartupTest(unittest.TestCase):
    def test_rechaza_integracion_fuera_de_windows(self):
        with mock.patch.object(startup.os, "name", "posix"):
            ok, message = startup.set_windows_startup(True)
        self.assertFalse(ok)
        self.assertIn("Windows", message)

    def test_comando_de_inicio_incluye_modo_background(self):
        with (
            mock.patch.object(startup, "sys") as system,
            mock.patch.object(startup.os, "name", "nt"),
        ):
            system.frozen = True
            system.executable = r"C:\Quick Mechanic\QuickMechanic.exe"
            command = startup.startup_command()
        self.assertIn("--background", command)
        self.assertIn("QuickMechanic.exe", command)

    def test_winreg_usa_solo_hkcu_y_quita_valor_existente(self):
        fake = mock.Mock()
        fake.HKEY_CURRENT_USER = object()
        fake.REG_SZ = 1
        fake.KEY_SET_VALUE = 2
        fake.CreateKeyEx.return_value.__enter__ = mock.Mock(return_value=object())
        fake.CreateKeyEx.return_value.__exit__ = mock.Mock(return_value=False)
        with mock.patch.object(startup.os, "name", "nt"):
            ok, _ = startup.set_windows_startup(
                True,
                registry=fake,
                command_factory=lambda: '"qm.exe" --background',
            )
            self.assertTrue(ok)
            fake.SetValueEx.assert_called_once()
            self.assertIs(fake.CreateKeyEx.call_args.args[0], fake.HKEY_CURRENT_USER)
            fake.DeleteValue.side_effect = FileNotFoundError
            ok, _ = startup.set_windows_startup(False, registry=fake)
            self.assertTrue(ok)
            fake.DeleteValue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
