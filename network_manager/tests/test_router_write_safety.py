"""
The routers must never become write-capable by accident.

These routers are shared with the legacy system and the office Mini PC. A write
can deprovision a paying subscriber, collide with the old system mid-change, or
cut a live line. Those failures hit the business immediately and are hard to
reverse, so every ambiguous path has to fail SAFE -- a missing environment
variable, a typo, a caller that cannot see settings, or a caller that passes
dry_run=False must all land on read_only.

The only way to 'live' is an explicit human decision. See AGENTS.md Rule 40.
"""

from unittest import mock

from django.test import SimpleTestCase, override_settings

from network_manager.services.base import MikrotikBase


def _build(device, **kwargs):
    """Instantiate the base without opening a socket or touching the router."""
    obj = MikrotikBase.__new__(MikrotikBase)
    obj.__init__(device, **kwargs)
    return obj


class RouterWriteDefaultsFailSafeTests(SimpleTestCase):
    """A missing or malformed ROUTER_MODE must never imply write access."""

    def test_settings_default_is_read_only(self):
        """The settings module itself must default to read_only, not live.

        Regression guard: the default used to be 'live', so any environment
        that failed to pass ROUTER_MODE (a bare `docker run`, a new compose
        service, a settings module evaluated outside compose) came up able to
        write to production hardware.
        """
        import importlib
        import sys

        with mock.patch.dict("os.environ", {}, clear=False):
            importlib.reload(importlib.import_module("gametech_core.settings"))

        import gametech_core.settings as s

        # sys.argv during a test run forces the testing branch, so read the
        # literal default out of the source instead of the evaluated value.
        source = open(s.__file__, encoding="utf-8").read()
        self.assertIn(
            'env.str("ROUTER_MODE", default="read_only")', source,
            "settings.py must default ROUTER_MODE to read_only",
        )
        self.assertNotIn(
            'env.str("ROUTER_MODE", default="live")', source,
            "settings.py must NEVER default ROUTER_MODE to live",
        )

    def test_missing_setting_is_read_only(self):
        obj = _build("dev")
        self.assertEqual(obj.router_mode, "read_only")
        self.assertTrue(obj.is_read_only)

    def test_setting_is_none_is_read_only(self):
        """ROUTER_MODE=None must not raise and must not grant writes.

        A partially-loaded settings module can expose ROUTER_MODE as None. The
        old `.lower().strip()` chain raised AttributeError on that, which is a
        crash rather than a safe refusal.
        """
        import network_manager.services.base as B

        class NoneSettings:
            ROUTER_MODE = None

        old = B.settings
        try:
            B.settings = NoneSettings()
            obj = _build("dev", dry_run=False)
        finally:
            B.settings = old
        self.assertEqual(obj.router_mode, "read_only")
        self.assertTrue(obj.is_read_only)

    def test_setting_attribute_absent_entirely(self):
        """A settings object with no ROUTER_MODE attribute at all."""
        import network_manager.services.base as B

        class EmptySettings:
            pass

        old = B.settings
        try:
            B.settings = EmptySettings()
            obj = _build("dev")
        finally:
            B.settings = old
        self.assertEqual(obj.router_mode, "read_only")

    def test_resolve_mode_helper_is_total(self):
        """_resolve_mode must return a safe mode for anything whatsoever."""
        from network_manager.services.base import MikrotikBase as M

        for value in (None, "", "  ", "LIVE", "Read_Only", "banana", 0, 1,
                      object(), [], {}, True, 3.5):
            with self.subTest(value=repr(value)):
                self.assertIn(M._resolve_mode(value),
                              ("dry_run", "read_only", "live"))
        self.assertEqual(M._resolve_mode("live"), "live")
        self.assertEqual(M._resolve_mode("READ_ONLY"), "read_only")
        self.assertEqual(M._resolve_mode(" Dry_Run "), "dry_run")

    def test_unrecognised_value_is_read_only(self):
        obj = _build("dev", router_mode="totally-bogus-mode")
        self.assertEqual(obj.router_mode, "read_only")
        self.assertTrue(obj.is_read_only)

    def test_dry_run_false_does_not_grant_writes(self):
        """THE REGRESSION THIS EXISTS FOR.

        `MikrotikAPI(device, dry_run=False)` used to resolve to "live" -- full
        write access -- because `dry_run is not None` short-circuited the
        settings lookup. A global ROUTER_MODE=read_only could not stop it.
        """
        obj = _build("dev", dry_run=False)
        self.assertNotEqual(obj.router_mode, "live")
        self.assertTrue(obj.is_read_only)

    @override_settings(ROUTER_MODE="read_only")
    def test_dry_run_false_respects_global_read_only(self):
        obj = _build("dev", dry_run=False)
        self.assertEqual(obj.router_mode, "read_only")
        self.assertTrue(obj.is_read_only)

    @override_settings(ROUTER_MODE="read_only")
    def test_dry_run_true_still_stubs(self):
        obj = _build("dev", dry_run=True)
        self.assertEqual(obj.router_mode, "dry_run")
        self.assertTrue(obj.is_dry_run)

    def test_explicit_live_is_still_honoured(self):
        """The escape hatch must keep working, or cutover could never happen."""
        obj = _build("dev", router_mode="live")
        self.assertEqual(obj.router_mode, "live")

    def test_no_service_layer_falls_back_to_live(self):
        """Grep-style guard: no module may default a lookup to 'live'."""
        import os
        import re

        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pattern = re.compile(r'ROUTER_MODE"\s*,\s*"live"')
        offenders = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in (".git", "node_modules", "__pycache__", "migrations",
                             "templates", "static", "archived_scripts")
            ]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    text = open(path, encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
                if pattern.search(text):
                    offenders.append(os.path.relpath(path, root))
        self.assertEqual(
            offenders, [],
            "these files default a ROUTER_MODE lookup to 'live': %s" % offenders,
        )