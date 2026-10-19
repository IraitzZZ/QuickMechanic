"""Tests de quickmechanic.discord_link contra la API real del Worker (simulada en red).

Esto NO prueba Discord en vivo: sustituye la capa HTTP por respuestas programadas que
siguen el contrato de discord-service/worker.js. La prueba end-to-end con una cuenta
real de Discord queda pendiente y se documenta aparte.
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

import unittest

from quickmechanic import discord_link, settings
from quickmechanic.discord_link import Status

MEMBER_ID = "123456789012345678"
AVATAR = "https://cdn.discordapp.com/avatars/123456789012345678/abc.png"
TOKEN = secrets.token_urlsafe(32)  # 43 caracteres base64url: formato válido
TICKET = secrets.token_urlsafe(32)
PROFILE = {
    "ok": True,
    "verified_at": 1_700_000_000_000,
    "user": {"id": MEMBER_ID, "name": "Iraitz", "avatar_url": AVATAR},
}


class _Net:
    """Sustituye discord_link._send: devuelve respuestas programadas y anota las llamadas."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[tuple[str, str, str | None]] = []
        self.user_agents: list[str | None] = []

    def __call__(self, method, url, *, headers, body, timeout):
        self.calls.append((method, url, headers.get("Authorization")))
        self.user_agents.append(headers.get("User-Agent"))
        if not self.replies:
            raise AssertionError(f"llamada inesperada: {method} {url}")
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        status, data = reply
        raw = b"" if data is None else (data if isinstance(data, bytes) else json.dumps(data).encode())
        return status, raw


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"APPDATA": self._tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def net(self, *replies: object) -> _Net:
        net = _Net(*replies)
        patcher = mock.patch.object(discord_link, "_send", side_effect=net)
        patcher.start()
        self.addCleanup(patcher.stop)
        return net

    def save_session(self, token: str = TOKEN) -> None:
        discord_link._store_token(token)


class MembershipCheckTests(_Base):
    """verify_session: cada arranque pregunta al servidor, nunca confía en datos locales."""

    def test_member_is_granted_with_real_profile(self) -> None:
        self.save_session()
        net = self.net((200, PROFILE))
        access = discord_link.verify_session(TOKEN)
        self.assertTrue(access.granted)
        self.assertEqual(access.user_id, MEMBER_ID)
        self.assertEqual(access.name, "Iraitz")
        self.assertEqual(access.avatar_url, AVATAR)
        self.assertEqual(access.verified_at, PROFILE["verified_at"])
        self.assertEqual(net.calls[0][1], discord_link.SERVICE_URL + "/api/session/check")
        self.assertEqual(net.calls[0][2], f"Bearer {TOKEN}")
        self.assertEqual(discord_link.stored_token(), TOKEN)

    def test_not_member_is_denied_and_session_removed(self) -> None:
        self.save_session()
        self.net((403, {"error": "not_member"}))
        access = discord_link.verify_session(TOKEN)
        self.assertEqual(access.status, Status.NOT_MEMBER)
        self.assertFalse(access.granted)
        self.assertIsNone(discord_link.stored_token())

    def test_revoked_or_expired_session_requires_login(self) -> None:
        self.save_session()
        self.net((401, {"error": "session_invalid"}))
        access = discord_link.verify_session(TOKEN)
        self.assertEqual(access.status, Status.SESSION_EXPIRED)
        self.assertIsNone(discord_link.stored_token())

    def test_discord_unavailable_denies_temporarily_but_keeps_session(self) -> None:
        self.save_session()
        self.net((503, {"error": "discord_unavailable"}))
        access = discord_link.verify_session(TOKEN)
        self.assertEqual(access.status, Status.UNAVAILABLE)
        self.assertFalse(access.granted)
        # Un error temporal no es una prueba de que el usuario haya salido del servidor.
        self.assertEqual(discord_link.stored_token(), TOKEN)

    def test_network_error_is_unavailable_not_not_member(self) -> None:
        self.save_session()
        self.net(discord_link._Unreachable())
        access = discord_link.verify_session(TOKEN)
        self.assertEqual(access.status, Status.UNAVAILABLE)
        self.assertEqual(access.error, "network")
        self.assertEqual(discord_link.stored_token(), TOKEN)

    def test_timeout_and_disconnect_are_unavailable(self) -> None:
        self.save_session()
        for failure in (TimeoutError("timed out"), ConnectionResetError("reset")):
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(urllib.request, "urlopen", side_effect=failure):
                    access = discord_link.verify_session(TOKEN)
                self.assertEqual(access.status, Status.UNAVAILABLE)
                self.assertEqual(discord_link.stored_token(), TOKEN)

    def test_malformed_responses_are_never_granted(self) -> None:
        self.save_session()
        bad_bodies = {
            "html en vez de JSON": (200, b"<html>oops</html>"),
            "sin ok": (200, {"user": PROFILE["user"], "verified_at": 1}),
            "usuario como texto": (200, {"ok": True, "verified_at": 1, "user": "123"}),
            "id no numérico": (200, {"ok": True, "verified_at": 1, "user": {"id": "abc"}}),
            "verified_at booleano": (200, {"ok": True, "verified_at": True, "user": PROFILE["user"]}),
            "sin verified_at": (200, {"ok": True, "user": PROFILE["user"]}),
        }
        for label, reply in bad_bodies.items():
            with self.subTest(label):
                self.net(reply)
                access = discord_link.verify_session(TOKEN)
                self.assertFalse(access.granted)
                self.assertEqual(access.status, Status.UNAVAILABLE)

    def test_avatar_outside_discord_cdn_is_dropped(self) -> None:
        self.save_session()
        profile = json.loads(json.dumps(PROFILE))
        profile["user"]["avatar_url"] = "https://evil.example/tracker.png"
        self.net((200, profile))
        access = discord_link.verify_session(TOKEN)
        self.assertTrue(access.granted)
        self.assertEqual(access.avatar_url, "")

    def test_forged_local_session_is_rejected_without_network(self) -> None:
        # Editar el JSON local con un token inventado no sirve: ni siquiera sale a la red.
        net = self.net()
        access = discord_link.verify_session("token-inventado")
        self.assertEqual(access.status, Status.SESSION_EXPIRED)
        self.assertEqual(net.calls, [])

    def test_hand_edited_session_file_is_ignored(self) -> None:
        path = discord_link._session_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        for content in ('{"token": "corto", "verified": true}', '{"verified": true}', "no es json"):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                self.assertIsNone(discord_link.stored_token())

    def test_legacy_local_flag_does_not_grant_access(self) -> None:
        # Formato anterior: un ajuste local "discord_account" con verificado=true.
        settings.set_value(discord_link.LEGACY_SETTINGS_KEY, {"name": "x", "verified": True})
        self.assertIsNone(discord_link.stored_token())
        discord_link.clear_session()
        self.assertIsNone(settings.get(discord_link.LEGACY_SETTINGS_KEY))

    def test_sign_out_revokes_on_server_and_clears_locally(self) -> None:
        self.save_session()
        net = self.net((204, None))
        discord_link.sign_out()
        self.assertEqual(net.calls[0][1], discord_link.SERVICE_URL + "/api/session/logout")
        self.assertIsNone(discord_link.stored_token())

    def test_sign_out_clears_locally_even_if_server_unreachable(self) -> None:
        self.save_session()
        self.net(discord_link._Unreachable())
        discord_link.sign_out()
        self.assertIsNone(discord_link.stored_token())


