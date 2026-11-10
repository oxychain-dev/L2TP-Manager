#!/usr/bin/env python3
"""Reconcile routed direct-L2TP IPv6 for explicitly assigned PPP clients.

Host-specific root-owned JSON; no service or firewall reset. The managed chain
is isolated; never flush built-in tables. Designed for a persistent oneshot
systemd timer and PPP lifecycle callbacks. Requires iproute2 + ip6tables.
"""
import argparse
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

CHAIN = "L2TP_DIRECT6"
JUMP = ["-m", "comment", "--comment", "l2tp-direct6-owned", "-j", CHAIN]
TAG = "l2tp-direct6-owned"


class Failure(Exception):
    pass


def run(*args, optional=False):
    p = subprocess.run(args, capture_output=True, text=True, check=False)
    if p.returncode and not optional:
        raise Failure("Command failed: " + " ".join(args) + ": " + p.stderr.strip())
    return p


def emit(argv, dry):
    if dry:
        print("PROPOSED:", shlex.join(argv))
    else:
        run(*argv)


def parse_config(path):
    file = Path(path)
    st = file.lstat()
    if not file.is_file() or file.is_symlink() or st.st_uid != 0 or st.st_mode & 0o077:
        raise Failure("Require root-owned regular JSON, mode 0600")
    cfg = json.loads(file.read_text(encoding="utf-8"))
    required = {"wan_interface", "wan_ipv6", "direct_prefix",
                "table", "priority", "clients"}
    if not isinstance(cfg, dict) or set(cfg) != required:
        raise Failure("Config fields must be: " + ", ".join(sorted(required)))
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,15}", cfg["wan_interface"]):
        raise Failure("Invalid WAN interface")
    ip6 = ipaddress.IPv6Address(cfg["wan_ipv6"])
    if not ip6.is_global:
        raise Failure("WAN must have public IPv6")
    cfg["wan_ipv6"] = str(ip6)
    prefix = ipaddress.IPv6Network(cfg["direct_prefix"], strict=True)
    if prefix.prefixlen != 48 or not prefix.subnet_of(ipaddress.IPv6Network("fd00::/8")):
        raise Failure("Direct prefix must be ULA /48")
    cfg["direct_prefix"] = str(prefix)
    if type(cfg["table"]) is not int or not (1 <= cfg["table"] <= 2**31 - 1):
        raise Failure("Invalid policy table")
    if type(cfg["priority"]) is not int or not (100 <= cfg["priority"] <= 32760):
        raise Failure("Invalid rule priority")
    if not isinstance(cfg["clients"], list) or not cfg["clients"]:
        raise Failure("Nonempty clients array required")
    seen_v4, seen_v6 = set(), set()
    clients = []
    for item in cfg["clients"]:
        if not isinstance(item, dict) or set(item) != {"peer_ipv4", "client_ipv6"}:
            raise Failure("Client must contain peer_ipv4 and client_ipv6")
        v4 = ipaddress.IPv4Address(item["peer_ipv4"])
        v6 = ipaddress.IPv6Network(item["client_ipv6"], strict=True)
        if not v4.is_private or v6.prefixlen != 128 or not v6.subnet_of(prefix):
            raise Failure("Invalid client peer or IPv6 assignment")
        if str(v4) in seen_v4 or str(v6) in seen_v6:
            raise Failure("Duplicate client address allocation")
        seen_v4.add(str(v4))
        seen_v6.add(str(v6))
        clients.append({"peer_ipv4": str(v4), "client_ipv6": str(v6)})
    cfg["clients"] = clients
    return cfg


def ipv6_wan(cfg):
    wan = cfg["wan_interface"]
    links = json.loads(run("ip", "-j", "-6", "addr", "show", "dev", wan).stdout)
    actual = {
        row.get("local") for link in links
        for row in link.get("addr_info", []) if row.get("family") == "inet6"
    }
    if cfg["wan_ipv6"] not in actual:
        raise Failure("Configured public IPv6 not present on verified WAN")
    routes = json.loads(run("ip", "-j", "-6", "route", "show",
                            "table", "main", "default").stdout)
    choices = [r for r in routes if r.get("dev") == wan
               and r.get("gateway") and r.get("dst") == "default"]
    if len(choices) != 1:
        raise Failure("Expected one usable public-WAN IPv6 default; no changes")
    return choices[0]["gateway"]


