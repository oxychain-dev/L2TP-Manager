#!/usr/bin/env python3
"""Manage distribution metadata for ONE shared L2TP/IPsec PSK.

A user marked 'offered' may be shown the common server PSK. This does
NOT enforce IPsec, revoke the PSK, prevent plaintext L2TP login, or
create individual IKE PSKs. These operations require root and never
print secrets unless an operator explicitly reveals them on a TTY.
"""
import argparse
import getpass
import hmac
import string
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
PSK_LINE = re.compile(r': PSK "([^"\r\n]+)"\n\Z')
SWAN_SECRET = re.compile(r'(?m)^([ \t]*secret[ \t]*=[ \t]*")([^"\r\n]+)("[ \t]*)


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


def valid_psk(value, minimum=8, maximum=128):
    # Quoted in strongSwan and ipsec.secrets: block controls, whitespace and
    # delimiters/escapes that could change config parsing. Permit punctuation.
    return (minimum <= len(value) <= maximum
            and all(33 <= ord(ch) <= 126 and ch not in '"\\' for ch in value))


def load_psk(path=PSK):
    secure_file(path)
    try:
        match = PSK_LINE.fullmatch(path.read_text(encoding="ascii"))
    except (UnicodeError, OSError) as exc:
        raise Invalid("Unrecognized global PSK text encoding") from exc
    if not match or not valid_psk(match.group(1)):
        raise Invalid("Invalid global PSK format: expected one quoted ASCII PSK (8-128 chars)")
    return match.group(1)


def active_psk(path=ACTIVE):
    secure_file(path)
    try:
        data = path.read_text(encoding="ascii")
    except UnicodeError as exc:
        raise Invalid("Active strongSwan PSK file is not ASCII") from exc
    matches = SWAN_SECRET.findall(data)
    if len(matches) != 1 or "ike-mobile-l2tp" not in data or "mobile-l2tp-psk" not in data:
        raise Invalid("Unexpected L2TP strongSwan secret or connection structure")
    key = matches[0][1]
    if not valid_psk(key):
        raise Invalid("Active strongSwan PSK has unsupported characters")
    return key


def credentials_match():
    return hmac.compare_digest(load_psk(), active_psk())


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
            if not credentials_match():
                raise Invalid("Global PSK and active strongSwan snippet differ; use Global PSK settings to synchronize first")
            flags["users"][username] = True
        else:
            flags["users"].pop(username, None)
        atomic_write(CONFIG, json.dumps(flags, indent=2, sort_keys=True) + "\n")
    print(username + ":", "PSK details offered" if offered else "PSK details not offered")
    print("Metadata only: this is NOT an IPsec/PPP access-control rule.")


def prune():
    """Remove only obsolete distribution flags for deleted PPP usernames."""
    with locked():
        users = read_users()
        flags = load_flags()
        stale = sorted(set(flags["users"]) - set(users))
        if stale:
            for name in stale:
                del flags["users"][name]
            atomic_write(CONFIG, json.dumps(flags, indent=2, sort_keys=True) + "\n")
    print("Removed stale PSK distribution flags:", len(stale))
    print("No VPN keys or actual access permissions were revoked.")


def secret_reveal(username=None):
    users = read_users()
    flags = load_flags()
    if username is not None and username not in users:
        raise Invalid("PPP username does not exist")
    offered = username is None or flags["users"].get(username) is True
    if offered and not credentials_match():
        raise Invalid("Global PSK and active strongSwan snippet differ. Synchronize before revealing client settings.")
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
    if not secure_file(PSK, required=False):
        print("Global PSK: missing")
    else:
        try:
            key = load_psk()
        except Invalid as exc:
            print("Global PSK: invalid; " + str(exc))
        else:
            print("Global PSK: valid (" + str(len(key)) + " chars, value hidden)")
    if secure_file(ACTIVE, required=False):
        try:
            print("Active strongSwan snippet consistency:",
                  "MATCH" if credentials_match() else "MISMATCH — not synchronized")
        except Invalid as exc:
            print("Active strongSwan snippet: invalid; " + str(exc))
    else:
        print("Active strongSwan snippet: absent")
    existing = read_users()
    print("Existing PPP users offered PSK details:",
          sum(1 for name in flags["users"] if name in existing))
    print("PSK is global; offering a profile is NOT per-user IPsec enforcement.")


def rotate():
    """Synchronize global and owned strongSwan PSKs, with rollback on failure.

    Operator chooses 8-64 ASCII non-whitespace chars (or auto-generates 16).
    Do NOT change xl2tpd/PPP sessions. This touches credentials of the one
    expected IKEv1 connection; other live configurations cause refusal.
    """
    tty_confirmation("Type CHANGE GLOBAL PSK to continue: ", "CHANGE GLOBAL PSK")
    with locked():
        old = load_psk()
        x = subprocess.run(["ip", "xfrm", "state", "count"], capture_output=True,
                           text=True, check=False, timeout=15)
        match = re.search(r"\bSAD count\s+(\d+)", x.stdout)
        if x.returncode or not match or int(match.group(1)) != 0:
            raise Invalid("Active or unknown kernel IPsec SAs: cannot replace PSK safely")
        s = subprocess.run(["swanctl", "--stats"], capture_output=True,
                           text=True, check=False, timeout=15)
        if s.returncode or not re.search(r"\bIKE_SAs:\s+0\s+total\b", s.stdout):
            raise Invalid("Active or unknown IKE sessions: cannot replace PSK safely")
        if subprocess.run(["systemctl", "is-active", "--quiet",
                           "strongswan.service"], check=False).returncode:
            raise Invalid("strongSwan is not active")
        conns = subprocess.run(["swanctl", "--list-conns"], capture_output=True,
                               text=True, check=False, timeout=15)
        names = re.findall(r"(?m)^(\S+):\s+IKEv[12]\b", conns.stdout)
        if conns.returncode or names != ["mobile-l2tp-psk"]:
            raise Invalid("Unexpected loaded IPsec connections; manual audit needed")
        snippets = sorted(ACTIVE.parent.glob("*.conf"))
        if snippets != [ACTIVE]:
            raise Invalid("Other strongSwan snippets exist; refused to modify shared credentials")
        paths = [PSK, ACTIVE]
        if secure_file(CANDIDATE, required=False):
            paths.append(CANDIDATE)
        original = {path: path.read_text(encoding="ascii") for path in paths}
        if not valid_psk(active_psk()):
            raise Invalid("Invalid active PSK")
        if len(PSK_LINE.findall(original[PSK])) != 1:
            raise Invalid("Invalid global PSK structure")
        for path in paths[1:]:
            if (len(SWAN_SECRET.findall(original[path])) != 1
                    or "ike-mobile-l2tp" not in original[path]
                    or "mobile-l2tp-psk" not in original[path]):
                raise Invalid("Unexpected strongSwan candidate structure in " + str(path))

        if not credentials_match():
            print("NOTICE: The global PSK differs from the active strongSwan file.")
            print("Both will be synchronized to the new PSK. Existing values remain private.")

        proposed = getpass.getpass(
            "New PSK (8-64 printable ASCII without spaces/quotes/backslash; "
            "Enter=random 16): "
        )
        if proposed:
            confirmation = getpass.getpass("Repeat new PSK: ")
            if proposed != confirmation:
                raise Invalid("PSK confirmation mismatch")
        else:
            alphabet = string.ascii_letters + string.digits
            proposed = "".join(secrets.choice(alphabet) for _ in range(16))
        if not valid_psk(proposed, minimum=8, maximum=64):
            raise Invalid("New PSK must be 8-64 printable ASCII characters; "
                          "no spaces, quotes, backslashes or control characters")
        if hmac.compare_digest(proposed, old):
            raise Invalid("New PSK is identical to previous global PSK")
        if len(proposed) < 16:
            print("WARNING: Short or guessable PSKs reduce IKEv1 protection; "
                  "a random 16-character PSK is recommended.")

        replacements = {PSK: ': PSK "' + proposed + '"\n'}
        for path in paths[1:]:
            replacements[path] = SWAN_SECRET.sub(
                lambda m: m.group(1) + proposed + m.group(3), original[path]
            )
        backup = Path(tempfile.mkdtemp(prefix="psk-rollback-", dir=str(PSK.parent)))
        os.chmod(backup, 0o700)
        for index, path in enumerate(paths):
            copy = backup / (str(index) + ".bak")
            with copy.open("x", encoding="ascii") as output:
                os.chmod(copy, 0o600)
                output.write(original[path])

        changed = []
        try:
            for path in paths:
                atomic_write(path, replacements[path])
                changed.append(path)
            r = subprocess.run(["swanctl", "--load-creds", "--clear", "--noprompt"],
                               capture_output=True, text=True, check=False, timeout=30)
            if r.returncode or not re.search(r"loaded\s+IKE\s+secret",
                                             r.stdout, re.IGNORECASE):
                raise Invalid("swanctl did not confirm that the new IKE secret was loaded")
        except (OSError, subprocess.TimeoutExpired, Invalid) as exc:
            for path in reversed(changed):
                atomic_write(path, original[path])
            try:
                restore = subprocess.run(
                    ["swanctl", "--load-creds", "--clear", "--noprompt"],
                    capture_output=True, text=True, check=False, timeout=30
                )
            except (OSError, subprocess.TimeoutExpired) as err:
                raise Invalid("ROLLBACK FAILED: restore the private backups in "
                              + str(backup)) from err
            if restore.returncode:
                raise Invalid("ROLLBACK INCOMPLETE: restore the private backups in "
                              + str(backup)) from exc
            raise Invalid("PSK update failed. Previous files restored; backup in "
                          + str(backup)) from exc

        print("SUCCESS: Global PSK and active/candidate snippets synchronized.")
        print("strongSwan IKE credentials reloaded; no daemon restart performed.")
        print("Private rollback backups:", backup)
        if not sys.stdout.isatty():
            print("New PSK not printed because output is not an interactive terminal.")
        else:
            print("NEW GLOBAL PSK (private terminal only):", proposed)
        print("All previously configured PSK clients must use the new shared key.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["list", "status", "set", "show", "global-status",
                                      "global-show", "global-rotate", "prune"])
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
    elif args.action == "prune":
        prune()


if __name__ == "__main__":
    try:
        main()
    except (Invalid, OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
        sys.exit("ERROR: " + str(exc))
