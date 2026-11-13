#!/usr/bin/env python3
"""Regression checks for generated mobile IKEv2 EAP profiles."""
import importlib.util
import json
from pathlib import Path
import plistlib
import unittest
import uuid


source = Path(__file__).resolve().parent.parent / "tools" / "mobile-profiles.py"
spec = importlib.util.spec_from_file_location("mobile_profiles", source)
mobile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)


class MobileProfiles(unittest.TestCase):
    def test_iphone_ikev2_eap_with_both_families(self):
        profile = mobile.iphone_payload("vpn.example.org", "test_account", "Test",
                                        str(uuid.uuid4()).upper())
        raw = plistlib.dumps(profile)
        result = plistlib.loads(raw)
        vpn = result["PayloadContent"][0]
        self.assertEqual(vpn["PayloadType"], "com.apple.vpn.managed")
        self.assertEqual(vpn["VPNType"], "IKEv2")
        cfg = vpn["IKEv2"]
        self.assertEqual(cfg["RemoteIdentifier"], "vpn.example.org")
        self.assertEqual(cfg["LocalIdentifier"], "test_account")
        self.assertEqual(cfg["AuthenticationMethod"], "None")
        self.assertEqual(cfg["ExtendedAuthEnabled"], 1)
        self.assertEqual(cfg["IncludeAllNetworks"], 1)
        self.assertNotIn("AuthPassword", cfg)
        self.assertNotIn("SharedSecret", cfg)
        self.assertNotIn("PayloadCertificateUUID", cfg)

    def test_android_strongswan_eap_with_both_ip_blocks(self):
        profile = mobile.android_payload("vpn.example.org", "test_account", "Test")
        raw = json.dumps(profile)
        cfg = json.loads(raw)
        self.assertEqual(cfg["type"], "ikev2-eap")
        self.assertEqual(cfg["remote"]["id"], "vpn.example.org")
        self.assertEqual(cfg["remote"]["addr"], "vpn.example.org")
        self.assertEqual(cfg["local"]["eap_id"], "test_account")
        self.assertEqual(cfg["split-tunneling"], {
            "block-ipv4": True, "block-ipv6": True
        })
        self.assertNotIn("shared_secret", raw)
        self.assertNotIn("password", raw)

    def test_both_files_have_distinct_formats(self):
        output = mobile.build({"server_id": "vpn.example.org"}, "test_account",
                              "both", "Test")
        self.assertEqual(set(output), {"test_account.mobileconfig", "test_account.sswan"})
        plistlib.loads(output["test_account.mobileconfig"])
        json.loads(output["test_account.sswan"])


if __name__ == "__main__":
    unittest.main()
