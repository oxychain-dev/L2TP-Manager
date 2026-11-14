#!/usr/bin/env python3
"""Create/audit one global on-host IKE/L2TP pre-shared key.

The output is a root-only strongSwan legacy secrets include, not a
deployed IPsec endpoint. No PSK value is printed, logged or committed.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import secrets
import sys

DEFAULT = Path("/etc/l2tp-manager/global-psk.secrets")
FORMAT = re.compile(r'^: PSK "([^"\r\n]+)"\n$')


class Invalid(Exception):
    pass


def verify_parent(path):
    if not path.is_absolute():
        raise Invalid("Key path must be absolute")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise Invalid("Parent directory must already exist and not be symlink")
    st = parent.stat()
    if st.st_uid != 0 or st.st_mode & 0o022:
        raise Invalid("Parent directory must be root-owned and not writable by group/others")


def audit(path):
    verify_parent(path)
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o077:
        raise Invalid("Key file must be root-owned regular mode 0600")
    data = path.read_text(encoding="ascii")
    match = FORMAT.fullmatch(data)
    if not match or not all(32 <= ord(x) <= 126 for x in match.group(1)):
        raise Invalid("Unexpected global key file format")
    print("Global PSK file valid:", path, "(length:", len(match.group(1)), ")")
    print("Fingerprint (not key):", hashlib.sha256(match.group(1).encode()).hexdigest()[:16])
    print("Not evidence of an active IPsec listener or secure user selection")


def init(path, length=16):
    verify_parent(path)
    if not 8 <= length <= 64:
        raise Invalid("New PSK length must be 8-64 (16 recommended)")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    key = "".join(secrets.choice(alphabet) for _ in range(length))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(': PSK "' + key + '"\n')
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    print("New global PSK generated in root-only file:", path)
    print("Never commit this file or paste the key in chat/logs")
    print("This does NOT configure strongSwan, UDP 500/4500, users or IPsec enforcement")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "audit"])
    parser.add_argument("--path", type=Path, default=DEFAULT)
    parser.add_argument("--length", type=int, default=16, help="New PSK length for init (8-64; default 16)")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise Invalid("Root required")
    if args.action == "init":
        init(args.path, args.length)
    else:
        audit(args.path)


if __name__ == "__main__":
    try:
        main()
    except (Invalid, FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
        sys.exit("ERROR: " + str(exc))
)


class Invalid(Exception):
    pass


def verify_parent(path):
    if not path.is_absolute():
        raise Invalid("Key path must be absolute")
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise Invalid("Parent directory must already exist and not be symlink")
    st = parent.stat()
    if st.st_uid != 0 or st.st_mode & 0o022:
        raise Invalid("Parent directory must be root-owned and not writable by group/others")


def audit(path):
    verify_parent(path)
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o077:
        raise Invalid("Key file must be root-owned regular mode 0600")
    data = path.read_text(encoding="ascii")
    match = FORMAT.fullmatch(data)
    if not match:
        raise Invalid("Unexpected global key file format")
    print("Global PSK file valid:", path)
    print("Fingerprint (not key):", hashlib.sha256(match.group(1).encode()).hexdigest()[:16])
    print("Not evidence of an active IPsec listener or secure user selection")


def init(path):
    verify_parent(path)
    # 48 cryptographically random bytes = 384 bits, URL-safe 64-character secret.
    key = secrets.token_urlsafe(48)
    if len(key) != 64 or not re.fullmatch(r"[A-Za-z0-9_-]{64}", key):
        raise Invalid("Unable to create required high-entropy key")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(': PSK "' + key + '"\n')
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    print("New global PSK generated in root-only file:", path)
    print("Never commit this file or paste the key in chat/logs")
    print("This does NOT configure strongSwan, UDP 500/4500, users or IPsec enforcement")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "audit"])
    parser.add_argument("--path", type=Path, default=DEFAULT)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise Invalid("Root required")
    if args.action == "init":
        init(args.path)
    else:
        audit(args.path)


if __name__ == "__main__":
    try:
        main()
    except (Invalid, FileExistsError, FileNotFoundError, OSError, ValueError) as exc:
        sys.exit("ERROR: " + str(exc))
