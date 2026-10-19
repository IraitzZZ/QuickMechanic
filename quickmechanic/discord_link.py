"""Acceso a Quick Mechanic según la membresía del servidor oficial de Discord.

El Worker de Freebuff (discord-service) es la única autoridad: canjea el código
OAuth2, comprueba que la cuenta pertenece al servidor y emite una sesión opaca
y revocable. La app solo guarda ese token; nunca un ID, un nombre ni un
«verificado = true» como prueba. Cada arranque y cada revalidación consultan
al servidor. El Client Secret de Discord no sale nunca del Worker.
"""

from __future__ import annotations

import html
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse

from . import __version__, settings

SERVICE_URL = "https://site-29d5890e08c8423e8e95673bd568debd.freebuff.page"
GUILD_ID = "1389601848591253566"
INVITE_URL = "https://discord.gg/pWE5yEKexW"
AVATAR_PREFIX = "https://cdn.discordapp.com/"
SESSION_FILE = "discord_session.json"
LEGACY_SETTINGS_KEY = "discord_account"  # formato anterior, confiaba en datos locales
HTTP_TIMEOUT = 10.0
# Cloudflare bloquea (error 1010) el User-Agent por defecto de urllib ("Python-urllib/x.y").
# Sin un User-Agent propio, el Worker responde 403 y la app muestra "verificación fallida".
USER_AGENT = f"QuickMechanic/{__version__}"
LOGIN_TIMEOUT = 300.0
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43,64}$")
_MAX_BODY = 16_384

_MESSAGES = {
    "denied": "Cancelaste la autorización en Discord.",
    "not_member": "Necesitas pertenecer al servidor oficial de Quick Mechanic.",
    "not_configured": "El servicio de acceso no está disponible ahora mismo.",
    "timeout": "No llegó la respuesta de Discord a tiempo. Vuelve a intentarlo.",
    "network": "No se pudo conectar. Revisa tu conexión a internet.",
    "unavailable": "Discord o el servicio de acceso no están disponibles ahora mismo.",
    "session_invalid": "Tu sesión ha caducado. Vuelve a conectar Discord.",
    "ticket_invalid": "La autorización ya no es válida. Vuelve a intentarlo.",
    "token_failed": "No se pudo completar la verificación. Vuelve a intentarlo.",
    "storage": "No se pudo guardar la sesión en este equipo.",
}


class Status(str, Enum):
    NOT_SIGNED_IN = "not_signed_in"  # no hay sesión guardada
    GRANTED = "granted"  # el servidor confirma la membresía ahora mismo
    NOT_MEMBER = "not_member"  # el servidor confirma que no es miembro
    SESSION_EXPIRED = "session_expired"  # sesión revocada o caducada
    UNAVAILABLE = "unavailable"  # no se pudo consultar: no es lo mismo que no ser miembro
    FAILED = "failed"  # el inicio de sesión no llegó a completarse


@dataclass(frozen=True)
class Access:
    status: Status
    user_id: str = ""
    name: str = ""
    avatar_url: str = ""
    verified_at: int = 0  # milisegundos desde epoch, según el servidor
    error: str = ""  # código corto; el texto para el usuario sale de error_message()

    @property
    def granted(self) -> bool:
        return self.status is Status.GRANTED


class LoginError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _Unreachable(Exception):
    """No hubo respuesta HTTP: red, DNS o tiempo agotado."""


def error_message(code: str) -> str:
    return _MESSAGES.get(code, "No se pudo completar la verificación. Vuelve a intentarlo.")


def _send(method: str, url: str, *, headers: dict, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(_MAX_BODY)
    except urllib.error.HTTPError as error:
        try:
            raw = error.read(_MAX_BODY)
        except OSError:
            raw = b""
        return error.code, raw
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise _Unreachable from error


def _call(
    method: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
    timeout: float = HTTP_TIMEOUT,
) -> tuple[int, dict | None]:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    status, raw = _send(method, SERVICE_URL + path, headers=headers, body=body, timeout=timeout)
    try:
        data = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, ValueError):
        data = None
    return status, data if isinstance(data, dict) else None


def _profile(data: dict | None, status: Status) -> Access | None:
    """Valida el perfil devuelto por el servidor. Devuelve None si la respuesta es malformada."""
    if not data:
        return None
    user = data.get("user")
    verified = data.get("verified_at")
    if not isinstance(user, dict) or not isinstance(verified, int) or isinstance(verified, bool):
        return None
    user_id = user.get("id")
    name = user.get("name", "")
    avatar = user.get("avatar_url", "")
    if not isinstance(user_id, str) or not user_id.isdigit() or len(user_id) > 25:
        return None
    if not isinstance(name, str) or not isinstance(avatar, str):
        return None
    if avatar and not avatar.startswith(AVATAR_PREFIX):
        avatar = ""  # solo se acepta el CDN oficial de Discord
    return Access(status, user_id=user_id, name=name[:64], avatar_url=avatar, verified_at=verified)


# --- Sesión guardada -------------------------------------------------------

def _session_path() -> Path:
    return settings.settings_path().parent / SESSION_FILE


