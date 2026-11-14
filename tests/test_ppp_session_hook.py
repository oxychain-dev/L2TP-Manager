#!/usr/bin/env python3
"""Pure regression tests for PPP hook session-generation safety."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "ppp-session-hook.py"
SPEC = importlib.util.spec_from_file_location("plain_l2tp_ppp_hook", SOURCE)
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


class PppHookTests(unittest.TestCase):
    def test_delayed_down_does_not_remove_new_up_for_same_ifname_and_peer(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            filename = state / "ppp0.json"
            new_generation = {
                "username": "ca2name",
                "remote": "172.16.101.13",
                "ifindex": 412,
                "since": 12345678.0
            }
            filename.write_text(json.dumps(new_generation), encoding="ascii")
            with mock.patch.object(hook.os, "geteuid", return_value=0):
                self.assertTrue(hook.record("down", "ppp0", "ca2name", "172.16.101.13"))
            self.assertEqual(json.loads(filename.read_text("ascii")), new_generation)

    def test_invalid_interface_or_peer_rejected_without_side_effects(self):
        with mock.patch.object(hook.os, "geteuid", return_value=0):
            self.assertFalse(hook.record("up", "tun0", "ca2name", "172.16.101.13"))
            self.assertFalse(hook.record("up", "ppp0", "ca2name", "not-ip"))
            self.assertFalse(hook.record("up", "ppp0", "../invalid", "172.16.101.13"))


if __name__ == "__main__":
    unittest.main()
