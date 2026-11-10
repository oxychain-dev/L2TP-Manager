#!/usr/bin/env python3
"""Pure unit checks: policy validation has no host dependencies or secrets."""
import copy
import importlib.util
from pathlib import Path
import unittest


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


ROOT = Path(__file__).resolve().parent.parent
ipsec = module("policy", ROOT / "tools" / "ipsec-policy.py")
egress = module("egress", ROOT / "tools" / "ipv4-gre-egress.py")


class Tests(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "global": {"mode": "disabled", "default_user_policy": "plaintext"},
            "endpoints": {},
            "users": {}
        }

    def test_disabled_clean(self):
        self.assertTrue(ipsec.validate(self.cfg))

    def test_secure_not_silently_allowed_when_off(self):
        c = copy.deepcopy(self.cfg)
        c["global"]["default_user_policy"] = "ipsec-required"
        with self.assertRaises(ValueError):
            ipsec.validate(c)

    def test_no_shared_listener(self):
        c = copy.deepcopy(self.cfg)
        c["global"]["mode"] = "dedicated-endpoints"
        c["endpoints"] = {
            "plain": {"transport": "plaintext", "bind_ipv4": "192.0.2.10",
                      "l2tp_udp_port": 1701},
            "secure": {"transport": "ipsec", "bind_ipv4": "192.0.2.10",
                       "l2tp_udp_port": 1701}
        }
        with self.assertRaises(ValueError):
            ipsec.validate(c)

    def test_correct_user_isolation_policy(self):
        c = copy.deepcopy(self.cfg)
        c["global"]["mode"] = "dedicated-endpoints"
        c["endpoints"] = {
            "plain": {"transport": "plaintext", "bind_ipv4": "192.0.2.10",
                      "l2tp_udp_port": 1701},
            "secure": {"transport": "ipsec", "bind_ipv4": "192.0.2.11",
                       "l2tp_udp_port": 1701}
        }
        c["users"]["vpn_client"] = {"policy": "ipsec-required", "endpoint": "secure"}
        self.assertTrue(ipsec.validate(c))
        c["users"]["vpn_client"]["endpoint"] = "plain"
        with self.assertRaises(ValueError):
            ipsec.validate(c)

    def test_egress_rule_scope(self):
        c = {"client_ipv4": "192.168.55.11", "gre_interface": "gre-lab",
             "gre_peer_ipv4": "10.0.1.1", "wan_interface": "wan-test"}
        rules = egress.rules(c)
        self.assertEqual(len(rules), 3)
        self.assertTrue(all("192.168.55.11/32" in args for _, _, args in rules))
        self.assertTrue(all("-j" in args for _, _, args in rules))
        self.assertFalse(any("0.0.0.0/0" in args for _, _, args in rules))


if __name__ == "__main__":
    unittest.main()
