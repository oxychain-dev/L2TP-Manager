#!/usr/bin/env python3
"""Pure tests for safe phase-one read-only IPsec audit."""
import importlib.util
import json
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "ipsec-phase1-audit.py"
SPEC = importlib.util.spec_from_file_location("ipsec_phase1", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class AuditTests(unittest.TestCase):
    def test_loaded_connection_requires_actual_ike(self):
        self.assertTrue(mod.loaded_connection("mobile-l2tp-psk: IKEv1, reauthentication every 14400s", "mobile-l2tp-psk"))
        self.assertFalse(mod.loaded_connection("no connections found, 0 unloaded", "mobile-l2tp-psk"))
        self.assertFalse(mod.loaded_connection("other: IKEv1", "mobile-l2tp-psk"))

    def test_xfrm_count(self):
        self.assertEqual(mod.xfrm_count("SAD count 0\n"), 0)
        self.assertEqual(mod.xfrm_count("SAD count 2\n"), 2)
        self.assertIsNone(mod.xfrm_count("not available"))

    def test_ppp_peer_dynamic_and_no_unrelated_interface(self):
        data = [
            {"ifname": "ppp2", "addr_info": [{"family": "inet", "local": "172.16.101.1", "peer": "172.16.101.10/32"}]},
            {"ifname": "ppp0", "addr_info": [{"family": "inet", "local": "172.16.101.1", "peer": "172.16.101.12/32"}]},
            {"ifname": "eth0", "addr_info": [{"family": "inet", "peer": "172.16.101.18/32"}]},
        ]
        self.assertEqual(mod.safe_ppp_peers(json.dumps(data)), ["172.16.101.10", "172.16.101.12"])
        self.assertEqual(mod.safe_ppp_peers("invalid"), [])


if __name__ == "__main__":
    unittest.main()
