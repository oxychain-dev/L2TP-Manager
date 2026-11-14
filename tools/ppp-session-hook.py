#!/usr/bin/env python3
"""Optional pppd ip-up.d/ip-down.d identity recorder. No network changes.

pppd provides IFNAME, IPREMOTE, PEERNAME only after authentication/IPCP.
Install this exact source as executable in both pppd hook directories. It
writes root-only ephemeral state in /run/l2tp-manager/ppp-sessions.
"""
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

STATE = Path("/run/l2tp-manager/ppp-sessions")
IFACE = re.compile(r"ppp[0-9]{1,6}\Z")
USERNAME = re.compile(r"[A-Za-z0-9_-]{3,32}\Z")


def record(event, interface, username, remote):
    if not IFACE.fullmatch(interface) or not USERNAME.fullmatch(username):
        return False
    try:
        remote = str(ipaddress.IPv4Address(remote))
    except ValueError:
        return False
    if os.geteuid() != 0:
        raise PermissionError("PPP hook must be invoked as root by pppd")
    if event == "up":
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        st = STATE.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
            raise PermissionError("Insecure PPP runtime directory")
        ifindex = int((Path("/sys/class/net") / interface / "ifindex").read_text("ascii").strip())
        fd, name = tempfile.mkstemp(prefix=".ppp-", dir=str(STATE))
        try:
            with os.fdopen(fd, "w", encoding="ascii") as f:
                os.fchmod(f.fileno(), 0o600)
                json.dump({"username": username, "remote": remote,
                           "ifindex": ifindex, "since": time.time()}, f)
            os.replace(name, STATE / (interface + ".json"))
        finally:
            if os.path.exists(name):
                os.unlink(name)
    elif event == "down":
        # Do not delete the state file here. pppd can recycle pppN before a
        # delayed DOWN hook runs. Even username+remote can repeat, and DOWN
        # has no trustworthy per-session token. A late DOWN deleting a newer
        # UP record would discard verified identity. Stale records are harmless:
        # the session reader accepts them only for the matching live ifindex
        # and remote peer. /run state is discarded on reboot.
        return True
    else:
        return False
    return True


def main():
    directory = Path(sys.argv[0]).parent.name
    event = {"ip-up.d": "up", "ip-down.d": "down"}.get(directory)
    if not event:
        return
    # Never infer usernames from source WAN IP (NAT may change).
    interface = os.environ.get("IFNAME", "")
    username = os.environ.get("PEERNAME", "")
    remote = os.environ.get("IPREMOTE", "")
    record(event, interface, username, remote)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as err:
        print("PPP metadata hook error: " + str(err), file=sys.stderr)
        sys.exit(1)
