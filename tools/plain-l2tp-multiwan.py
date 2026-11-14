#!/usr/bin/env python3
"""Plain L2TPv2/CHAP account allocation and PPP session inspection.

This is NOT a VPN endpoint implementation. No encryption, IPsec, daemon
restart, NAT or firewall changes are performed. Mutations take an advisory
flock and atomically replace only /etc/ppp/chap-secrets. All other writers
must use the same lock to guarantee concurrent account allocation.
"""
import argparse
import contextlib
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import subprocess
import sys
import tempfile
import time

CHAP = Path("/etc/ppp/chap-secrets")
FORWARDS = Path("/etc/l2tp-forwards.conf")
ROUTES = Path("/etc/l2tp-routes.conf")
RESERVED = Path("/etc/l2tp-manager/ppp-reserved-ips")
DIRECT6 = Path("/etc/l2tp-manager/direct6.json")
IPV4_EGRESS = Path("/etc/l2tp-manager/ipv4-egress.json")
LOCK = Path("/run/lock/l2tp-manager-accounts.lock")
STATE = Path("/run/l2tp-manager/ppp-sessions")
USER = re.compile(r"[A-Za-z0-9_-]{3,32}\Z")
PASSWORD = re.compile(r"[A-Za-z0-9@._+=!%:-]{12,64}\Z")
IFACE = re.compile(r"ppp[0-9]{1,6}\Z")
DISABLED = "# l2tp-manager-disabled "


class Invalid(Exception):
    pass


def secure_file(path):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise Invalid("Expected root-owned private regular file: " + str(path))
    return st


def private_chap(path=CHAP):
    return secure_file(path)


def parse_records(content):
    """Preserve opaque lines while inspecting ALL PPP credential address claims."""
    active, disabled, claimed, unknown = {}, {}, set(), []
    for i, original in enumerate(content.splitlines(keepends=True)):
        raw = original.strip()
        off = raw.startswith(DISABLED)
        if off:
            raw = raw[len(DISABLED):]
        elif not raw or raw.startswith("#"):
            continue
        try:
            fields = shlex.split(raw, comments=True, posix=True)
        except ValueError as exc:
            raise Invalid("Malformed PPP secrets entry at line " + str(i+1)) from exc
        if len(fields) < 3:
            raise Invalid("Incomplete PPP secrets entry at line " + str(i+1))
        # Reserve addresses even for non-managed server/wildcard entries.
        for address in fields[3:]:
            if address == "*":
                unknown.append(i+1)
                continue
            if address.startswith("!"):
                continue
            try:
                claimed.add(ipaddress.IPv4Network(address, strict=False))
            except ValueError:
                unknown.append(i+1)
        name = fields[0]
        if USER.fullmatch(name) and fields[1] == "*":
            dest = disabled if off else active
            if name in active or name in disabled:
                raise Invalid("Duplicate managed username at line " + str(i+1))
            if len(fields) != 4:
                raise Invalid("Managed account must have exactly one static IP: " + name)
            if fields[3] == "*":
                # Preserve old dynamic accounts as unknown; never issue a new
                # static lease until wildcard authorization is audited.
                dest[name] = ("*", i)
            else:
                try:
                    address = ipaddress.IPv4Address(fields[3])
                except ValueError as exc:
                    raise Invalid("Managed account has invalid IPv4: " + name) from exc
                dest[name] = (str(address), i)
    return active, disabled, claimed, unknown


def reference_file_safe(path):
    st = path.lstat()
    return stat.S_ISREG(st.st_mode) and st.st_uid == 0 and not (st.st_mode & 0o022)


def structured_reserved(direct6=DIRECT6, ipv4_egress=IPV4_EGRESS):
    """Keep address allocations referenced by other project-managed paths."""
    reserved = set()
    for path, field, list_field in (
        (direct6, "peer_ipv4", "clients"),
        (ipv4_egress, "client_ipv4", None),
    ):
        if not path.exists():
            continue
        if not reference_file_safe(path):
            raise Invalid("Unsafe project routing configuration: " + str(path))
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(cfg, dict):
                raise ValueError("Expected JSON object")
            entries = cfg[list_field] if list_field else [cfg]
            if not isinstance(entries, list):
                raise ValueError("Invalid client reservation list")
            for entry in entries:
                if not isinstance(entry, dict) or field not in entry:
                    raise ValueError("Invalid client reservation")
                reserved.add(ipaddress.IPv4Address(entry[field]))
        except (ValueError, TypeError, KeyError) as exc:
            raise Invalid("Invalid managed routing reservation in " + str(path)) from exc
    return reserved