def stored_token() -> str | None:
    """Token opaco guardado. Un archivo editado a mano no basta: el servidor lo rechaza."""
    try:
        data = json.loads(_session_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    token = data.get("token") if isinstance(data, dict) else None
    return token if isinstance(token, str) and _TOKEN_RE.match(token) else None


def _store_token(token: str) -> None:
    path = _session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"token": token}), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def clear_session() -> None:
    try:
        _session_path().unlink()
    except OSError:
        pass
    try:
        if LEGACY_SETTINGS_KEY in settings.load():
            settings.delete_value(LEGACY_SETTINGS_KEY)
    except OSError:
        pass


# --- Comprobación contra el servidor ---------------------------------------

def verify_session(token: str, *, timeout: float = HTTP_TIMEOUT) -> Access:
    """Pregunta al servidor si la sesión sigue siendo válida y la cuenta sigue en el servidor."""
    if not _TOKEN_RE.match(token):
        clear_session()
        return Access(Status.SESSION_EXPIRED, error="session_invalid")
    try:
        status, data = _call("POST", "/api/session/check", token=token, timeout=timeout)
    except _Unreachable:
        return Access(Status.UNAVAILABLE, error="network")
    if status == 200 and data and data.get("ok") is True:
        access = _profile(data, Status.GRANTED)
        return access if access is not None else Access(Status.UNAVAILABLE, error="unavailable")
    code = data.get("error") if data else None
    if status == 401:
        clear_session()
        return Access(Status.SESSION_EXPIRED, error="session_invalid")
    if status == 403 and code == "not_member":
        clear_session()
        return Access(Status.NOT_MEMBER, error="not_member")
    return Access(Status.UNAVAILABLE, error="unavailable")


def sign_out() -> None:
    token = stored_token()
    if token:
        try:
            _call("POST", "/api/session/logout", token=token)
        except _Unreachable:
            pass  # la sesión se borra igualmente en este equipo
    clear_session()


def _exchange(ticket: str) -> tuple[str, Access]:
    if not _TOKEN_RE.match(ticket):
        raise LoginError("token_failed")
    try:
        status, data = _call("POST", "/api/session/exchange", payload={"ticket": ticket})
    except _Unreachable:
        raise LoginError("network") from None
    token = data.get("token") if data else None
    access = _profile(data, Status.GRANTED)
    if status != 200 or not isinstance(token, str) or not _TOKEN_RE.match(token) or access is None:
        raise LoginError("ticket_invalid" if status == 401 else "token_failed")
    return token, access


def _finish(query: dict[str, str]) -> tuple[str | None, Access]:
    code = query.get("error", "")
    if code:
        status = Status.NOT_MEMBER if code == "not_member" else Status.FAILED
        return None, Access(status, error=code[:32])
    try:
        token, access = _exchange(query.get("t", ""))
        _store_token(token)
    except LoginError as error:
        return None, Access(Status.FAILED, error=error.code)
    except OSError:
        return None, Access(Status.FAILED, error="storage")
    return token, access


# --- Inicio de sesión por loopback -----------------------------------------

_SUCCESS_TEXT = "Autorización recibida. Puedes volver a Quick Mechanic para completar el acceso."
_PAGE = (
    "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
    "<title>Quick Mechanic</title></head>"
    "<body style=\"background:#0b0b0c;color:#e9e4d6;font-family:sans-serif;"
    "display:flex;min-height:100vh;align-items:center;justify-content:center\">"
    "<p style=\"max-width:28rem;text-align:center;line-height:1.5\">{text}</p></body></html>"
)


def _make_handler(nonce: str, sink: list[dict[str, str]]) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (nombre requerido por http.server)
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self._reply(404, "Página no encontrada.")
                return
            query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
            if not secrets.compare_digest(query.get("s", "").encode(), nonce.encode()):
                self._reply(400, "Esta autorización no corresponde a esta sesión de Quick Mechanic.")
                return
            if sink:
                self._reply(409, "Esta autorización ya se utilizó.")
                return
            sink.append(query)
            text = error_message(query["error"]) if query.get("error") else _SUCCESS_TEXT
            self._reply(200, text)

        def _reply(self, status: int, text: str) -> None:
            body = _PAGE.format(text=html.escape(text)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return  # nunca se registran las URLs de callback (llevan tickets)

    return _Handler


def _wait_for_login(
    server: HTTPServer,
    sink: list[dict[str, str]],
    timeout: float,
    on_result: Callable[[str | None, Access], None],
) -> None:
    deadline = time.monotonic() + timeout
    try:
        while not sink:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            server.timeout = remaining
            server.handle_request()
    finally:
        server.server_close()
    if not sink:
        on_result(None, Access(Status.FAILED, error="timeout"))
        return
    token, access = _finish(sink[0])
    on_result(token, access)


def start_login(
    on_result: Callable[[str | None, Access], None],
    *,
    timeout: float = LOGIN_TIMEOUT,
    open_browser: bool = True,
) -> str:
    """Abre Discord en el navegador. on_result se llama desde un hilo secundario.

    Sólo un callback con el `state` de esta llamada se acepta, y solo una vez.
    """
    nonce = secrets.token_urlsafe(24)
    sink: list[dict[str, str]] = []
    server = HTTPServer(("127.0.0.1", 0), _make_handler(nonce, sink))
    port = server.server_address[1]
    start_url = f"{SERVICE_URL}/api/discord/start?" + urlencode({"port": port, "state": nonce})
    threading.Thread(
        target=_wait_for_login,
        args=(server, sink, timeout, on_result),
        name="discord-login",
        daemon=True,
    ).start()
    if open_browser:
        webbrowser.open(start_url)
    return start_url
