"""Tests de la puerta de acceso y de la revalidación periódica (sin Discord real).

Todas las llamadas a discord_link se sustituyen por simulaciones. Los tests
comprueban la lógica de estado; la decisión real la toma el servidor.
"""
from __future__ import annotations

import os
import threading
import time
import unittest
from typing import Callable
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # pragma: no cover - depende del entorno
    from PyQt6.QtWidgets import QApplication

    from quickmechanic import access_gate, discord_link
    from quickmechanic.discord_link import Access, Status

    GUI = True
    GUI_ERROR = ""
except Exception as error:  # pragma: no cover
    GUI = False
    GUI_ERROR = str(error)


def _granted(name: str = "Iraitz") -> Access:
    return Access(Status.GRANTED, user_id="123", name=name, verified_at=1_700_000_000_000)


class _SyncCalls:
    """Sustituto de _MainThreadCalls que ejecuta todo en el hilo del test."""

    def run(self, work: Callable[[], object], done: Callable[[object], None]) -> None:
        done(work())

    def post(self, fn: Callable[[], None]) -> None:
        fn()


@unittest.skipUnless(GUI, f"PyQt6 no esta disponible: {GUI_ERROR if not GUI else ''}")
class AccessMonitorTests(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.monitor = access_gate.AccessMonitor()
        self.addCleanup(self.monitor._timer.stop)
        self.published: list[Access] = []
        self.monitor.changed.connect(self.published.append)

    def _pump(self, predicate: Callable[[], bool], timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > deadline:
                self.fail("Tiempo agotado esperando el resultado de la comprobación")
            self.app.processEvents()
            time.sleep(0.01)

    def test_attach_publishes_granted_and_starts_revalidation(self) -> None:
        self.monitor.attach("token-valido", _granted())
        self.assertTrue(self.monitor.access.granted)
        self.assertTrue(self.monitor._timer.isActive())
        self.assertEqual(self.monitor._timer.interval(), access_gate.REVALIDATE_MS)

    def test_still_member_keeps_access(self) -> None:
        self.monitor.attach("token-valido", _granted())
        with mock.patch.object(discord_link, "verify_session", return_value=_granted()) as verify:
            self.monitor._calls = _SyncCalls()
            self.monitor.check_now()
        verify.assert_called_once_with("token-valido")
        self.assertTrue(self.monitor.access.granted)
        self.assertEqual(self.monitor._token, "token-valido")

    def test_member_who_left_loses_access_and_token(self) -> None:
        self.monitor.attach("token-valido", _granted())
        self.monitor._calls = _SyncCalls()
        with mock.patch.object(
            discord_link, "verify_session", return_value=Access(Status.NOT_MEMBER, error="not_member")
        ):
            self.monitor.check_now()
        self.assertEqual(self.monitor.access.status, Status.NOT_MEMBER)
        self.assertIsNone(self.monitor._token)
        self.assertFalse(self.monitor._timer.isActive())

    def test_expired_session_loses_access(self) -> None:
        self.monitor.attach("token-caducado", _granted())
        self.monitor._calls = _SyncCalls()
        with mock.patch.object(
            discord_link, "verify_session", return_value=Access(Status.SESSION_EXPIRED, error="session_invalid")
        ):
            self.monitor.check_now()
        self.assertEqual(self.monitor.access.status, Status.SESSION_EXPIRED)
        self.assertIsNone(self.monitor._token)

    def test_unavailable_discord_does_not_revoke_access(self) -> None:
        self.monitor.attach("token-valido", _granted())
        self.monitor._calls = _SyncCalls()
        with mock.patch.object(
            discord_link, "verify_session", return_value=Access(Status.UNAVAILABLE, error="unavailable")
        ):
            self.monitor.check_now()
        self.assertEqual(self.monitor.access.status, Status.UNAVAILABLE)
        self.assertEqual(self.monitor._token, "token-valido")
        self.assertTrue(self.monitor._timer.isActive())
        self.assertEqual(self.monitor._timer.interval(), access_gate.RETRY_MS)

    def test_exception_in_background_check_is_unavailable_not_revoked(self) -> None:
        self.monitor.attach("token-valido", _granted())
        with mock.patch.object(discord_link, "verify_session", side_effect=RuntimeError("boom")):
            self.monitor.check_now()
            self._pump(lambda: self.monitor.access.status is Status.UNAVAILABLE)
        self.assertEqual(self.monitor._token, "token-valido")
        self.assertFalse(self.monitor._busy)

    def test_check_is_ignored_while_another_is_running(self) -> None:
        self.monitor.attach("token-valido", _granted())
        release = threading.Event()
        calls: list[str] = []

        def slow_verify(token: str) -> Access:
            calls.append(token)
            release.wait(5)
            return _granted()

        with mock.patch.object(discord_link, "verify_session", side_effect=slow_verify):
            self.monitor.check_now()
            self.monitor.check_now()  # debe ignorarse: ya hay una comprobación en curso
            self.assertEqual(len(calls), 1)
            release.set()
            self._pump(lambda: not self.monitor._busy)
        self.assertEqual(len(calls), 1)

    def test_late_result_after_sign_out_is_ignored(self) -> None:
        self.monitor.attach("token-valido", _granted())
        self.monitor._token = None  # simula sign_out ya ejecutado
        before = len(self.published)
        self.monitor._on_checked(Access(Status.NOT_MEMBER, error="not_member"))
        self.assertEqual(len(self.published), before)

    def test_sign_out_clears_session_and_publishes_not_signed_in(self) -> None:
        self.monitor.attach("token-valido", _granted())
        with mock.patch.object(discord_link, "sign_out") as sign_out:
            self.monitor.sign_out()
            self._pump(lambda: self.monitor.access.status is Status.NOT_SIGNED_IN)
        sign_out.assert_called_once()
        self.assertIsNone(self.monitor._token)
        self.assertFalse(self.monitor._timer.isActive())

    def test_check_without_session_reports_not_signed_in(self) -> None:
        with mock.patch.object(discord_link, "verify_session") as verify:
            self.monitor.check_now()
        verify.assert_not_called()
        self.assertEqual(self.monitor.access.status, Status.NOT_SIGNED_IN)


@unittest.skipUnless(GUI, f"PyQt6 no esta disponible: {GUI_ERROR if not GUI else ''}")
class AccessGateTests(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.monitor = access_gate.AccessMonitor()
        self.addCleanup(self.monitor._timer.stop)
        self.gate = access_gate.AccessGate(self.monitor)
        self.gate._calls = _SyncCalls()  # type: ignore[assignment]
        self.addCleanup(self.gate.close)
        self.gate.show()

    def test_granted_by_server_accepts_and_attaches_monitor(self) -> None:
        with mock.patch.object(self.monitor, "attach", wraps=self.monitor.attach) as attach:
            self.gate._on_verified("token-valido", _granted())
        attach.assert_called_once()
        self.assertTrue(self.gate._granted)
        self.assertTrue(self.monitor.access.granted)
        self.assertFalse(self.gate.isVisible())

    def test_not_member_blocks_and_offers_join_button(self) -> None:
        self.gate._on_verified("token-valido", Access(Status.NOT_MEMBER, error="not_member"))
        self.assertFalse(self.gate._granted)
        self.assertEqual(self.gate._stack.currentIndex(), 2)
        self.assertTrue(self.gate._join_button.isVisibleTo(self.gate))
        self.assertTrue(self.gate.isVisible())
        self.assertFalse(self.monitor.access.granted)

    def test_unavailable_blocks_without_offering_join(self) -> None:
        self.gate._on_verified("token-valido", Access(Status.UNAVAILABLE, error="unavailable"))
        self.assertFalse(self.gate._granted)
        self.assertEqual(self.gate._stack.currentIndex(), 2)
        self.assertFalse(self.gate._join_button.isVisibleTo(self.gate))
        self.assertTrue(self.gate._retry_button.isEnabled())

    def test_login_result_without_token_is_never_accepted(self) -> None:
        self.gate._on_login(None, _granted())
        self.assertFalse(self.gate._granted)
        self.assertFalse(self.monitor.access.granted)

    def test_login_success_with_token_is_accepted(self) -> None:
        self.gate._on_login("token-nuevo", _granted())
        self.assertTrue(self.gate._granted)
        self.assertEqual(self.monitor._token, "token-nuevo")

    def test_duplicate_login_callback_attaches_only_once(self) -> None:
        with mock.patch.object(self.monitor, "attach") as attach:
            self.gate._on_login("token-nuevo", _granted())
            self.gate._on_login("token-nuevo", _granted())  # callback reutilizado
        attach.assert_called_once()

    def test_window_closed_before_answer_does_not_grant(self) -> None:
        self.gate.hide()
        with mock.patch.object(self.monitor, "attach") as attach:
            self.gate._on_verified("token-valido", _granted())
        attach.assert_not_called()
        self.assertFalse(self.gate._granted)

    def test_retry_without_stored_token_starts_login(self) -> None:
        with mock.patch.object(discord_link, "stored_token", return_value=None), mock.patch.object(
            discord_link, "start_login", return_value="http://servicio/login"
        ) as start:
            self.gate._retry()
        start.assert_called_once()

    def test_retry_with_stored_token_checks_server(self) -> None:
        with mock.patch.object(discord_link, "stored_token", return_value="token-guardado"), mock.patch.object(
            discord_link, "verify_session", return_value=_granted()
        ) as verify:
            self.gate._retry()
        verify.assert_called_once_with("token-guardado")
        self.assertTrue(self.gate._granted)

    def test_browser_cannot_be_opened_is_reported_as_unavailable(self) -> None:
        with mock.patch.object(discord_link, "start_login", side_effect=OSError("sin navegador")):
            self.gate._start_login()
        self.assertEqual(self.gate._stack.currentIndex(), 2)
        self.assertFalse(self.gate._granted)


if __name__ == "__main__":
    unittest.main()
