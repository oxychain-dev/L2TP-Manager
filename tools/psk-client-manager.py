#!/usr/bin/env python3
"""Manage distribution metadata for ONE shared L2TP/IPsec PSK.

A user marked 'offered' may be shown the common server PSK. This does
NOT enforce IPsec, revoke the PSK, prevent plaintext L2TP login, or
create individual IKE PSKs. These operations require root and never
print secrets unless an operator explicitly reveals them on a TTY.
"""
import argparse
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

CHAP = Path("/etc/ppp/chap-secrets")
PSK = Path("/etc/l2tp-manager/global-psk.secrets")
CONFIG = Path("/etc/l2tp-manager/psk-client-flags.json")
ACTIVE = Path("/etc/swanctl/conf.d/50-mobile-l2tp-ipsec.conf")
CANDIDATE = Path("/etc/l2tp-manager/mobile-l2tp-ipsec.candidate.conf")
LOCK = Path("/etc/l2tp-manager/.psk-client-flags.lock")
USERNAME = re.compile(r"[A-Za-z0-9_-]{3,32}\Z")
PSK_LINE = re.compile(r': PSK "([A-Za-z0-9_-]{64})"\n\Z')
SWAN_SECRET = re.compile(r'(?m)^([ \t]*secret[ \t]*=[ \t]*")([A-Za-z0-9_-]{64})("[ \t]*)$')


class Invalid(Exception):
    pass


def secure_file(path, required=True):
    try:
        st = path.lstat()
    except FileNotFoundError:
        if not required:
            return False
        raise Invalid("Required file is absent: " + str(path))
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise Invalid("File must be root-owned regular and not accessible to group/other: " + str(path))
    return True


def read_users(path=CHAP):
    secure_file(path)
    result = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            fields = shlex.split(line, comments=False, posix=True)
        except ValueError as exc:
            raise Invalid("Malformed PPP entry at line " + str(lineno)) from exc
        if len(fields) < 4:
            raise Invalid("Malformed PPP entry at line " + str(lineno))
        username, _server, password, address = fields[:4]
        if not USERNAME.fullmatch(username):
            continue  # Service/wildcard entries are not a managed user.
        if username in result:
            raise Invalid("Duplicate PPP username: " + username)
        if address != "*":
            try:
                ipaddress.IPv4Address(address)
            except ValueError as exc:
                raise Invalid("Bad assigned PPP address for " + username) from exc
        result[username] = {"password": password, "ip": address}
    return result


