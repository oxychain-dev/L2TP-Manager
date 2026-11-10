#!/usr/bin/env python3
"""Generate, never automatically deploy, iOS IKEv2 dual-stack swanctl config.

Separate IPv4/IPv6 pools, EAP users and certificate-based server identity.
Generated secret-containing config stays root-owned 0600. No daemon restart,
package installation, firewall or live IPsec configuration performed.
"""
import argparse
import base64
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

NAME = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
FQDN = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")


class Invalid(Exception):
    pass


def root_file(p):
    path = Path(p)
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or st.st_uid != 0 or st.st_mode & 0o077:
        raise Invalid("Must be a root-owned regular file mode 0600: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def check_config(cfg):
    fields = {"wan_interface", "wan_ipv4", "server_id", "certificate",
              "ipv4_pool", "ipv6_pool", "excluded_ipv4", "excluded_ipv6"}
    if not isinstance(cfg, dict) or set(cfg) != fields:
        raise Invalid("Unexpected IKEv2 host config fields")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", cfg["wan_interface"]):
        raise Invalid("Invalid WAN interface")
    if not FQDN.fullmatch(cfg["server_id"]):
        raise Invalid("Use actual DNS name with public trusted X.509 SAN")
    if Path(cfg["certificate"]).name != cfg["certificate"] or not cfg["certificate"].endswith(".pem"):
        raise Invalid("Certificate must be a PEM filename in /etc/swanctl/x509")
    wan = ipaddress.IPv4Address(cfg["wan_ipv4"])
    v4 = ipaddress.IPv4Network(cfg["ipv4_pool"], strict=True)
    v6 = ipaddress.IPv6Network(cfg["ipv6_pool"], strict=True)
    if not wan.is_global or not v4.is_private or v4.prefixlen > 28:
        raise Invalid("Invalid WAN address or usable private IPv4 client pool")
    if v6.prefixlen != 64 or not v6.subnet_of(ipaddress.IPv6Network("fd00::/8")):
        raise Invalid("IKEv2 IPv6 pool must be a distinct ULA /64")
    if not cfg["excluded_ipv4"] or not cfg["excluded_ipv6"]:
        raise Invalid("Provide all known GRE, PPP, Docker, WARP and direct-prefix exclusions")
    for other in cfg["excluded_ipv4"]:
        if v4.overlaps(ipaddress.IPv4Network(other, strict=True)):
            raise Invalid("IKEv2 IPv4 pool overlaps another subnet")
    for other in cfg["excluded_ipv6"]:
        if v6.overlaps(ipaddress.IPv6Network(other, strict=True)):
            raise Invalid("IKEv2 IPv6 pool overlaps another prefix")
    return cfg


def check_certificate(cfg):
    cert = Path("/etc/swanctl/x509") / cfg["certificate"]
    if not cert.is_file() or cert.is_symlink():
        raise Invalid("Expected certificate not found: " + str(cert))
    proc = subprocess.run(["openssl", "x509", "-in", str(cert),
                           "-noout", "-ext", "subjectAltName"],
                          capture_output=True, text=True)
    if proc.returncode:
        raise Invalid("Certificate cannot be parsed by openssl")
    san = "DNS:" + cfg["server_id"]
    if not re.search(r"(?<![A-Za-z0-9.-])" + re.escape(san) + r"(?![A-Za-z0-9.-])",
                     proc.stdout):
        raise Invalid("X.509 SAN does not exactly match IKE server identity")


def check_users(users):
    if not isinstance(users, dict):
        raise Invalid("Expected user map")
    for name, secret in users.items():
        if not NAME.fullmatch(name) or not isinstance(secret, str):
            raise Invalid("Invalid EAP user identity/secret")
        try:
            raw = base64.b64decode(secret, validate=True)
        except ValueError as e:
            raise Invalid("Invalid EAP secret encoding") from e
        if len(raw) < 16:
            raise Invalid("Too-short EAP secret")
    return users


def atomic_json(path, data):
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink() or parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
        raise Invalid("Target directory must exist and be root-owned non-writable by others")
    fd, tmp = tempfile.mkstemp(prefix=".ikev2-users-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def render(cfg, users):
    check_config(cfg)
    check_users(users)
    check_certificate(cfg)
    lines = [
        "connections {", "  ios-direct {", "    version = 2",
        "    local_addrs = " + cfg["wan_ipv4"],
        "    send_cert = always", "    pools = ios4, ios6",
        "    local {", "      auth = pubkey",
        "      id = @" + cfg["server_id"],
        "      certs = " + cfg["certificate"],
        "    }", "    remote {", "      auth = eap-mschapv2",
        "      eap_id = %any", "    }", "    children {",
        "      ios-net {", "        local_ts = 0.0.0.0/0, ::/0",
        "      }", "    }", "  }", "}",
        "pools {",
        "  ios4 {", "    addrs = " + cfg["ipv4_pool"], "  }",
        "  ios6 {", "    addrs = " + cfg["ipv6_pool"], "  }",
        "}", "secrets {"
    ]
    for username, value in sorted(users.items()):
        lines += ["  eap-" + username + " {",
                  "    id = " + username,
                  "    secret = 0s" + value,
                  "  }"]
    lines += ["}", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["audit", "init-users", "add-user", "disable-user", "render"])
    ap.add_argument("--config", default="/etc/l2tp-manager/ikev2.json")
    ap.add_argument("--users", default="/etc/l2tp-manager/ikev2-users.json")
    ap.add_argument("--output", help="New, root-only swanctl config output filename")
    ap.add_argument("--username")
    args = ap.parse_args()
    if os.geteuid() != 0:
        raise Invalid("Root required")
    cfg = check_config(root_file(args.config))
    path = Path(args.users)
    if args.action == "audit":
        if path.exists():
            print("Valid users:", len(check_users(root_file(path))))
        print("Valid host-local config. No daemon/certificate/client test performed.")
        return
    if args.action == "init-users":
        if path.exists() or path.is_symlink():
            raise Invalid("Users file already exists")
        atomic_json(path, {})
        print("Created private EAP credential registry, no active strongSwan changes")
        return
    users = check_users(root_file(path))
    if args.action in ("add-user", "disable-user"):
        name = args.username or ""
        if not NAME.fullmatch(name):
            raise Invalid("Valid --username required")
        if args.action == "add-user":
            if name in users:
                raise Invalid("User already exists; disable first and plan rotation")
            secret = getpass.getpass("New individual IKEv2 EAP password: ")
            if len(secret) < 16 or len(secret) > 256:
                raise Invalid("Password must be 16-256 characters")
            users[name] = base64.b64encode(secret.encode("utf-8")).decode("ascii")
        else:
            if name not in users:
                raise Invalid("User not found")
            del users[name]
        atomic_json(path, users)
        print("Local EAP registry updated. NOT loaded into strongSwan; existing SAs NOT terminated.")
        return
    if not args.output:
        raise Invalid("--output is required for render")
    output = Path(args.output)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise Invalid("Choose a NEW absolute output path; never overwrite live IPsec configuration")
    text = render(cfg, users)
    parent = output.parent
    if not parent.is_dir() or parent.is_symlink() or parent.stat().st_uid != 0 or parent.stat().st_mode & 0o022:
        raise Invalid("Output directory must be root-owned and not writable by others")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(output, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    print("Rendered root-only candidate; NOT DEPLOYED:", output)


if __name__ == "__main__":
    try:
        main()
    except (Invalid, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        sys.exit("ERROR: " + str(exc))