def optional_reserved(path=RESERVED, forwards=FORWARDS, routes=ROUTES):
    """Address claims in forwards/routes prevent premature IP reuse."""
    used = set()
    if path.exists():
        secure_file(path)
        for raw in path.read_text("ascii").splitlines():
            token = raw.split("#", 1)[0].strip()
            if token:
                try:
                    used.add(ipaddress.IPv4Address(token))
                except ValueError as exc:
                    raise Invalid("Invalid reserved PPP IPv4 entry") from exc
    for f, index, separator in ((forwards, 2, ":"), (routes, 1, ":")):
        if not f.exists():
            continue
        # Ancillary config must not be writable by other users.
        if not reference_file_safe(f):
            raise Invalid("Unsafe reference file: " + str(f))
        for line in f.read_text("utf-8").splitlines():
            if line.lstrip().startswith("#") or not line.strip():
                continue
            parts = line.split(separator)
            if len(parts) <= index:
                continue
            try:
                used.add(ipaddress.IPv4Address(parts[index].strip()))
            except ValueError:
                pass
    return used | structured_reserved()


def kernel_sessions():
    result = subprocess.run(["ip", "-j", "-4", "address", "show"],
                            capture_output=True, text=True, timeout=12, check=False)
    if result.returncode:
        raise Invalid("Cannot read current IPv4 interfaces (ip -j failed)")
    try:
        records = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise Invalid("Cannot parse active IPv4 interface information") from exc
    found = []
    for item in records:
        interface = item.get("ifname", "")
        if not IFACE.fullmatch(interface):
            continue
        for address in item.get("addr_info", []):
            peer = address.get("peer")
            if not peer:
                continue
            try:
                remote = ipaddress.ip_interface(peer).ip
                local = ipaddress.IPv4Address(address["local"])
            except (ValueError, KeyError) as exc:
                raise Invalid("Invalid kernel PPP address on " + interface) from exc
            found.append({"ifname": interface, "remote": str(remote),
                          "local": str(local)})
    return found


def claims(network, networks, used, kernel):
    reserved = {int(ip) for ip in used if ip in network}
    for block in networks:
        if block.version != 4:
            continue
        overlap = block.overlaps(network)
        if overlap and block.num_addresses >= network.num_addresses:
            reserved.update(map(int, network))
        elif overlap:
            reserved.update(int(ip) for ip in block if ip in network)
    for entry in kernel:
        ip = ipaddress.IPv4Address(entry["remote"])
        if ip in network:
            reserved.add(int(ip))
    return reserved


def pool_config(args):
    try:
        network = ipaddress.IPv4Network(args.subnet, strict=True)
        start = ipaddress.IPv4Address(args.pool_start)
        end = ipaddress.IPv4Address(args.pool_end)
        local = ipaddress.IPv4Address(args.local_ip)
    except ValueError as exc:
        raise Invalid("Invalid network/pool address") from exc
    if (network.prefixlen < 8 or network.prefixlen > 30 or
            int(start) > int(end) or start not in network or end not in network or
            local not in network or start == network.network_address or
            end == network.broadcast_address or
            int(end) - int(start) > 4095):
        raise Invalid("Invalid or unsafe PPP allocation pool")
    if int(start) <= int(local) <= int(end):
        raise Invalid("Local PPP IP overlaps client pool")
    return network, int(start), int(end), int(local)


