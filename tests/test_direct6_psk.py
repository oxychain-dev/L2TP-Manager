#!/usr/bin/env python3
"""Safe unit checks for the isolated direct IPv6 and root-only global PSK."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
from unittest import TestCase, main, mock


ROOT = Path(__file__).resolve().parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


d6 = load("direct6", ROOT / "tools" / "direct6-reconcile.py")
psk = load("global_psk", ROOT / "tools" / "global-psk.py")


def sample():
    return {
        "wan_interface": "test0",
        "wan_ipv6": "2606:4700:4700::1111",
        "direct_prefix": "fdab:1234:5678::/48",
        "table": 203,
        "priority": 10978,
        "clients": [
            {"peer_ipv4": "172.20.31.10", "client_ipv6": "fdab:1234:5678::11/128"},
            {"peer_ipv4": "172.20.31.12", "client_ipv6": "fdab:1234:5678::12/128"}
        ]
    }


class Direct6Tests(TestCase):
    def test_valid_config(self):
        cfg = d6.validate_config(sample())
        self.assertEqual(len(cfg["clients"]), 2)
        self.assertEqual(cfg["direct_prefix"], "fdab:1234:5678::/48")

    def test_duplicate_ipv6_rejected(self):
        c = sample()
        c["clients"][1]["client_ipv6"] = c["clients"][0]["client_ipv6"]
        with self.assertRaises(d6.Failure):
            d6.validate_config(c)

    def test_outside_prefix_rejected(self):
        c = sample()
        c["clients"][0]["client_ipv6"] = "fdff::11/128"
        with self.assertRaises(d6.Failure):
            d6.validate_config(c)

    def test_gre_and_wan_not_hardcoded_in_rules(self):
        cfg = d6.validate_config(sample())
        rules = d6.client_rules(cfg, {"172.20.31.10": "ppp9"})
        self.assertEqual(len(rules), 4)
        self.assertTrue(any("ppp9" in rule and "-j" in rule for rule in rules))
        self.assertFalse(any("172.20.31.12" in rule for rule in rules))
        self.assertEqual(sum(rule[-1] == "DROP" for rule in rules), 2)
        self.assertFalse(any("gre-tunnel-ca" in rule for rule in rules))

    def test_offline_stays_drop_only(self):
        cfg = d6.validate_config(sample())
        rules = d6.client_rules(cfg, {})
        self.assertEqual(len(rules), 2)
        self.assertTrue(all(r[-1] == "DROP" for r in rules))

    def test_nat_limited_to_each_client(self):
        c = sample()
        r = d6.nat_rule(c, c["clients"][0])
        self.assertIn("fdab:1234:5678::11/128", r)
        self.assertIn("test0", r)
        self.assertNotIn("::/0", r)

    def test_bad_priority_rejected(self):
        c = sample()
        c["priority"] = 32766
        with self.assertRaises(d6.Failure):
            d6.validate_config(c)


class GlobalPskTests(TestCase):
    def test_format_and_no_secret_stdout(self):
        with tempfile.TemporaryDirectory() as t:
            secret = Path(t) / "psk.secrets"
            buf = io.StringIO()
            with mock.patch.object(psk, "verify_parent", return_value=None):
                with contextlib.redirect_stdout(buf):
                    psk.init(secret)
            data = secret.read_text()
            self.assertTrue(psk.FORMAT.fullmatch(data))
            self.assertNotIn(data.split('"')[1], buf.getvalue())
            self.assertEqual(secret.stat().st_mode & 0o777, 0o600)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            secret = Path(t) / "psk.secrets"
            with mock.patch.object(psk, "verify_parent", return_value=None):
                with contextlib.redirect_stdout(io.StringIO()):
                    psk.init(secret)
                with self.assertRaises(FileExistsError):
                    psk.init(secret)


if __name__ == "__main__":
    main()
