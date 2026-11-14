#!/usr/bin/env python3
"""Offline regression tests for independent plain L2TP static PPP clients."""
import contextlib
import importlib.util
import ipaddress
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "plain-l2tp-multiwan.py"
SPEC = importlib.util.spec_from_file_location("plain_multiwan", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def pool():
    return SimpleNamespace(subnet="172.16.101.0/24",
                           pool_start="172.16.101.10",
                           pool_end="172.16.101.20",
                           local_ip="172.16.101.1")


class MultiWanTests(unittest.TestCase):
    def test_preserves_old_ca1_and_uses_free_static_address(self):
        old = "existingCA1 * LegacySafePass123! 172.16.101.10\n"
        records = mod.parse_records(old)
        self.assertEqual(mod.allocate(pool(), records, set(), []), "172.16.101.11")
        self.assertEqual(records[0]["existingCA1"][0], "172.16.101.10")

    def test_conflicting_live_peer_never_issued(self):
        records = mod.parse_records("ca1name * GoodPass12345 172.16.101.10\n")
        kernel = [{"ifname": "ppp7", "remote": "172.16.101.11",
                   "local": "172.16.101.1"}]
        self.assertEqual(mod.allocate(pool(), records, set(), kernel), "172.16.101.12")

    def test_wildcard_and_duplicate_account_rejected(self):
        records = mod.parse_records("wildname * Password12345 *\n")
        with self.assertRaises(mod.Invalid):
            mod.allocate(pool(), records, set(), [])
        with self.assertRaises(mod.Invalid):
            mod.parse_records("ca1name * GoodPass12345 172.16.101.10\n"
                              "ca1name * OtherPass1234 172.16.101.11\n")

    def test_pool_boundary_local_overlap_and_reserved_route(self):
        args = pool()
        args.local_ip = "172.16.101.10"
        with self.assertRaises(mod.Invalid):
            mod.pool_config(args)
        args.local_ip = "172.16.101.1"
        records = mod.parse_records("ca1name * GoodPass12345 172.16.101.10\n")
        self.assertEqual(mod.allocate(args, records,
                                      {ipaddress.IPv4Address("172.16.101.11")},
                                      []), "172.16.101.12")

    def test_parallel_account_creation_serialized(self):
        gate = threading.Lock()
        with tempfile.TemporaryDirectory() as directory:
            chap = Path(directory) / "chap-secrets"
            chap.write_text("ca1name * PreviousPassword12 172.16.101.10\n")
            def update(_path, _old, new):
                chap.write_text(new)
            args = pool()
            errors = []
            with (mock.patch.object(mod, "CHAP", chap),
                  mock.patch.object(mod, "locked", side_effect=lambda: gate),
                  mock.patch.object(mod, "private_chap"),
                  mock.patch.object(mod, "atomic_update", side_effect=update),
                  mock.patch.object(mod, "kernel_sessions", return_value=[]),
                  mock.patch.object(mod, "optional_reserved", return_value=set())):
                def create(name):
                    item = SimpleNamespace(**vars(args), action="add", username=name,
                                           password_stdin=True)
                    try:
                        mod.update_account(item, password_override="StrongPass123!")
                    except Exception as err:
                        errors.append(str(err))
                threads = [threading.Thread(target=create, args=(name,))
                           for name in ("tunnelCA2", "tunnelCA3")]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=3)
                self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertEqual(errors, [])
                active = mod.parse_records(chap.read_text())[0]
                self.assertEqual(active["ca1name"][0], "172.16.101.10")
                ips = [address for address, _ in active.values()]
                self.assertEqual(len(ips), len(set(ips)))
                self.assertEqual(set(ips), {"172.16.101.10",
                                            "172.16.101.11", "172.16.101.12"})

    def test_disable_keeps_reserved_and_remove_refuses_live_peer(self):
        with tempfile.TemporaryDirectory() as directory:
            chap = Path(directory) / "chap-secrets"
            chap.write_text("ca1name * PreviousPassword12 172.16.101.10\n"
                            "ca2name * AnotherPassword12 172.16.101.11\n")
            def update(_path, _old, new):
                chap.write_text(new)
            args = SimpleNamespace(action="disable", username="ca2name")
            with (mock.patch.object(mod, "CHAP", chap),
                  mock.patch.object(mod, "locked", return_value=contextlib.nullcontext()),
                  mock.patch.object(mod, "private_chap"),
                  mock.patch.object(mod, "atomic_update", side_effect=update),
                  mock.patch.object(mod, "optional_reserved", return_value=set()),
                  mock.patch.object(mod, "kernel_sessions", return_value=[])):
                mod.update_account(args)
                self.assertIn("ca2name", mod.parse_records(chap.read_text())[1])
                args.action = "remove"
                with mock.patch.object(mod, "kernel_sessions", return_value=[
                    {"ifname": "ppp1", "remote": "172.16.101.11", "local": "172.16.101.1"}
                ]):
                    with self.assertRaises(mod.Invalid):
                        mod.update_account(args)
                with mock.patch.object(mod, "optional_reserved",
                                       return_value={ipaddress.IPv4Address("172.16.101.11")}):
                    with self.assertRaises(mod.Invalid):
                        mod.update_account(args)
                mod.update_account(args)
                self.assertNotIn("ca2name", chap.read_text())
                self.assertIn("ca1name", chap.read_text())

    def test_existing_forward_ip_reservation_and_no_secret_printing(self):
        with tempfile.TemporaryDirectory() as directory:
            forwards = Path(directory) / "forward.txt"
            routes = Path(directory) / "routes.txt"
            forwards.write_text("demo:4000:172.16.101.14:8291:test\n")
            routes.write_text("192.0.2.0/24:172.16.101.15:legacy\n")
            with (mock.patch.object(mod, "RESERVED", Path(directory) / "absent"),
                  mock.patch.object(mod, "reference_file_safe", return_value=True)):
                result = mod.optional_reserved(forwards=forwards, routes=routes)
            self.assertIn(ipaddress.IPv4Address("172.16.101.14"), result)
            self.assertIn(ipaddress.IPv4Address("172.16.101.15"), result)
            with mock.patch.object(mod, "CHAP", Path(directory) / "chap"):
                mod.CHAP.write_text("ca1name * TestSecret1234 172.16.101.10\n")
                with (mock.patch.object(mod, "private_chap"),
                      mock.patch.object(mod, "kernel_sessions", return_value=[]),
                      contextlib.redirect_stdout(io.StringIO()) as capture):
                    mod.inspect(SimpleNamespace(action="list", json=False))
                self.assertNotIn("TestSecret1234", capture.getvalue())


if __name__ == "__main__":
    unittest.main()
