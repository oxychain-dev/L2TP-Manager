#!/usr/bin/env python3
"""Stage, but never activate, IKEv1 L2TP/IPsec PSK for an existing xl2tpd server.

Only creates a root-owned swanctl candidate from the already generated global
PSK. Uses the host's single effective public IPv4 default-route source.
DOES NOT install packages, change iptables/XFRM, start strongSwan, modify
xl2tpd/PPP authentication, or promise IPsec-only enforcement. Retains legacy
plaintext L2TP access until separately scoped firewall/AAA policy is tested.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CANONICAL_PSK = Path("/etc/l2tp-manager/global-psk.secrets")
PSK_FORMAT = re.compile(r'^: PSK "([^"\r\n]+)"\n$')


class Stop(Exception):
    pass


def capture(*args):
    p = subprocess.run(args, capture_output=True, text=True, check=False)
    if p.returncode:
        raise Stop("Failed read-only probe: " + " ".join(args) + ": " + p.stderr.strip())
    return p.stdout


def load_psk(path):
    st = path.lstat()
    if path.is_symlink() or not path.is_file() or st.st_uid != 0 or st.st_mode & 0o077:
        raise Stop("PSK must be root-owned regular file, mode 0600")
    value = PSK_FORMAT.fullmatch(path.read_text("ascii"))
    if not value or not all(32 <= ord(x) <= 126 for x in value.group(1)):
        raise Stop("Invalid quoted ASCII global PSK format")
    return value.group(1)


def discover_wan():
    routes = json.loads(capture("ip", "-j", "-4", "route", "show", "default"))
    routes = [r for r in routes if r.get("dst") == "default" and r.get("dev")]
    if len(routes) != 1:
        raise Stop("Cannot uniquely identify the public default IPv4 WAN route")
    wan = routes[0]["dev"]
    ip_source = routes[0].get("prefsrc")
    if not ip_source:
        raise Stop("The default route must include a verified source IPv4")
    addr = ipaddress.IPv4Address(ip_source)
    if not addr.is_global:
        raise Stop("Default route source IPv4 is not globally routable")
    addrs = json.loads(capture("ip", "-j", "-4", "addr", "show", "dev", wan))
    assigned = {x.get("local") for link in addrs
                for x in link.get("addr_info", []) if x.get("family") == "inet"}
    if str(addr) not in assigned:
        raise Stop("IPv4 source not actually assigned to discovered WAN interface")
    return wan, str(addr)


def candidate(ipv4, key):
    # IKEv1 PSK is required for L2TP/IPsec; modern Android built-in VPN
    # has removed L2TP and will need a different IKEv2 profile.
    return (
        "connections {\n"
        "  mobile-l2tp-psk {\n"
        "    version = 1\n"
        "    local_addrs = " + ipv4 + "\n"
        "    remote_addrs = %any\n"
        "    proposals = aes256-sha256-modp2048, aes128-sha256-modp2048\n"
        "    local {\n"
        "      auth = psk\n"
        "      id = " + ipv4 + "\n"
        "    }\n"
        "    remote {\n"
        "      auth = psk\n"
        "    }\n"
        "    children {\n"
        "      l2tp-transport {\n"
        "        mode = transport\n"
        "        local_ts = dynamic[udp/1701]\n"
        "        remote_ts = dynamic[udp]\n"
        "        esp_proposals = aes256-sha256, aes128-sha256\n"
        "        rekey_time = 0s\n"
        "        dpd_action = clear\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
        "secrets {\n"
        "  ike-mobile-l2tp {\n"
        '    secret = "' + key + '"\n'
        "  }\n"
        "}\n"
    )


def save_new(path, contents):
    if not path.is_absolute() or not path.parent.is_dir() or path.parent.is_symlink():
        raise Stop("Output must be absolute within an existing directory")
    parent = path.parent.stat()
    if parent.st_uid != 0 or parent.st_mode & 0o077:
        raise Stop("Output parent directory must be root-owned and mode 0700")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(contents)
        out.flush()
        os.fsync(out.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["audit", "stage"])
    parser.add_argument("--psk-file", type=Path, default=CANONICAL_PSK)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise Stop("Root required")
    key = load_psk(args.psk_file)
    iface, public = discover_wan()
    print("L2TP/IPsec server:", public, "WAN:", iface)
    print("Global PSK:", "validated (secret never displayed)")
    if args.action == "audit":
        print("Not evidence of an installed or active IPsec daemon")
        return
    if args.output is None:
        raise Stop("--output required for stage")
    save_new(args.output, candidate(public, key))
    print("Wrote inactive, root-only strongSwan IKEv1 L2TP candidate:", args.output)
    print("No active daemon/firewall/PPP change; swanctl load and live client test REQUIRED")
    print("Existing plaintext L2TP listener remains reachable until explicitly restricted")


if __name__ == "__main__":
    try:
        main()
    except (Stop, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        sys.exit("ERROR: " + str(exc))
