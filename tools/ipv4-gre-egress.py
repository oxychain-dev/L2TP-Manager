#!/usr/bin/env python3
"""Scoped IPv4 GRE egress: audit or reconcile ONE PPP client's public IPv4 path.

No host addresses are compiled into this program. Configure them in a
root-owned, non-writable-by-others JSON file. Never touches any default route,
WARP interface, service, existing PPP connection or global firewall policy.
"""
import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path


class Abort(RuntimeError):
    pass


def run(*args, allow_failure=False):
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode and not allow_failure:
        raise Abort("Failed: " + " ".join(args) + ": " + result.stderr.strip())
    return result


def load(filename):
    path = Path(filename)
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or (st.st_mode & 0o022):
        raise Abort("Configuration must be a root-owned regular file without group/world writes")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    if type(cfg) is not dict:
        raise Abort("Expected JSON object")
    required = {"client_ipv4", "gre_interface", "gre_peer_ipv4", "wan_interface"}
    if not required.issubset(cfg):
        raise Abort("Missing keys: " + ", ".join(sorted(required - cfg.keys())))
    if set(cfg) != required:
        raise Abort("Unsupported config key(s): " + ", ".join(sorted(set(cfg) - required)))
    ip = ipaddress.IPv4Address(cfg["client_ipv4"])
    if not ip.is_private:
        raise Abort("Selected PPP peer must be an RFC1918 address")
    cfg["client_ipv4"] = str(ip)
    cfg["gre_peer_ipv4"] = str(ipaddress.IPv4Address(cfg["gre_peer_ipv4"]))
    for key in ("gre_interface", "wan_interface"):
        val = cfg[key]
        if not isinstance(val, str) or not re.fullmatch(r"[A-Za-z0-9_.@-]{1,15}", val):
            raise Abort("Invalid interface name for " + key)
    if cfg["gre_interface"] == cfg["wan_interface"]:
        raise Abort("GRE and WAN interfaces must be different")
    return cfg


def route_line(prefix):
    return run("ip", "-4", "route", "show", "exact", prefix).stdout.strip()


def firewall_rule(table, chain, rule, action, dry_run):
    base = ["iptables", "-w", "5", "-t", table]
    matches = run(*(base + ["-C", chain] + rule), allow_failure=True).returncode == 0
    if action == "add" and not matches:
        argv = base + ["-I", chain, "1"] + rule
    elif action == "remove" and matches:
        argv = base + ["-D", chain] + rule
    else:
        return
    if dry_run:
        print("PROPOSED:", " ".join(argv))
    else:
        run(*argv)


def validate_egress(cfg):
    gre, wan, peer, client = (cfg[k] for k in
                              ("gre_interface", "wan_interface",
                               "gre_peer_ipv4", "client_ipv4"))
    for iface in (gre, wan):
        run("ip", "-4", "link", "show", "dev", iface)
    if run("sysctl", "-n", "net.ipv4.ip_forward").stdout.strip() != "1":
        raise Abort("IPv4 forwarding must already be enabled (no global sysctl changes)")
    to_peer = run("ip", "-4", "route", "get", peer).stdout.strip()
    if ("dev " + gre) not in to_peer:
        raise Abort("IPv4 GRE peer is not routed through configured GRE: " + to_peer)
    external = run("ip", "-4", "route", "get", "1.1.1.1", "from", client, "iif", gre).stdout.strip()
    if ("dev " + wan) not in external:
        raise Abort("FORWARDED client traffic does not currently choose configured WAN: " + external)
    existing = route_line(client + "/32")
    if existing and not (("via " + peer) in existing and ("dev " + gre) in existing):
        raise Abort("A conflicting route already exists: " + existing)
    return existing, external


def rules(cfg):
    gre, wan, client = (cfg[k] for k in ("gre_interface", "wan_interface", "client_ipv4"))
    return [
        ("filter", "FORWARD", ["-i", gre, "-o", wan, "-s", client + "/32", "-j", "ACCEPT"]),
        ("filter", "FORWARD", ["-i", wan, "-o", gre, "-d", client + "/32",
                              "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"]),
        ("nat", "POSTROUTING", ["-s", client + "/32", "-o", wan, "-j", "MASQUERADE"])
    ]


def audit(cfg):
    client = cfg["client_ipv4"]
    print("=== Client-specific IPv4 GRE egress audit ===")
    print("GRE:", cfg["gre_interface"], "WAN:", cfg["wan_interface"])
    for command in [
        ["ip", "-4", "rule", "show"],
        ["ip", "-4", "route", "get", "1.1.1.1", "from", client, "iif", cfg["gre_interface"]],
        ["ip", "-4", "route", "get", cfg["gre_peer_ipv4"]],
        ["ip", "-4", "route", "get", client],
        ["ip", "-4", "route", "show", "exact", client + "/32"]
    ]:
        outcome = run(*command, allow_failure=True)
        print("$", " ".join(command))
        print((outcome.stdout or outcome.stderr).strip() or "(no result)")
    print("IPv4 forward:", run("sysctl", "-n", "net.ipv4.ip_forward").stdout.strip())
    for table, chain, rule in rules(cfg):
        ok = run("iptables", "-w", "5", "-t", table, "-C", chain,
                 *rule, allow_failure=True).returncode == 0
        print(table, chain, "installed" if ok else "missing", " ".join(rule))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["audit", "apply", "remove"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise Abort("Run as root")
    cfg = load(args.config)
    if args.action == "audit":
        audit(cfg)
        return
    if args.action == "apply":
        existing, egress = validate_egress(cfg)
        print("Verified forwarded route:", egress)
        for table, chain, rule in rules(cfg):
            # Refuse conflicting NAT ownership for this exact source+egress.
            if table == "nat":
                for line in run("iptables", "-w", "5", "-t", "nat", "-S", "POSTROUTING").stdout.splitlines():
                    if ("-s " + cfg["client_ipv4"] + "/32") in line and (
                            "-o " + cfg["wan_interface"]) in line and (
                            "-j MASQUERADE" not in line):
                        raise Abort("Conflicting NAT rule: " + line)
        route = ["ip", "-4", "route", "add", cfg["client_ipv4"] + "/32", "via",
                 cfg["gre_peer_ipv4"], "dev", cfg["gre_interface"]]
        if not existing:
            if args.dry_run:
                print("PROPOSED:", " ".join(route))
            else:
                run(*route)
        for table, chain, rule in rules(cfg):
            firewall_rule(table, chain, rule, "add", args.dry_run)
    else:
        # Never remove a route/rule unless the exact target still matches.
        for table, chain, rule in reversed(rules(cfg)):
            firewall_rule(table, chain, rule, "remove", args.dry_run)
        existing = route_line(cfg["client_ipv4"] + "/32")
        if existing and (("via " + cfg["gre_peer_ipv4"]) in existing and
                         ("dev " + cfg["gre_interface"]) in existing):
            route = ["ip", "-4", "route", "del", cfg["client_ipv4"] + "/32",
                     "via", cfg["gre_peer_ipv4"], "dev", cfg["gre_interface"]]
            if args.dry_run:
                print("PROPOSED:", " ".join(route))
            else:
                run(*route)


if __name__ == "__main__":
    try:
        main()
    except (Abort, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        sys.exit("ERROR: " + str(exc))