def ppp_sessions():
    found = {}
    for path in sorted(Path("/sys/class/net").glob("ppp*")):
        iface = path.name
        out = run("ip", "-o", "-4", "addr", "show", "dev", iface, optional=True)
        if out.returncode:
            continue
        for match in re.finditer(r"\bpeer (\d+\.\d+\.\d+\.\d+)/32\b", out.stdout):
            peer = match.group(1)
            if peer in found:
                raise Failure("Duplicate connected PPP peer: " + peer)
            v6 = run("ip", "-o", "-6", "addr", "show", "dev", iface).stdout
            if "inet6 fe80:" in v6.lower():
                found[peer] = iface
    return found


def check_table(cfg):
    table = str(cfg["table"])
    entries = run("ip", "-6", "route", "show", "table", table, optional=True).stdout
    for entry in entries.splitlines():
        if not (entry.startswith("default via ") or
                entry.startswith("unreachable default")):
            raise Failure("Routing table has unrelated entries: " + entry)
        if entry.startswith("default via ") and (
                "dev " + cfg["wan_interface"]) not in entry:
            raise Failure("Routing table default points to a different interface")


def policy(cfg, action, dry):
    pref, cidr, table = str(cfg["priority"]), cfg["direct_prefix"], str(cfg["table"])
    entries = [line for line in run("ip", "-6", "rule", "show").stdout.splitlines()
               if line.split(":", 1)[0].strip() == pref]
    expected = "from " + cidr + " lookup " + table
    if entries and (len(entries) != 1 or expected not in entries[0]):
        raise Failure("Policy priority belongs to another rule: " + pref)
    if action == "apply" and not entries:
        emit(["ip", "-6", "rule", "add", "pref", pref, "from",
              cidr, "lookup", table], dry)
    if action == "remove" and entries:
        emit(["ip", "-6", "rule", "del", "pref", pref, "from",
              cidr, "lookup", table], dry)


def get_rules(chain, table=None):
    command = ["ip6tables", "-w", "5"]
    if table:
        command += ["-t", table]
    p = run(*(command + ["-S", chain]), optional=True)
    if p.returncode:
        return None
    return [shlex.split(line)[2:] for line in p.stdout.splitlines()
            if line.startswith("-A " + chain + " ")]


def sync_chain(desired, dry):
    current = get_rules(CHAIN)
    if current is None:
        emit(["ip6tables", "-w", "5", "-N", CHAIN], dry)
        current = []
    jump_rules = get_rules("FORWARD")
    if jump_rules is None:
        raise Failure("FORWARD chain unavailable")
    if JUMP not in jump_rules:
        emit(["ip6tables", "-w", "5", "-I", "FORWARD", "1"] + JUMP, dry)
    for old in current:
        # This is a privately owned chain. Refuse to delete unknown rules.
        if TAG not in old:
            raise Failure("Unrecognized rule in privately owned chain")
    if desired == current:
        return
    # Insert the new rules first, before removing stale rules. Short-lived
    # duplicates stay within the managed client scope, never built-in tables.
    for rule in reversed(desired):
        emit(["ip6tables", "-w", "5", "-I", CHAIN, "1"] + rule, dry)
    for old in current:
        emit(["ip6tables", "-w", "5", "-D", CHAIN] + old, dry)


def nat_rule(cfg, client):
    return ["-s", client["client_ipv6"], "-o", cfg["wan_interface"],
            "-m", "comment", "--comment", TAG,
            "-j", "SNAT", "--to-source", cfg["wan_ipv6"]]


def reconcile_nat(cfg, action, dry):
    current = get_rules("POSTROUTING", "nat")
    if current is None:
        raise Failure("IPv6 nat POSTROUTING unavailable")
    own = [r for r in current if TAG in r]
    desired = [nat_rule(cfg, c) for c in cfg["clients"]] if action == "apply" else []
    if any(r not in desired and r not in [nat_rule(cfg, c) for c in cfg["clients"]]
           for r in own):
        raise Failure("Unknown owned NAT rule; audit before modifying")
    for r in desired:
        if r not in current:
            emit(["ip6tables", "-w", "5", "-t", "nat", "-I", "POSTROUTING", "1"] + r, dry)
    for r in own:
        if r not in desired:
            emit(["ip6tables", "-w", "5", "-t", "nat", "-D", "POSTROUTING"] + r, dry)


