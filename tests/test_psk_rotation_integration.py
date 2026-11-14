#!/usr/bin/env python3
"""Simulated no-host-access rotation: mismatched global/active PSK is repaired."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest import mock
import unittest

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "psk-client-manager.py"
SPEC = importlib.util.spec_from_file_location("psk_rotate_module", SOURCE)
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class RotationIntegration(unittest.TestCase):
    def test_reconcile_different_psks_without_real_daemon(self):
        before_global = "PreviousGlobalPass18"
        before_active = "DifferentActivePass1234"
        new_key = "Short+Secret16!"

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            global_file = root / "global-psk.secrets"
            active = root / "50-mobile-l2tp-ipsec.conf"
            candidate = root / "candidate.conf"
            global_file.write_text(': PSK "' + before_global + '"\n')
            template = ('connections {\n  mobile-l2tp-psk {\n    version = 1\n  }\n}\n'
                        'secrets {\n  ike-mobile-l2tp {\n    secret = "'
                        + before_active + '"\n  }\n}\n')
            active.write_text(template)
            candidate.write_text(template)

            def fake_run(args, **_kwargs):
                if args[:4] == ["ip", "xfrm", "state", "count"]:
                    return SimpleNamespace(returncode=0, stdout="SAD count 0\n")
                if args[:2] == ["swanctl", "--stats"]:
                    return SimpleNamespace(returncode=0, stdout="IKE_SAs: 0 total, 0 half-open\n")
                if args[:2] == ["systemctl", "is-active"]:
                    return SimpleNamespace(returncode=0, stdout="")
                if args[:2] == ["swanctl", "--list-conns"]:
                    return SimpleNamespace(returncode=0, stdout="mobile-l2tp-psk: IKEv1\n")
                if args[:2] == ["swanctl", "--load-creds"]:
                    return SimpleNamespace(returncode=0, stdout="loaded IKE secret 'ike-mobile-l2tp'\n")
                raise AssertionError("Unexpected external command: " + repr(args))

            def fake_atomic_write(path, data):
                path.write_text(data, encoding="ascii")

            with (
                mock.patch.object(manager, "PSK", global_file),
                mock.patch.object(manager, "ACTIVE", active),
                mock.patch.object(manager, "CANDIDATE", candidate),
                mock.patch.object(manager, "secure_file", return_value=True),
                mock.patch.object(manager, "locked", return_value=contextlib.nullcontext()),
                mock.patch.object(manager, "load_psk", return_value=before_global),
                mock.patch.object(manager, "active_psk", return_value=before_active),
                mock.patch.object(manager, "tty_confirmation"),
                mock.patch.object(manager, "atomic_write", side_effect=fake_atomic_write),
                mock.patch.object(manager.getpass, "getpass", side_effect=[new_key, new_key]),
                mock.patch.object(manager.subprocess, "run", side_effect=fake_run),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                manager.rotate()

            self.assertEqual(global_file.read_text(), ': PSK "' + new_key + '"\n')
            self.assertIn('secret = "' + new_key + '"', active.read_text())
            self.assertIn('secret = "' + new_key + '"', candidate.read_text())
            self.assertNotIn(new_key, output.getvalue())
            self.assertIn("SUCCESS:", output.getvalue())

    def test_short_custom_and_legacy_lengths(self):
        self.assertTrue(manager.valid_psk("Easy123!", minimum=8, maximum=64, for_new=True))
        self.assertTrue(manager.valid_psk("LongerLegacyPassword18"))
        self.assertFalse(manager.valid_psk("too short", minimum=8, maximum=64, for_new=True))
        self.assertFalse(manager.valid_psk(r"unsafe\\12345", minimum=8, maximum=64, for_new=True))


if __name__ == "__main__":
    unittest.main()
