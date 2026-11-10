#!/usr/bin/env python3
"""Validate/edit global L2TP IPsec policy metadata.

SECURITY: metadata is NOT an IPsec enforcement mechanism. Enforcement must
be configured on dedicated IPsec-only L2TP endpoints and verified independently.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile


CONFIG = Path("/etc/l2tp-manager/ipsec-policy.json")


def error(msg):
    raise ValueError(msg)


def read(path):
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o077:
        error("Policy file must be root-owned, regular, and mode 0600")
    obj = json.loads(path.read_text(encoding="utf-8"))
    validate(obj)
    return obj


def validate(obj):
    if not isinstance(obj, dict) or set(obj) != {"global", "endpoints", "users"}:
        error("Top level keys must be global, endpoints, users")
    gl, endpoints, users = obj["global"], obj["endpoints"], obj["users"]
    if not isinstance(gl, dict) or not isinstance(endpoints, dict) or not isinstance(users, dict):
        error("global/endpoints/users must be objects")
    if set(gl) != {"mode", "default_user_policy"}:
        error("global keys must be mode and default_user_policy")
    if gl["mode"] not in ("disabled", "dedicated-endpoints"):
        error("mode must be disabled or dedicated-endpoints")
    if gl["default_user_policy"] not in ("plaintext", "ipsec-required"):
        error("Invalid default_user_policy")
    used_listeners = set()
    has_secure_endpoint = False
    for name, ep in endpoints.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,31}", name):
            error("Invalid endpoint name")
        if not isinstance(ep, dict) or set(ep) != {"transport", "bind_ipv4", "l2tp_udp_port"}:
            error("Endpoint requires transport, bind_ipv4, l2tp_udp_port")
        if ep["transport"] not in ("plaintext", "ipsec"):
            error("Invalid endpoint transport")
        address = ipaddress.IPv4Address(ep["bind_ipv4"])
        if address.is_unspecified or address.is_multicast:
            error("Endpoint bind_ipv4 must be a specific unicast local address")
        port = ep["l2tp_udp_port"]
        if type(port) is not int or not (1 <= port <= 65535):
            error("Invalid L2TP listener UDP port")
        listener = (str(address), port)
        if listener in used_listeners:
            error("Plaintext and IPsec policies cannot share an L2TP listener")
        used_listeners.add(listener)
        has_secure_endpoint |= ep["transport"] == "ipsec"
    if gl["mode"] == "disabled" and (has_secure_endpoint or
                                    gl["default_user_policy"] == "ipsec-required"):
        error("IPsec must be enabled before assigning protected policies")
    if gl["default_user_policy"] == "ipsec-required" and not has_secure_endpoint:
        error("No separate protected listener exists")
    for username, spec in users.items():
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", username):
            error("Invalid username in policy")
        if not isinstance(spec, dict) or set(spec) != {"policy", "endpoint"}:
            error("Each user needs policy and endpoint")
        endpoint_name = spec["endpoint"]
        if endpoint_name not in endpoints:
            error("User references unknown endpoint")
        expected = "ipsec" if spec["policy"] == "ipsec-required" else "plaintext"
        if spec["policy"] not in ("plaintext", "ipsec-required"):
            error("Invalid user security policy")
        if endpoints[endpoint_name]["transport"] != expected:
            error("User policy is inconsistent with selected listener")
        if expected == "ipsec" and gl["mode"] != "dedicated-endpoints":
            error("IPsec-required user in disabled mode")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=["validate", "status", "set-user"])
    p.add_argument("--config", type=Path, default=CONFIG)
    p.add_argument("--username")
    p.add_argument("--policy", choices=["plaintext", "ipsec-required"])
    p.add_argument("--endpoint")
    a = p.parse_args()
    if os.geteuid() != 0:
        error("Root required for protected local configuration")
    cfg = read(a.config)
    if a.operation == "validate":
        print("VALID: policy structure only; no listener/IPsec enforcement was checked")
        return
    if a.operation == "status":
        print("Global:", cfg["global"])
        print("Configured endpoint names:", ", ".join(sorted(cfg["endpoints"])))
        for user, policy in sorted(cfg["users"].items()):
            print(user + ":", policy["policy"], "at", policy["endpoint"])
        print("SECURITY: endpoint and kernel XFRM/IPsec enforcement NOT VERIFIED")
        return
    if not a.username or not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", a.username):
        error("--username must be a valid L2TP account")
    if not a.policy or not a.endpoint:
        error("--policy and --endpoint are required")
    cfg["users"][a.username] = {"policy": a.policy, "endpoint": a.endpoint}
    validate(cfg)
    # Only updates metadata. It deliberately does not touch PPP, IPsec or services.
    fd, name = tempfile.mkstemp(prefix=".ipsec-policy-", dir=a.config.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(cfg, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        os.replace(name, a.config)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print("Policy metadata updated for", a.username)
    print("NOT ENFORCED: configure and verify dedicated IPsec-only endpoint before use")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        sys.exit("ERROR: " + str(exc))
