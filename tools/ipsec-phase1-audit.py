#!/usr/bin/env python3
"""Read-only L2TP/IPsec phase-1 server audit; never dumps keys or passwords.

Use after an actual client connection attempt. This is NOT a connectivity
test from the device and does not mark production readiness.
"""
import argparse
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys

EXPECTED_CONN = "mobile-l2tp-psk"
SAFE_CONN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def command(args):
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=12,
                           check=False)
        return p.returncode, p.stdout
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return 127, ""


def service_state(service):
    status, out = command(["systemctl", "is-active", service])
    return out.strip() if status == 0 else "not-active-or-unavailable"


def loaded_connection(output, name):
    # Never report a connection as configured on the basis of daemon status.
    return bool(re.search(r"(?m)^\s*" + re.escape(name) + r": IKEv[12]\b", output))


def safe_ppp_peers(output):
    try:
        links = json.loads(output)
        peers = set()
        for link in links:
            if not re.fullmatch(r"ppp[0-9]+", link.get("ifname", "")):
                continue
            for value in link.get("addr_info", []):
                if value.get("family") == "inet" and value.get("peer"):
                    peer = value["peer"].split("/", 1)[0]
                    peers.add(str(ipaddress.IPv4Address(peer)))
        return sorted(peers, key=ipaddress.IPv4Address)
    except (ValueError, KeyError, TypeError, AttributeError):
        return []


def xfrm_count(output):
    match = re.search(r"\bSAD count\s+(\d+)", output)
    return int(match.group(1)) if match else None


def run():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expect-connection", default=EXPECTED_CONN,
                   help="Connection name expected in swanctl --list-conns")
    p.add_argument("--expect-ppp-peer",
                   help="Optional verified IPv4 PPP peer to check")
    args = p.parse_args()

    if os.geteuid() != 0:
        sys.exit("ERROR: Run as root to inspect IPsec service state.")
    if not SAFE_CONN.fullmatch(args.expect_connection):
        sys.exit("ERROR: Invalid connection name.")
    expected_peer = None
    if args.expect_ppp_peer:
        try:
            expected_peer = str(ipaddress.IPv4Address(args.expect_ppp_peer))
        except ipaddress.AddressValueError:
            sys.exit("ERROR: Invalid PPP peer IPv4.")

    print("=== Read-only Phase 1 L2TP/IPsec audit ===")
    for service in ("xl2tpd.service", "strongswan.service", "l2tp-direct6.timer"):
        print("SERVICE", service, service_state(service))

    code, conn_text = command(["swanctl", "--list-conns"])
    loaded = code == 0 and loaded_connection(conn_text, args.expect_connection)
    print("LOADED_CONNECTION", args.expect_connection, "yes" if loaded else "no")
    if code != 0:
        print("NOTE: Could not query swanctl --list-conns (service/privileges/tool).")

    code, sa_text = command(["ip", "xfrm", "state", "count"])
    sa = xfrm_count(sa_text) if code == 0 else None
    print("KERNEL_IPSEC_SA_COUNT", sa if sa is not None else "unknown")

    code, addr_text = command(["ip", "-j", "-4", "address", "show"])
    peers = safe_ppp_peers(addr_text) if code == 0 else []
    print("ACTIVE_PPP_PEER_COUNT", len(peers))
    if expected_peer:
        print("EXPECTED_PPP_PEER", expected_peer,
              "present" if expected_peer in peers else "not-present")
    else:
        print("NOTE: No target PPP peer specified, so authentication cannot be correlated.")

    if not loaded or sa is None or sa == 0:
        print("RESULT: No verified encrypted client session. Do NOT mark test passed.")
    else:
        print("RESULT: IPsec candidate and kernel SA observed; NOT proof the")
        print("        requested PPP user is protected or has Internet access.")
    print("NEXT: Validate a specific client with IKE/CHILD_SA, PPP identity,")
    print("      protected UDP 1701, and IPv4/IPv6 HTTPS from the device.")
    print("No secret files, PPP passwords, xfrm keys or journal payloads printed.")


if __name__ == "__main__":
    run()