def load_flags(path=CONFIG):
    if not secure_file(path, required=False):
        return {"version": 1, "users": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise Invalid("Invalid PSK distribution metadata") from exc
    if not isinstance(data, dict) or set(data) != {"version", "users"} or data["version"] != 1:
        raise Invalid("Unsupported PSK distribution metadata schema")
    users = data["users"]
    if not isinstance(users, dict) or not all(
        isinstance(n, str) and USERNAME.fullmatch(n) and v is True
        for n, v in users.items()
    ):
        raise Invalid("Invalid PSK user metadata")
    return data


def load_psk(path=PSK):
    secure_file(path)
    try:
        match = PSK_LINE.fullmatch(path.read_text(encoding="ascii"))
    except (UnicodeError, OSError) as exc:
        raise Invalid("Unrecognized global PSK format") from exc
    if not match:
        raise Invalid("Unrecognized global PSK format")
    return match.group(1)


def atomic_write(path, data):
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise Invalid("Missing or unsafe output directory")
    st = path.parent.stat()
    if st.st_uid != 0 or st.st_mode & 0o022:
        raise Invalid("Output directory must be root-owned and not writable by others")
    if secure_file(path, required=False):
        pass
    fd, temporary = tempfile.mkstemp(prefix=".psk-write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            os.fchmod(out.fileno(), 0o600)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def locked():
    st = LOCK.parent.stat()
    if st.st_uid != 0 or st.st_mode & 0o077:
        raise Invalid("Manager directory must be root-owned and private")
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    lock = os.fdopen(fd, "r+")
    if not secure_file(LOCK):
        lock.close()
        raise Invalid("Unsafe lock file")
    fcntl.flock(lock, fcntl.LOCK_EX)
    return lock


def public_ip(active=ACTIVE):
    if not secure_file(active, required=False):
        return "unverified"
    data = active.read_text("ascii")
    match = re.search(r"(?m)^[ \t]*local_addrs[ \t]*=[ \t]*(\d+(?:\.\d+){3})[ \t]*$", data)
    if not match:
        return "unverified"
    try:
        addr = ipaddress.IPv4Address(match.group(1))
    except ValueError:
        return "unverified"
    p = subprocess.run(["ip", "-j", "-4", "addr", "show"], text=True, capture_output=True, check=False)
    if p.returncode:
        return "unverified"
    try:
        assigned = {x.get("local") for link in json.loads(p.stdout)
                    for x in link.get("addr_info", []) if x.get("family") == "inet"}
    except (ValueError, TypeError, AttributeError):
        return "unverified"
    return str(addr) if str(addr) in assigned else "unverified"


def tty_confirmation(prompt, required):
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise Invalid("Secret reveal or rotation requires an interactive private terminal")
    try:
        response = input(prompt)
    except EOFError as exc:
        raise Invalid("Confirmation unavailable") from exc
    if response != required:
        raise Invalid("Cancelled: confirmation does not match")


def user_status(username, users, flags):
    if username not in users:
        raise Invalid("PPP username does not exist: " + username)
    return "offered (not enforced)" if flags["users"].get(username) is True else "not offered"


def set_user(username, offered):
    with locked():
        users = read_users()
        flags = load_flags()
        if username not in users:
            raise Invalid("PPP username does not exist: " + username)
        if offered:
            load_psk()
            secure_file(ACTIVE)
            flags["users"][username] = True
        else:
            flags["users"].pop(username, None)
        atomic_write(CONFIG, json.dumps(flags, indent=2, sort_keys=True) + "\n")
    print(username + ":", "PSK details offered" if offered else "PSK details not offered")
    print("Metadata only: this is NOT an IPsec/PPP access-control rule.")


def secret_reveal(username=None):
    users = read_users()
    flags = load_flags()
    if username is not None and username not in users:
        raise Invalid("PPP username does not exist")
    offered = username is None or flags["users"].get(username) is True
    key = load_psk() if offered else None
    ip = public_ip()
    tty_confirmation("Type REVEAL to display sensitive credentials locally: ", "REVEAL")
    if username is None:
        print("GLOBAL L2TP/IPsec SHARED PSK:", key)
        print("WARNING: This is the same key for all PSK-enabled profiles.")
        return
    print("=== COPY LOCALLY ONLY; DO NOT PASTE INTO CHAT ===")
    print("VPN type:", "L2TP/IPsec PSK (if supported by device)" if offered else "L2TP (plaintext)")
    print("Server IPv4:", ip)
    print("Username:", username)
    print("PPP password:", users[username]["password"])
    print("Shared Secret (global PSK):", key if offered else "[not offered]")
    print("PPP assigned IPv4:", users[username]["ip"])
    print("NOTE: The PSK flag is only a distribution preference; it is NOT IPsec enforcement.")


def status():
    flags = load_flags()
    print("Global PSK:", "ready" if secure_file(PSK, required=False) else "missing")
    if secure_file(PSK, required=False):
        load_psk()
    print("Installed L2TP/IPsec snippet:", "present" if secure_file(ACTIVE, required=False) else "absent")
    existing = read_users()
    print("Existing PPP users offered PSK details:",
          sum(1 for name in flags["users"] if name in existing))
    print("Policy: one global PSK, not user-specific and not IPsec-only enforcement.")


def rotate():
    """Controlled common-key rotation, with best-effort config + VICI rollback."""
    tty_confirmation("Type ROTATE GLOBAL PSK (disrupts all PSK clients): ", "ROTATE GLOBAL PSK")
    with locked():
        old = load_psk()
        # Do not change PSK with active encrypted sessions.
        x = subprocess.run(["ip", "xfrm", "state", "count"], capture_output=True, text=True, check=False)
        match = re.search(r"\bSAD count\s+(\d+)", x.stdout)
        if x.returncode or not match or int(match.group(1)) != 0:
            raise Invalid("Nonzero/unknown kernel IPsec SAs; rotation refused")
        service = subprocess.run(["systemctl", "is-active", "--quiet", "strongswan.service"], check=False)
        if service.returncode:
            raise Invalid("strongSwan is not active; no live rotation permitted")
        snippets = sorted(ACTIVE.parent.glob("*.conf"))
        if snippets != [ACTIVE]:
            raise Invalid("Unknown additional swanctl snippets: rotation requires a dedicated audit")
        paths = [PSK, ACTIVE]
        if secure_file(CANDIDATE, required=False):
            paths.append(CANDIDATE)
        original = {}
        for path in paths:
            secure_file(path)
            original[path] = path.read_text(encoding="ascii")
        originals = original[ACTIVE]
        if len(SWAN_SECRET.findall(originals)) != 1 or SWAN_SECRET.search(originals).group(2) != old:
            raise Invalid("Active PSK snippet differs from validated global secret")
        for path in paths[2:]:
            data = original[path]
            if len(SWAN_SECRET.findall(data)) != 1 or SWAN_SECRET.search(data).group(2) != old:
                raise Invalid("Candidate snippet differs from validated global secret")
        new = secrets.token_urlsafe(48)
        if len(new) != 64 or not re.fullmatch(r"[A-Za-z0-9_-]{64}", new):
            raise Invalid("Generated PSK failed entropy format check")
        replacements = {PSK: ': PSK "' + new + '"\n'}
        for path in paths[1:]:
            replacements[path] = SWAN_SECRET.sub(
                lambda m: m.group(1) + new + m.group(3), original[path]
            )
        changed = []
        try:
            for path in paths:
                atomic_write(path, replacements[path])
                changed.append(path)
            r = subprocess.run(["swanctl", "--load-creds", "--noprompt"],
                               capture_output=True, text=True, check=False, timeout=25)
            if r.returncode or "loaded IKE secret" not in r.stdout:
                raise Invalid("strongSwan did not confirm the new IKE secret was loaded")
        except (OSError, subprocess.TimeoutExpired, Invalid):
            for path in reversed(changed):
                atomic_write(path, original[path])
            subprocess.run(["swanctl", "--load-creds", "--noprompt"],
                           capture_output=True, check=False, timeout=25)
            raise Invalid("Rotation failed; files restored. Verify daemon credentials before reuse.")
    print("GLOBAL PSK ROTATED; update ALL previously provisioned clients.")
    print("NEW SHARED SECRET (local terminal only):", new)
    print("No xl2tpd restart performed; existing sessions were required to be absent.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["list", "status", "set", "show", "global-status",
                                      "global-show", "global-rotate"])
    p.add_argument("--username")
    p.add_argument("--offered", choices=["yes", "no"])
    args = p.parse_args()
    if os.geteuid() != 0:
        raise Invalid("Root required")
    if args.username and not USERNAME.fullmatch(args.username):
        raise Invalid("Invalid username")
    if args.action in ("set", "status", "show") and not args.username:
        raise Invalid("--username required")
    if args.action == "list":
        users, flags = read_users(), load_flags()
        print("L2TP accounts (passwords never printed by this command):")
        for name, data in sorted(users.items()):
            print(name, "PPP IPv4:", data["ip"], "PSK details:", user_status(name, users, flags))
    elif args.action == "status":
        users, flags = read_users(), load_flags()
        print(args.username, "PSK details:", user_status(args.username, users, flags))
    elif args.action == "set":
        if not args.offered:
            raise Invalid("--offered yes/no required")
        set_user(args.username, args.offered == "yes")
    elif args.action == "show":
        secret_reveal(args.username)
    elif args.action == "global-status":
        status()
    elif args.action == "global-show":
        secret_reveal()
    elif args.action == "global-rotate":
        rotate()


if __name__ == "__main__":
    try:
        main()
    except (Invalid, OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
        sys.exit("ERROR: " + str(exc))