def client_rules(cfg, sessions):
    rules = []
    wan = cfg["wan_interface"]
    for client in cfg["clients"]:
        prefix = client["client_ipv6"]
        iface = sessions.get(client["peer_ipv4"])
        if iface:
            rules.append(["-i", iface, "-o", wan, "-s", prefix,
                          "-m", "comment", "--comment", TAG, "-j", "ACCEPT"])
            rules.append(["-i", wan, "-o", iface, "-d", prefix,
                          "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED",
                          "-m", "comment", "--comment", TAG, "-j", "ACCEPT"])
        rules.append(["-s", prefix, "-m", "comment", "--comment", TAG, "-j", "DROP"])
    return rules


def client_routes(cfg, sessions, action, dry):
    for client in cfg["clients"]:
        prefix = client["client_ipv6"]
        current = run("ip", "-6", "route", "show", "exact", prefix).stdout.strip()
        iface = sessions.get(client["peer_ipv4"]) if action == "apply" else None
        if current and not re.search(r"\bdev ppp\d+\b", current):
            raise Failure("Client return route owned by another network: " + current)
        if iface and ("dev " + iface) in current:
            continue
        if iface:
            emit(["ip", "-6", "route", "replace", prefix, "dev", iface], dry)
        elif current:
            emit(["ip", "-6", "route", "del", prefix], dry)


def table_routes(cfg, gateway, action, dry):
    t = str(cfg["table"])
    existing = run("ip", "-6", "route", "show", "table", t, optional=True).stdout
    if action == "apply":
        emit(["ip", "-6", "route", "replace", "unreachable", "default",
              "metric", "42700", "table", t], dry)
        desired = ["ip", "-6", "route", "replace", "default", "via",
                   gateway, "dev", cfg["wan_interface"], "metric", "10", "table", t]
        emit(desired, dry)
    else:
        for line in existing.splitlines():
            if line.startswith("default via "):
                gw = line.split()[2]
                emit(["ip", "-6", "route", "del", "default", "via", gw,
                      "dev", cfg["wan_interface"], "metric", "10", "table", t], dry)
            elif line.startswith("unreachable default"):
                emit(["ip", "-6", "route", "del", "unreachable", "default",
                      "table", t], dry)


def inspect(cfg):
    print("Configured:", json.dumps(cfg, indent=2))
    print("Live PPP:", ppp_sessions())
    print("Source rules:", run("ip", "-6", "rule", "show").stdout)
    print("Table:", run("ip", "-6", "route", "show", "table",
                        str(cfg["table"]), optional=True).stdout)
    print("Managed chain:", get_rules(CHAIN))
    print("Managed NAT:", [r for r in (get_rules("POSTROUTING", "nat") or [])
                           if TAG in r])


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("action", choices=["audit", "apply", "remove"])
    arg.add_argument("--config", required=True)
    arg.add_argument("--dry-run", action="store_true")
    args = arg.parse_args()
    if os.geteuid() != 0:
        raise Failure("Root required")
    config = parse_config(args.config)
    if args.action == "audit":
        inspect(config)
        return
    if run("sysctl", "-n", "net.ipv6.conf.all.forwarding").stdout.strip() != "1":
        raise Failure("Kernel IPv6 forwarding not enabled")
    # Only one reconciler instance may edit source policies/firewall at a time.
    Path("/run/l2tp-direct6").mkdir(mode=0o700, exist_ok=True)
    with open("/run/l2tp-direct6/lock", "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        check_table(config)
        gateway = ipv6_wan(config) if args.action == "apply" else None
        sessions = ppp_sessions() if args.action == "apply" else {}
        # Fail-closed policy is maintained even while every client is offline.
        if args.action == "apply":
            table_routes(config, gateway, args.action, args.dry_run)
        policy(config, args.action, args.dry_run)
        sync_chain(client_rules(config, sessions) if args.action == "apply" else [],
                   args.dry_run)
        client_routes(config, sessions, args.action, args.dry_run)
        reconcile_nat(config, args.action, args.dry_run)
        if args.action == "remove":
            table_routes(config, None, args.action, args.dry_run)
            if not args.dry_run:
                # Remove owned jump/chain only when empty, never flush tables.
                old = get_rules("FORWARD") or []
                if JUMP in old:
                    run("ip6tables", "-w", "5", "-D", "FORWARD", *JUMP)
                run("ip6tables", "-w", "5", "-X", CHAIN)
        print("Reconciled:", args.action, "sessions:", sessions)


if __name__ == "__main__":
    try:
        main()
    except (Failure, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        sys.exit("ERROR: " + str(exc))
