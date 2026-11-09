#!/usr/bin/env python3
"""Opt-in, host-neutral IPv6 over PPP -> GRE egress helper.

All addresses/interfaces live in root-owned instance JSON. This tool does
not create tunnels, configure the remote router, or change default host routes.
"""
import argparse
import ipaddress
import json
import os
import re
import secrets
import socket
import subprocess
import sys
from pathlib import Path


def fail(message):
    raise ValueError(message)


def ula():
    ident = secrets.randbits(40)
    prefix = ipaddress.IPv6Network((int(ipaddress.IPv6Address("fd00::")) | (ident << 80), 48))
    router = ipaddress.IPv6Address(int(prefix.network_address) + 0x11)
    lan = ipaddress.IPv6Network((int(prefix.network_address) + (1 << 64), 64))
    print("ULA prefix:", prefix)
    print("Router address:", str(router) + "/128")
    print("LAN prefix:", lan)
    print("LAN gateway:", str(ipaddress.IPv6Address(int(lan.network_address) + 1)) + "/64")
    print("Save these values; re-generating changes the addresses.")


def load(path):
    st = path.stat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022:
        fail("Config must be a root-owned regular file, not group/world writable")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        fail("Expected a JSON object")
    role = obj.get("role")
    if role not in ("server", "gateway"):
        fail("role must be server or gateway")
    for key in ("gre_interface", "gre_peer_ipv6"):
        if not isinstance(obj.get(key), str) or not obj[key]:
            fail("Missing " + key)
    for key in ("gre_interface", "wan_interface"):
        if key in obj and not re.fullmatch(r"[a-zA-Z0-9_.:@-]{1,15}", obj[key]):
            fail("Invalid interface name: " + key)
    obj["gre_peer_ipv6"] = str(ipaddress.IPv6Address(obj["gre_peer_ipv6"]))
    router = ipaddress.IPv6Network(obj["client_ipv6"], strict=True)
    if router.prefixlen != 128 or not router.subnet_of(ipaddress.IPv6Network("fd00::/8")):
        fail("client_ipv6 must be a ULA /128")
    obj["client_ipv6"] = str(router)
    if obj.get("lan_prefix"):
        lan = ipaddress.IPv6Network(obj["lan_prefix"], strict=True)
        if lan.prefixlen != 64 or not lan.subnet_of(ipaddress.IPv6Network("fd00::/8")):
            fail("lan_prefix must be a ULA /64")
        if router.subnet_of(lan):
            fail("Router /128 must not overlap LAN /64")
        obj["lan_prefix"] = str(lan)
    if role == "server":
        client = ipaddress.IPv4Address(obj["client_ipv4"])
        if not client.is_private:
            fail("client_ipv4 must be a private IPv4 peer address")
        obj["client_ipv4"] = str(client)
        table, priority = obj.get("routing_table"), obj.get("rule_priority")
        if type(table) is not int or not 1 <= table <= 2**31 - 1:
            fail("routing_table must be a valid positive integer")
        if type(priority) is not int or not 100 <= priority <= 32760:
            fail("rule_priority must be in 100..32760")
    else:
        obj["wan_ipv6"] = str(ipaddress.IPv6Address(obj["wan_ipv6"]))
        if not ipaddress.IPv6Address(obj["wan_ipv6"]).is_global:
            fail("wan_ipv6 must be a publicly routable IPv6")
        if not obj.get("wan_interface"):
            fail("Missing wan_interface")
    return obj


def call(argv, dry_run=False, capture=False, allow_missing=False):
    if dry_run:
        print("+", " ".join(argv))
        return ""
    proc = subprocess.run(argv, check=False, text=True, capture_output=True)
    if proc.returncode:
        if allow_missing:
            return ""
        fail("Command failed: " + " ".join(argv) + ": " + proc.stderr.strip())
    if not capture and proc.stdout.strip():
        print(proc.stdout.strip())
    return proc.stdout