class LoginResultTests(_Base):
    """_finish: el resultado que llega desde el navegador tras el callback."""

    def test_denied_authorization_is_reported_as_failure(self) -> None:
        token, access = discord_link._finish({"error": "denied"})
        self.assertIsNone(token)
        self.assertEqual(access.status, Status.FAILED)
        self.assertIn("Cancelaste", discord_link.error_message(access.error))

    def test_not_member_callback_is_denied(self) -> None:
        token, access = discord_link._finish({"error": "not_member"})
        self.assertIsNone(token)
        self.assertEqual(access.status, Status.NOT_MEMBER)
        self.assertIsNone(discord_link.stored_token())

    def test_valid_ticket_is_exchanged_once_for_session(self) -> None:
        self.net((200, {"token": TOKEN, "user": PROFILE["user"], "verified_at": PROFILE["verified_at"]}))
        token, access = discord_link._finish({"t": TICKET})
        self.assertEqual(token, TOKEN)
        self.assertTrue(access.granted)
        self.assertEqual(discord_link.stored_token(), TOKEN)

    def test_rejected_ticket_stores_nothing(self) -> None:
        self.net((401, {"error": "ticket_invalid"}))
        token, access = discord_link._finish({"t": TICKET})
        self.assertIsNone(token)
        self.assertEqual(access.status, Status.FAILED)
        self.assertIsNone(discord_link.stored_token())

    def test_malformed_ticket_never_reaches_network(self) -> None:
        net = self.net()
        for ticket in ("", "corto", "con espacios " * 5, "a" * 200):
            with self.subTest(ticket=ticket[:12]):
                token, access = discord_link._finish({"t": ticket})
                self.assertIsNone(token)
                self.assertEqual(access.status, Status.FAILED)
        self.assertEqual(net.calls, [])

    def test_exchange_response_without_valid_token_fails(self) -> None:
        for reply in ((200, {"user": PROFILE["user"], "verified_at": 1}), (200, {"token": "corto", "user": PROFILE["user"], "verified_at": 1})):
            with self.subTest(reply=reply[1]):
                self.net(reply)
                token, access = discord_link._finish({"t": TICKET})
                self.assertIsNone(token)
                self.assertEqual(access.status, Status.FAILED)
                self.assertIsNone(discord_link.stored_token())

    def test_requests_send_quickmechanic_user_agent_not_urllib_default(self) -> None:
        # Cloudflare (error 1010) rechaza "Python-urllib/x.y" con 403: cada petición debe llevar nuestro User-Agent.
        net = self.net((401, {"error": "ticket_invalid"}))
        discord_link._finish({"t": TICKET})
        self.assertEqual(len(net.user_agents), 1)
        self.assertEqual(net.user_agents[0], discord_link.USER_AGENT)
        self.assertTrue(discord_link.USER_AGENT.startswith("QuickMechanic/"))
        self.assertNotIn("urllib", discord_link.USER_AGENT.lower())

    def test_edge_block_403_never_grants_access(self) -> None:
        # Respuesta real del bloqueo de Cloudflare: HTML/JSON de 403 sin ticket ni sesión.
        self.net((403, {"title": "Error 1010: Access denied", "status": 403}))
        token, access = discord_link._finish({"t": TICKET})
        self.assertIsNone(token)
        self.assertFalse(access.granted)
        self.assertEqual(access.status, Status.FAILED)
        self.assertIsNone(discord_link.stored_token())

    def test_error_messages_never_echo_raw_codes(self) -> None:
        generic = discord_link.error_message("weird")
        self.assertNotIn("weird", generic)
        self.assertIn("Vuelve a intentarlo", generic)


