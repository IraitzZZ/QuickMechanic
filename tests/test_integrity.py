"""Pruebas de la firma de ficheros compartidos."""
from __future__ import annotations

import unittest

from quickmechanic.integrity import SIGNATURE_FIELD, sign_payload, verify_payload


class IntegrityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {"kind": "setup", "version": 1, "name": "Monza", "setup": {"a": 1, "b": [2, 3]}}

    def test_firma_valida(self):
        signed = sign_payload(self.payload)
        self.assertIn(SIGNATURE_FIELD, signed)
        self.assertTrue(verify_payload(signed))

    def test_no_depende_del_orden_de_las_claves(self):
        signed = sign_payload(self.payload)
        reordered = dict(reversed(list(signed.items())))
        self.assertTrue(verify_payload(reordered))

    def test_detecta_modificaciones(self):
        signed = sign_payload(self.payload)
        signed["setup"]["a"] = 2
        self.assertFalse(verify_payload(signed))

    def test_rechaza_sin_firma_o_firma_invalida(self):
        self.assertFalse(verify_payload(self.payload))
        self.assertFalse(verify_payload({**self.payload, SIGNATURE_FIELD: 123}))
        self.assertFalse(verify_payload({**self.payload, SIGNATURE_FIELD: "0" * 64}))


if __name__ == "__main__":
    unittest.main()
