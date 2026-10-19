"""Firma de los ficheros que Quick Mechanic comparte (.qmsetup y perfiles .json).

Cada fichero exportado lleva una firma HMAC-SHA256 calculada sobre su contenido
(sin el propio campo de firma, con las claves ordenadas). Al importar, un fichero
sin firma o con una firma que no coincide se rechaza: detecta setups editados a
mano o creados fuera de la app.

Limite honesto: la clave viaja dentro del programa. Esto impide copias y
ediciones casuales, pero quien tenga el ejecutable puede extraer la clave.
"""
from __future__ import annotations

import hashlib
import hmac
import json

__all__ = ["SIGNATURE_FIELD", "sign_payload", "verify_payload"]

SIGNATURE_FIELD = "signature"
_KEY = bytes.fromhex("7f3a9c1e5b2d80f4a6c7e1d93b5a2f08c4e6d7b9a1f0e2c3d5b7a9f1e4c6d8a0")


def _digest(payload: dict) -> str:
    body = {key: value for key, value in payload.items() if key != SIGNATURE_FIELD}
    message = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(_KEY, message.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_payload(payload: dict) -> dict:
    """Devuelve una copia del contenido con su firma añadida."""
    return {**payload, SIGNATURE_FIELD: _digest(payload)}


def verify_payload(payload: dict) -> bool:
    """True solo si la firma existe y coincide con el contenido."""
    given = payload.get(SIGNATURE_FIELD)
    if not isinstance(given, str):
        return False
    return hmac.compare_digest(given, _digest(payload))