@contextlib.contextmanager
def locked():
    if os.geteuid() != 0:
        raise Invalid("Root required for account management")
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(fd)
        if st.st_uid != 0 or st.st_mode & 0o077:
            raise Invalid("Unsafe account lock permissions")
        with os.fdopen(fd, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield
    finally:
        # Never delete shared lock (would allow races with another inode).
        pass


def allocate(args, records, other, kernel):
    network, start, end, local = pool_config(args)
    active, disabled, ranges, unknown = records
    # Wildcard or unknown CHAP authorization could dynamically claim pool IPs.
    if unknown:
        raise Invalid("Unbounded/unknown PPP address authorizations; audit chap-secrets first")
    occupied = claims(network, ranges, other, kernel)
    occupied.add(local)
    for ip in range(start, end+1):
        if ip not in occupied:
            return str(ipaddress.IPv4Address(ip))
    raise Invalid("No safe PPP IPv4 addresses available in configured pool")


def atomic_update(path, original, updated):
    before = private_chap(path)
    if before.st_size > 1024 * 1024:
        raise Invalid("Unexpected oversized CHAP secrets file")
    fd, tmp = tempfile.mkstemp(prefix=".l2tp-accounts-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchown(stream.fileno(), before.st_uid, before.st_gid)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        # Refuse a competing out-of-band writer even though it ignored LOCK.
        current = private_chap(path)
        if current.st_ino != before.st_ino or path.read_text("utf-8") != original:
            raise Invalid("CHAP secrets changed during transaction")
        os.replace(tmp, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def update_account(args, password_override=None):
    with locked():
        private_chap()
        old = CHAP.read_text("utf-8")
        records = parse_records(old)
        active, disabled, _ranges, _unknown = records
        if not USER.fullmatch(args.username):
            raise Invalid("Username must be 3–32 ASCII letters/digits/_/-")
        kernel = kernel_sessions()
        other = optional_reserved()
        if args.action == "add":
            if args.username in active or args.username in disabled:
                raise Invalid("PPP username already exists (including disabled account)")
            if password_override is not None:
                password = password_override
            elif args.password_stdin:
                password = sys.stdin.readline().removesuffix("\n")
            else:
                raise Invalid("Account creation requires --password-stdin")
            if not PASSWORD.fullmatch(password):
                raise Invalid("PPP password must match 12–64 safe characters")
            ip = allocate(args, records, other, kernel)
            newline = "" if not old or old.endswith("\n") else "\n"
            updated = old + newline + f"{args.username} * {password} {ip}\n"
            atomic_update(CHAP, old, updated)
            print(ip)
            return
        if args.username not in active and args.username not in disabled:
            raise Invalid("Managed account was not found")
        ip, line_no = (active.get(args.username) or disabled.get(args.username))
        if ip == "*":
            raise Invalid("Legacy dynamic-IPv4 account requires a scoped migration before editing")
        live = any(entry["remote"] == ip for entry in kernel)
        if live:
            raise Invalid("PPP address is live; disconnect only this account before changing it")
        if args.action == "remove" and ipaddress.IPv4Address(ip) in other:
            raise Invalid("PPP address is referenced by a route/forward/reservation; remove dependency first")
        lines = old.splitlines(keepends=True)
        if args.action == "disable":
            if args.username in disabled:
                raise Invalid("Account already disabled")
            lines[line_no] = DISABLED + lines[line_no]
        elif args.action == "enable":
            if args.username in active:
                raise Invalid("Account already enabled")
            # Preserve this IP; reject if another active managed account claims it.
            if any(address == ip for name, (address, _) in active.items()):
                raise Invalid("Static PPP address is assigned to another active account")
            lines[line_no] = lines[line_no].removeprefix(DISABLED)
        else:
            lines.pop(line_no)
        atomic_update(CHAP, old, "".join(lines))
        print(args.action.upper() + " complete for " + args.username +
              "; existing PPP sessions were not restarted; no PSK changed")


def state_record(ifname):
    path = STATE / (ifname + ".json")
    if not path.exists():
        return None
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def observe_sessions():
    kernel = kernel_sessions()
    active, _disabled, _ranges, _unknown = parse_records(CHAP.read_text("utf-8"))
    result = []
    for entry in kernel:
        interface = entry["ifname"]
        remote = entry["remote"]
        record = state_record(interface)
        if record and record.get("remote") == remote and USER.fullmatch(record.get("username", "")):
            username = record["username"]
            source = "pppd hook"
            uptime = max(0, round(time.time() - float(record.get("since", time.time()))))
        else:
            candidates = [name for name, (ip, _) in active.items() if ip == remote]
            username = candidates[0] if len(candidates) == 1 else "unknown"
            source = "IP inference" if len(candidates) == 1 else "unverified"
            uptime = None
        counters = {}
        for counter in ("rx_bytes", "tx_bytes"):
            try:
                counters[counter] = int((Path("/sys/class/net") / interface /
                                         "statistics" / counter).read_text().strip())
            except (OSError, ValueError):
                counters[counter] = None
        result.append({**entry, "username": username, "identity_source": source,
                       "uptime_seconds": uptime, **counters})
    return result


def hook(args):
    if os.geteuid() != 0:
        raise Invalid("Root required for PPP hook")
    if not IFACE.fullmatch(args.ifname):
        raise Invalid("Invalid PPP interface")
    if not USER.fullmatch(args.username):
        return  # non-manager PPP user; do not affect other services
    remote = str(ipaddress.IPv4Address(args.remote))
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = STATE.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise Invalid("Unsafe PPP runtime state directory")
    dest = STATE / (args.ifname + ".json")
    if args.event == "down":
        current = state_record(args.ifname)
        if current and current.get("remote") == remote and current.get("username") == args.username:
            dest.unlink(missing_ok=True)
        return
    # PPP hook writes identity only; no logs, secrets, firewall or routes.
    payload = json.dumps({"remote": remote, "username": args.username,
                          "since": time.time()}) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".ppp-hook-", dir=str(STATE))
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def inspect(args):
    private_chap()
    records = parse_records(CHAP.read_text("utf-8"))
    active, disabled, networks, unknown = records
    kernel = kernel_sessions()
    sessions = observe_sessions()
    if args.action == "sessions":
        if args.json:
            print(json.dumps(sessions, indent=2))
        else:
            for x in sessions:
                print(x["ifname"], "user:", x["username"], "peer:", x["remote"],
                      "source:", x["identity_source"],
                      "uptime(s):", x["uptime_seconds"],
                      "rx_bytes:", x["rx_bytes"], "tx_bytes:", x["tx_bytes"])
            if not sessions:
                print("No active IPv4 PPP interfaces found")
        return
    for name, (ip, _) in sorted(active.items()):
        print("ENABLED", name, "IPv4:", ip)
    for name, (ip, _) in sorted(disabled.items()):
        print("DISABLED", name, "reserved IPv4:", ip)
    if args.action == "list":
        return
    from collections import Counter
    ips = Counter(ip for ip, _ in active.values())
    live = Counter(x["remote"] for x in kernel)
    for ip, count in sorted(ips.items()):
        if count > 1:
            print("CONFLICT: duplicate configured IPv4:", ip, count)
    for ip, count in sorted(live.items()):
        if count > 1:
            print("CONFLICT: duplicate live PPP peer IPv4:", ip, count)
    for entry in sessions:
        if entry["username"] == "unknown":
            print("UNKNOWN identity:", entry["ifname"], entry["remote"])
    if unknown:
        print("WARNING: wildcards/unknown address fields at CHAP lines:", unknown)
    print("PPP IPv4 active interfaces:", len(sessions))
    print("Reminder: PPP/CHAP authenticates but plain L2TP provides NO encryption")
    if args.action == "health":
        for unit in ("xl2tpd.service", "l2tp-forwards.service"):
            p = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True)
            print(unit + ":", p.stdout.strip() or "unknown")
        p = subprocess.run(["sysctl", "-n", "net.ipv4.ip_forward"], capture_output=True, text=True)
        print("IPv4 forwarding:", p.stdout.strip() if p.returncode == 0 else "unknown")
        print("NAT/firewall health requires host rule audit and real external egress tests")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "next-ip", "add", "disable", "enable",
                                          "remove", "sessions", "check", "health", "hook"])
    parser.add_argument("--username")
    parser.add_argument("--password-stdin", action="store_true")
    parser.add_argument("--subnet")
    parser.add_argument("--pool-start")
    parser.add_argument("--pool-end")
    parser.add_argument("--local-ip")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--event", choices=["up", "down"])
    parser.add_argument("--ifname")
    parser.add_argument("--remote")
    args = parser.parse_args()
    if args.action == "hook":
        if not args.event or not args.ifname or not args.remote or not args.username:
            raise Invalid("PPP hook requires event, interface, authenticated username and remote IPv4")
        hook(args)
    elif args.action == "next-ip":
        with locked():
            private_chap()
            record = parse_records(CHAP.read_text("utf-8"))
            print(allocate(args, record, optional_reserved(), kernel_sessions()))
    elif args.action in ("add", "disable", "enable", "remove"):
        if not args.username:
            raise Invalid("--username required")
        update_account(args)
    else:
        inspect(args)


if __name__ == "__main__":
    try:
        main()
    except (Invalid, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        sys.exit("ERROR: " + str(exc))
