"""Tests del explorador de circuitos: descubrimiento seguro y solo lectura."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from quickmechanic import tracks


class TrackScannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="qm_tracks_")
        self.addCleanup(self.temp.cleanup)
        self.ac_root = Path(self.temp.name)
        self.tracks_root = self.ac_root / "content" / "tracks"
        self.tracks_root.mkdir(parents=True)

    def test_discovers_root_track_multiple_layouts_metadata_and_ini(self) -> None:
        track = self.tracks_root / "sample_track"
        (track / "ui").mkdir(parents=True)
        # Assetto Corsa mods commonly leave trailing commas in UI JSON; commas in
        # strings must be retained while the trailing comma is tolerated.
        (track / "ui" / "ui_track.json").write_text(
            '{"name":"Track, One", "country":"Spain", "author":"A, B",}',
            encoding="utf-8",
        )
        (track / "models_club.ini").write_text("[MODEL_0]\nFILE=club.kn5\n", encoding="utf-8")
        (track / "club" / "data").mkdir(parents=True)
        (track / "club" / "data" / "surfaces.ini").write_text(
            "[SURFACE_0]\nKEY=ROAD\nFRICTION=0.95 ; grip\n", encoding="utf-8"
        )
        (track / "ui" / "club").mkdir()
        (track / "ui" / "club" / "ui_track.json").write_text(
            '{"name":"Club layout", "pitboxes":"24",}', encoding="utf-8"
        )

        found = tracks.scan_tracks(self.ac_root)
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertEqual(item.display_name, "Track, One")
        self.assertEqual(item.country, "Spain")
        self.assertEqual(item.metadata["author"], "A, B")
        self.assertEqual(len(item.layouts), 1)
        layout = item.layouts[0]
        self.assertEqual(layout.name, "club")
        self.assertEqual(layout.display_name, "Club layout")
        self.assertIsNotNone(layout.model_file)
        self.assertEqual(layout.data_dir, track / "club" / "data")

        entries = tracks.read_ini(layout.data_dir / "surfaces.ini", track)
        self.assertEqual([(row.section, row.key, row.value) for row in entries], [
            ("SURFACE_0", "KEY", "ROAD"), ("SURFACE_0", "FRICTION", "0.95")
        ])

    def test_scans_single_layout_track_without_inventing_layout(self) -> None:
        track = self.tracks_root / "single"
        (track / "ui").mkdir(parents=True)
        (track / "data").mkdir()
        (track / "ui" / "ui_track.json").write_text(json.dumps({"name": "Solo"}), encoding="utf-8")
        result = tracks.scan_tracks(self.ac_root)[0]
        self.assertEqual(result.display_name, "Solo")
        self.assertEqual(result.layouts, ())
        self.assertEqual(result.data_dir, track / "data")

    def test_malformed_metadata_is_reported_not_rewritten(self) -> None:
        track = self.tracks_root / "broken"
        (track / "ui").mkdir(parents=True)
        ui = track / "ui" / "ui_track.json"
        original = "{ this is not JSON"
        ui.write_text(original, encoding="utf-8")
        result = tracks.scan_tracks(self.ac_root)[0]
        self.assertTrue(result.metadata_error)
        self.assertEqual(ui.read_text(encoding="utf-8"), original)

    def test_edits_existing_numeric_ini_key_with_backup_and_stale_file_protection(self) -> None:
        track_folder = self.tracks_root / "editable"
        data = track_folder / "data"
        data.mkdir(parents=True)
        ini = data / "surfaces.ini"
        initial = "[SURFACE_0]\nKEY=ROAD\nFRICTION=0.90 ; grip\n"
        ini.write_text(initial, encoding="utf-8")
        track = tracks.scan_tracks(self.ac_root)[0]
        snapshot = hashlib.sha256(ini.read_bytes()).hexdigest()

        tracks.edit_ini_number(track, ini, "SURFACE_0", "FRICTION", 1.05, snapshot)
        self.assertIn("FRICTION=1.05 ; grip", ini.read_text(encoding="utf-8"))
        backups = list(data.glob("surfaces.ini.qm-*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), initial)

        with self.assertRaises(tracks.TrackError):
            tracks.edit_ini_number(track, ini, "SURFACE_0", "FRICTION", 1.1, snapshot)
        self.assertIn("FRICTION=1.05", ini.read_text(encoding="utf-8"))
        with self.assertRaises(tracks.TrackError):
            tracks.edit_ini_number(
                track, ini, "SURFACE_0", "UNKNOWN", 2.0,
                hashlib.sha256(ini.read_bytes()).hexdigest(),
            )
        with self.assertRaises(tracks.TrackError):
            tracks.edit_ini_number(
                track, ini, "SURFACE_0", "FRICTION", float("nan"),
                hashlib.sha256(ini.read_bytes()).hexdigest(),
            )

    def test_rejects_ini_outside_track_and_symlinks(self) -> None:
        track = self.tracks_root / "safe"
        data = track / "data"
        data.mkdir(parents=True)
        ini = data / "surfaces.ini"
        ini.write_text("[SURFACE_0]\nKEY=ROAD\n", encoding="utf-8")
        outside = self.ac_root / "outside.ini"
        outside.write_text("[X]\nK=V\n", encoding="utf-8")
        with self.assertRaises(tracks.TrackError):
            tracks.read_ini(outside, track)
        try:
            link = data / "linked.ini"
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("el sistema de archivos no permite enlaces simbolicos")
        with self.assertRaises(tracks.TrackError):
            tracks.read_ini(link, track)

    def test_rejects_symlinked_track_root(self) -> None:
        external = Path(self.temp.name) / "external"
        (external / "content" / "tracks").mkdir(parents=True)
        linked_root = self.ac_root / "linked_ac"
        try:
            linked_root.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("el sistema de archivos no permite enlaces simbolicos")
        with self.assertRaises(tracks.TrackError):
            tracks.scan_tracks(linked_root)


if __name__ == "__main__":
    unittest.main()
