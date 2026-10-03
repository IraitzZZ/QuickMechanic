"""Pruebas de descubrimiento local de Content Manager."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from quickmechanic import content_manager


class ContentManagerDiscoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="qm_cm_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executable = self.root / "Content Manager.exe"
        self.executable.write_bytes(b"test")

    def test_finds_configured_executable_first(self):
        with mock.patch.object(content_manager, "_registry_paths", return_value=[]):
            self.assertEqual(content_manager.find_executable(self.executable), self.executable)

    def test_default_path_is_the_requested_cm_location(self):
        self.assertEqual(str(content_manager.DEFAULT_PATH), r"C:\latest\Content Manager.exe")

    def test_rejects_missing_path_before_launch(self):
        missing = self.root / "missing.exe"
        with self.assertRaises(FileNotFoundError):
            content_manager.launch(missing)

    def test_launch_uses_selected_program_path(self):
        with mock.patch.object(content_manager.subprocess, "Popen") as popen:
            content_manager.launch(self.executable)
        args, kwargs = popen.call_args
        self.assertEqual(args[0], [str(self.executable)])
        self.assertEqual(kwargs["cwd"], str(self.root))


if __name__ == "__main__":
    unittest.main()