def link_up(iface):
    if not socket.if_nametoindex(iface):
        fail("Interface unavailable: " + iface)
    result = call(["ip", "-o", "link", "show", "dev", iface], capture=True)
    if "UP" not in result.split("<", 1)[-1].split(">", 1)[0].split(","):
        fail("Interface is not UP: " + iface)


def check_own_route(prefix, expected):
    existing = call(["ip", "-6", "route", "show", "exact", prefix], capture=True)
    if existing.strip() and expected not in existing:
        fail("Conflicting route for " + prefix + ": " + existing.strip())


def rules_for(priority):
    output = call(["ip", "-6", "rule", "show"], capture=True)
    return [line for line in output.splitlines() if line.split(":", 1)[0].strip() == str(priority)]


def ensure_rule(prefix, table, priority, dry_run):
    matches = rules_for(priority)
    if matches:
        ipnet = str(ipaddress.IPv6Network(prefix).network_address)
        if len(matches) != 1 or not any(
            ("from " + p) in matches[0] and ("lookup " + str(table)) in matches[0]
            for p in (prefix, ipnet)
        ):
            fail("Policy priority already used by another rule: " + str(priority))
        return
    call(["ip", "-6", "rule", "add", "pref", str(priority),
          "from", prefix, "lookup", str(table)], dry_run)


def match_ppp(iface, client):
    link_up(iface)
    addresses = call(["ip", "-o", "-4", "addr", "show", "dev", iface], capture=True)
    if not re.search(r"\bpeer " + re.escape(client) + r"/32\b", addresses):
        return False
    ipv6 = call(["ip", "-o", "-6", "addr", "show", "dev", iface], capture=True)
    return "fe80:" in ipv6.lower()


def server_apply(cfg, iface, dry_run):
    if not iface:
        fail("--interface is required for server apply")
    if not match_ppp(iface, cfg["client_ipv4"]):
        print("No matching IPv4+IPv6 PPP session on", iface, "; no changes")
        return
    table, pref = str(cfg["routing_table"]), cfg["rule_priority"]
    # A per-source unreachable route prevents fallback to the host WAN.
    existing = call(["ip", "-6", "route", "show", "table", table],
                    capture=True, allow_missing=True)
    if any(not (line.startswith("unreachable default") or
                (line.startswith("default via " + cfg["gre_peer_ipv6"]) and
                 ("dev " + cfg["gre_interface"]) in line))
           for line in existing.splitlines()):
        fail("Routing table is not dedicated to this helper")
    prefixes = [cfg["client_ipv6"]] + ([cfg["lan_prefix"]] if cfg.get("lan_prefix") else [])
    for i, prefix in enumerate(prefixes):
        check_own_route(prefix, "dev " + iface)
    call(["ip", "-6", "route", "replace", "unreachable", "default",
          "metric", "42700", "table", table], dry_run)
    for i, prefix in enumerate(prefixes):
        ensure_rule(prefix, table, pref + i, dry_run)
    for prefix in prefixes:
        call(["ip", "-6", "route", "replace", prefix, "dev", iface], dry_run)
    link_up(cfg["gre_interface"])
    call(["ip", "-6", "route", "replace", "default", "via",
          cfg["gre_peer_ipv6"], "dev", cfg["gre_interface"],
          "metric", "10", "table", table], dry_run)


def server_down(cfg, iface, dry_run):
    # Keep the source policies and unreachable fallback in place on disconnect.
    if not iface:
        fail("--interface is required for server down")
    for prefix in [cfg["client_ipv6"]] + ([cfg["lan_prefix"]] if cfg.get("lan_prefix") else []):
        existing = call(["ip", "-6", "route", "show", "exact", prefix],
                        capture=True, allow_missing=True)
        if ("dev " + iface) in existing:
            call(["ip", "-6", "route", "del", prefix, "dev", iface], dry_run)


def firewall_rule(args, present, dry_run):
    base = ["ip6tables", "-w", "5"]
    if present:
        if subprocess.run(base + ["-C"] + args, capture_output=True).returncode:
            call(base + ["-I"] + args[:1] + ["1"] + args[1:], dry_run)
    else:
        if not subprocess.run(base + ["-C"] + args, capture_output=True).returncode:
            call(base + ["-D"] + args, dry_run)


