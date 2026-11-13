#!/usr/bin/env python3
"""Pure-unit validation for the staged IP-address L2TP/IPsec PSK candidate."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "l2tp_legacy_ipsec", ROOT / "tools" / "l2tp-ipsec-psk.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class L2tpPskCandidate(unittest.TestCase):
    def test_ikev1_transport_psk_on_ip_not_fqdn(self):
        key = "A" * 64
        result = tool.candidate("198.51.100.14", key)
        self.assertIn("version = 1", result)
        self.assertIn("mode = transport", result)
        self.assertIn("local_ts = dynamic[udp/1701]", result)
        self.assertIn("remote_ts = dynamic[udp]", result)
        self.assertIn("local_addrs = 198.51.100.14", result)
        self.assertIn('secret = "' + key + '"', result)
        self.assertNotIn("EAP", result)
        self.assertNotIn("xl2tpd", result)

    def test_existing_global_file_pattern_requires_long_generated_key(self):
        self.assertIsNotNone(tool.PSK_FORMAT.fullmatch(': PSK "' + "A" * 64 + '"\n'))
        self.assertIsNone(tool.PSK_FORMAT.fullmatch(': PSK "oxychanin"\n'))
        self.assertIsNone(tool.PSK_FORMAT.fullmatch(': PSK "A B"\n'))


if __name__ == "__main__":
    unittest.main()
