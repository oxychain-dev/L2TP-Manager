#!/usr/bin/env python3
"""Non-privileged pure regression tests for global PSK distribution tooling."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "psk-client-manager.py"
SPEC = importlib.util.spec_from_file_location("psk_client_manager", SOURCE)
psk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(psk)


class SharedPskTests(unittest.TestCase):
    def test_user_status_not_an_ipsec_enforcement_flag(self):
        users = {"example": {"password": "secret", "ip": "198.51.100.10"}}
        self.assertEqual(psk.user_status("example", users, {"users": {}}), "not offered")
        self.assertEqual(psk.user_status("example", users, {"users": {"example": True}}),
                         "offered (not enforced)")
        with self.assertRaises(psk.Invalid):
            psk.user_status("missing", users, {"users": {}})

    def test_root_psk_format(self):
        self.assertIsNotNone(psk.PSK_LINE.fullmatch(': PSK "' + "x" * 64 + '"\n'))
        self.assertIsNotNone(psk.PSK_LINE.fullmatch(': PSK "SimpleKey123!"\n'))
        self.assertIsNotNone(psk.PSK_LINE.fullmatch(': PSK "manuallyChanged123"\n'))
        self.assertIsNone(psk.PSK_LINE.fullmatch(': PSK "bad"quote"\n'))
        self.assertTrue(psk.valid_psk("Short!123", minimum=8, maximum=64, for_new=True))
        self.assertTrue(psk.valid_psk("Special$#&!123", minimum=8, maximum=64, for_new=True))
        self.assertFalse(psk.valid_psk("short", minimum=8, maximum=64, for_new=True))
        self.assertFalse(psk.valid_psk("space wrong", minimum=8, maximum=64, for_new=True))
        self.assertFalse(psk.valid_psk("bad\\path123", minimum=8, maximum=64, for_new=True))
        self.assertFalse(psk.valid_psk("x"*65, minimum=8, maximum=64, for_new=True))
    def test_swanctl_secret_match(self):
        config = 'connections {\n}\nsecrets {\n  ike-client {\n    secret = "' + "x"*64 + '"\n  }\n}\n'
        m = psk.SWAN_SECRET.search(config)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "x"*64)
        self.assertEqual(len(psk.SWAN_SECRET.findall(config)), 1)
        self.assertNotIn("secret = 0s", config)

    def test_chap_parser_supports_comments_and_spaces(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "chap-secrets"
            path.write_text('# comment\nuserabc  *  p@ssWORD12345  198.51.100.10\n'
                            'another  *  "long phrase old"  *\n', encoding="utf-8")
            with mock.patch.object(psk, "secure_file", return_value=True):
                users = psk.read_users(path)
            self.assertEqual(users["userabc"]["ip"], "198.51.100.10")
            self.assertEqual(users["another"]["password"], "long phrase old")

    def test_duplicate_user_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "chap-secrets"
            path.write_text("sample * firstsecret123 198.51.100.1\n"
                            "sample * secondsecret123 198.51.100.2\n")
            with mock.patch.object(psk, "secure_file", return_value=True):
                with self.assertRaises(psk.Invalid):
                    psk.read_users(path)

    def test_metadata_strict(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "flags.json"
            path.write_text(json.dumps({"version": 1, "users": {"userabc": True}}))
            with mock.patch.object(psk, "secure_file", return_value=True):
                self.assertTrue(psk.load_flags(path)["users"]["userabc"])
            path.write_text(json.dumps({"version": 1, "users": {"userabc": "true"}}))
            with mock.patch.object(psk, "secure_file", return_value=True):
                with self.assertRaises(psk.Invalid):
                    psk.load_flags(path)

    def test_reveal_requires_interactive_terminal(self):
        with mock.patch.object(psk.sys.stdin, "isatty", return_value=False):
            with self.assertRaises(psk.Invalid):
                psk.tty_confirmation("Confirm: ", "REVEAL")


if __name__ == "__main__":
    unittest.main()
