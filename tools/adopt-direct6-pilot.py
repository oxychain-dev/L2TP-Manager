#!/usr/bin/env python3
"""Remove ONLY the known legacy single-client direct6 pilot after migration.

Safe migration guard: the new reconciler must already have an active owned
chain hook, direct IPv6 source policy, client NAT and healthy PPP return route.
Never restore or flush an entire firewall. Dry run by default.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

OLD_TAG = "l2tp-direct6-pilot"
NEW_TAG = "l2tp-direct6-owned"
NEW_CHAIN = "L2TP_DIRECT6"


def call(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "command failed: " + shlex.join(cmd))
    return p.stdout


def rules(table, chain):
    cmd = ["ip6tables", "-w", "5"]
    if table:
        cmd += ["-t", table]
    out = call(*(cmd + ["-S", chain]))
    return [shlex.split(line)[2:] for line in out.splitlines()
            if line.startswith("-A " + chain + " ")]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True, help="Same root-only JSON as direct6 reconciler")
    p.add_argument("--apply", action="store_true", help="Execute the validated cleanup")
    p.add_argument("--legacy-priority", type=int, required=True,
                   help="Existing legacy source rule priority (operator-verified)")
    a = p.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("Root required")
    path = Path(a.config)
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o077:
        raise RuntimeError("Config must be root-owned 0600")
    cfg = json.loads(path.read_text())
    if type(cfg) is not dict or not cfg.get("clients"):
        raise RuntimeError("Invalid clients")
    sources = set()
    for c in cfg["clients"]:
        v = ipaddress.IPv6Network(c["client_ipv6"], strict=True)
        if v.prefixlen != 128:
            raise RuntimeError("Require /128")
        sources.add(str(v))
    print("Candidate client ULA list:", sorted(sources))
    new_rules = rules(None, "FORWARD")
    if not any(NEW_TAG in r and "-j" in r and NEW_CHAIN in r for r in new_rules):
        raise RuntimeError("New managed chain hook is not installed")
    if not rules(None, NEW_CHAIN):
        raise RuntimeError("New managed chain is empty; refusing migration")
    if not any(NEW_TAG in r for r in rules("nat", "POSTROUTING")):
        raise RuntimeError("New direct6 NAT not installed")
    new_policy = call("ip", "-6", "rule", "show")
    if ("from " + cfg["direct_prefix"] + " lookup " + str(cfg["table"])) not in new_policy:
        raise RuntimeError("New prefix-level policy not installed")
    legacy = []
    for table, chain in [(None, "FORWARD"), ("nat", "POSTROUTING")]:
        for r in rules(table, chain):
            if OLD_TAG not in r:
                continue
            address_fields = [
                r[i+1] for i, val in enumerate(r[:-1])
                if val in ("-s", "-d")
            ]
            if len(address_fields) != 1 or address_fields[0] not in sources:
                raise RuntimeError("Unknown legacy rule; manual audit required: " + " ".join(r))
            legacy.append((table, chain, r))
    if not legacy:
        print("No legacy pilot rules remain")
    for table, chain, r in legacy:
        cmd = ["ip6tables", "-w", "5"]
        if table:
            cmd += ["-t", table]
        cmd += ["-D", chain] + r
        print(("APPLY" if a.apply else "DRY RUN") + ":", shlex.join(cmd))
        if a.apply:
            call(*cmd)
    old = [x for x in new_policy.splitlines()
           if x.split(":", 1)[0].strip() == str(a.legacy_priority)]
    for entry in old:
        if not any(("from " + prefix.split("/")[0] + " lookup " + str(cfg["table"])) in entry
                   or ("from " + prefix + " lookup " + str(cfg["table"])) in entry
                   for prefix in sources):
            raise RuntimeError("Legacy priority is owned by another policy: " + entry)
        suffix = entry.split(":", 1)[1]
        source = next(prefix for prefix in sources if prefix.split("/")[0] in suffix)
        cmd = ["ip", "-6", "rule", "del", "pref", str(a.legacy_priority),
               "from", source, "lookup", str(cfg["table"])]
        print(("APPLY" if a.apply else "DRY RUN") + ":", shlex.join(cmd))
        if a.apply:
            call(*cmd)
    print("Legacy pilot cleanup", "completed" if a.apply else "dry-run only")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        sys.exit("ERROR: " + str(e))