def gateway_apply(cfg, dry_run):
    if call(["sysctl", "-n", "net.ipv6.conf.all.forwarding"], capture=True).strip() != "1":
        fail("IPv6 forwarding is not enabled")
    link_up(cfg["gre_interface"])
    link_up(cfg["wan_interface"])
    addresses = call(["ip", "-o", "-6", "addr", "show", "dev", cfg["wan_interface"]], capture=True)
    if cfg["wan_ipv6"] not in addresses:
        fail("Configured WAN IPv6 is not assigned to the WAN interface")
    prefixes = [cfg["client_ipv6"]] + ([cfg["lan_prefix"]] if cfg.get("lan_prefix") else [])
    for prefix in prefixes:
        check_own_route(prefix, "via " + cfg["gre_peer_ipv6"] + " dev " + cfg["gre_interface"])
    for prefix in prefixes:
        call(["ip", "-6", "route", "replace", prefix, "via", cfg["gre_peer_ipv6"],
              "dev", cfg["gre_interface"]], dry_run)
        firewall_rule(["FORWARD", "-i", cfg["gre_interface"], "-o",
                       cfg["wan_interface"], "-s", prefix, "-j", "ACCEPT"], True, dry_run)
        firewall_rule(["FORWARD", "-i", cfg["wan_interface"], "-o",
                       cfg["gre_interface"], "-d", prefix, "-m", "conntrack",
                       "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"], True, dry_run)
        nat = ["-t", "nat", "POSTROUTING", "-s", prefix, "-o",
               cfg["wan_interface"], "-j", "SNAT", "--to-source", cfg["wan_ipv6"]]
        if subprocess.run(["ip6tables", "-w", "5", "-t", "nat", "-C"] + nat[3:],
                          capture_output=True).returncode:
            call(["ip6tables", "-w", "5", "-t", "nat", "-I", "POSTROUTING", "1"]
                 + nat[3:], dry_run)


def gateway_down(cfg, dry_run):
    prefixes = [cfg["client_ipv6"]] + ([cfg["lan_prefix"]] if cfg.get("lan_prefix") else [])
    for prefix in prefixes:
        firewall_rule(["FORWARD", "-i", cfg["gre_interface"], "-o",
                       cfg["wan_interface"], "-s", prefix, "-j", "ACCEPT"], False, dry_run)
        firewall_rule(["FORWARD", "-i", cfg["wan_interface"], "-o",
                       cfg["gre_interface"], "-d", prefix, "-m", "conntrack",
                       "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"], False, dry_run)
        nat = ["-s", prefix, "-o", cfg["wan_interface"], "-j",
               "SNAT", "--to-source", cfg["wan_ipv6"]]
        if not subprocess.run(["ip6tables", "-w", "5", "-t", "nat", "-C", "POSTROUTING"] + nat,
                              capture_output=True).returncode:
            call(["ip6tables", "-w", "5", "-t", "nat", "-D", "POSTROUTING"] + nat, dry_run)
        existing = call(["ip", "-6", "route", "show", "exact", prefix], capture=True, allow_missing=True)
        if ("via " + cfg["gre_peer_ipv6"] + " dev " + cfg["gre_interface"]) in existing:
            call(["ip", "-6", "route", "del", prefix, "via", cfg["gre_peer_ipv6"],
                  "dev", cfg["gre_interface"]], dry_run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("generate-ula")
    for name in ("apply", "down"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", type=Path, required=True)
        cmd.add_argument("--interface", help="PPP interface provided by pppd")
        cmd.add_argument("--dry-run", action="store_true")
    opts = parser.parse_args()
    if opts.action == "generate-ula":
        ula()
        return
    if os.geteuid() != 0:
        fail("Run as root to inspect/apply system networking")
    cfg = load(opts.config)
    if cfg["role"] == "server":
        (server_apply if opts.action == "apply" else server_down)(
            cfg, opts.interface, opts.dry_run)
    else:
        (gateway_apply if opts.action == "apply" else gateway_down)(
            cfg, opts.dry_run)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