class LoopbackLoginTests(_Base):
    """start_login: servidor local en 127.0.0.1 que solo acepta el state de esta sesión."""

    def _start(self, *, timeout: float = 5.0) -> tuple[str, list, threading.Event]:
        done = threading.Event()
        results: list = []

        def on_result(token, access):
            results.append((token, access))
            done.set()

        url = discord_link.start_login(on_result, timeout=timeout, open_browser=False)
        return url, results, done

    @staticmethod
    def _params(url: str) -> tuple[int, str]:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        return int(query["port"][0]), query["state"][0]

    @staticmethod
    def _hit(port: int, query: str) -> int | None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f"http://127.0.0.1:{port}/callback?{query}", timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            return code
        except (urllib.error.URLError, OSError):
            return None  # servidor ya cerrado tras la primera autorización

    def test_start_url_points_to_service_without_secrets(self) -> None:
        url, _results, _done = self._start(timeout=0.2)
        self.assertTrue(url.startswith(discord_link.SERVICE_URL + "/api/discord/start?"))
        self.assertNotIn("secret", url.lower())
        self.assertNotIn("client", url.lower())

    def test_wrong_state_is_rejected_then_correct_callback_grants(self) -> None:
        url, results, done = self._start()
        port, nonce = self._params(url)
        self.net((200, {"token": TOKEN, "user": PROFILE["user"], "verified_at": 1}))
        self.assertEqual(self._hit(port, f"s={secrets.token_urlsafe(24)}&t={TICKET}"), 400)
        self.assertEqual(self._hit(port, f"s={nonce}&t={TICKET}"), 200)
        self.assertTrue(done.wait(5))
        token, access = results[0]
        self.assertEqual(token, TOKEN)
        self.assertTrue(access.granted)

    def test_error_callback_reports_denial(self) -> None:
        url, results, done = self._start()
        port, nonce = self._params(url)
        self.assertEqual(self._hit(port, f"s={nonce}&error=denied"), 200)
        self.assertTrue(done.wait(5))
        token, access = results[0]
        self.assertIsNone(token)
        self.assertEqual(access.status, Status.FAILED)
        self.assertEqual(access.error, "denied")

    def test_duplicate_callback_is_not_accepted_twice(self) -> None:
        url, results, done = self._start()
        port, nonce = self._params(url)
        self.net((200, {"token": TOKEN, "user": PROFILE["user"], "verified_at": 1}))
        self.assertEqual(self._hit(port, f"s={nonce}&t={TICKET}"), 200)
        self.assertTrue(done.wait(5))
        self.assertIn(self._hit(port, f"s={nonce}&t={TICKET}"), (409, None))
        self.assertEqual(len(results), 1)

    def test_no_callback_times_out_as_failure(self) -> None:
        _url, results, done = self._start(timeout=0.2)
        self.assertTrue(done.wait(5))
        token, access = results[0]
        self.assertIsNone(token)
        self.assertEqual(access.status, Status.FAILED)
        self.assertEqual(access.error, "timeout")


if __name__ == "__main__":
    unittest.main()
