#!/usr/bin/env python3
"""Generate portable iPhone and Android IKEv2/EAP profiles with NO secrets.

Apple: .mobileconfig XML property list, certificate-authenticated IKEv2 server
with individual EAP-MSCHAPv2 username. Android: strongSwan Client .sswan JSON.
Profiles do not configure or verify a running VPN/IPsec service and never
embed the global L2TP/IPsec PSK, EAP password, or private keys.

Host config and user registry are the same root-owned files as
tools/ikev2-dualstack.py. Refuses to export usernames not in that registry.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import sys
import uuid


class ProfileError(Exception):
    pass


def backend_module():
    source = Path(__file__).resolve().with_name("ikev2-dualstack.py")
    spec = importlib.util.spec_from_file_location("l2tp_ikev2_backend", source)
    if spec is None or spec.loader is None:
        raise ProfileError("IKEv2 backend could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iphone_payload(server_id, username, display_name, uid=None):
    """Only Apple-documented VPN payload attributes; no account password."""
    uid = uid or str(uuid.uuid4()).upper()
    vpn_id = str(uuid.uuid4()).upper()
    return {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": "net.l2tpmanager.mobile." + uid.lower(),
        "PayloadUUID": uid,
        "PayloadDisplayName": display_name,
        "PayloadDescription": "IKEv2 VPN (server certificate + individual EAP account)",
        "PayloadOrganization": "L2TP-Manager",
        "PayloadContent": [{
            "PayloadType": "com.apple.vpn.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": "net.l2tpmanager.mobile." + vpn_id.lower(),
            "PayloadUUID": vpn_id,
            "PayloadDisplayName": display_name,
            "UserDefinedName": display_name,
            "VPNType": "IKEv2",
            "IKEv2": {
                "RemoteAddress": server_id,
                "RemoteIdentifier": server_id,
                "LocalIdentifier": username,
                "AuthenticationMethod": "None",
                "ExtendedAuthEnabled": 1,
                "AuthName": username,
                "IncludeAllNetworks": 1,
                "OnDemandEnabled": 0,
                "DeadPeerDetectionRate": "Medium",
            },
        }],
    }


def android_payload(server_id, username, display_name, uid=None):
    """strongSwan .sswan documented profile: EAP, both-IP-family block-leaks."""
    uid = uid or str(uuid.uuid4())
    return {
        "uuid": uid,
        "name": display_name,
        "type": "ikev2-eap",
        "remote": {"addr": server_id, "id": server_id},
        "local": {"eap_id": username},
        "split-tunneling": {"block-ipv4": True, "block-ipv6": True},
    }


def create_private(path, contents):
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def private_dir(path):
    if not path.is_absolute():
        raise ProfileError("Output directory must be an absolute path")
    if not path.is_dir() or path.is_symlink():
        raise ProfileError("Output directory must already exist and not be a symlink")
    st = path.stat()
    if st.st_uid != 0 or st.st_mode & 0o077:
        raise ProfileError("Output directory must be root-owned and mode 0700")


def build(cfg, username, platform, name):
    server_id = cfg["server_id"]
    payloads = {}
    if platform in ("both", "ios"):
        payloads[username + ".mobileconfig"] = plistlib.dumps(
            iphone_payload(server_id, username, name), fmt=plistlib.FMT_XML)
    if platform in ("both", "android"):
        payloads[username + ".sswan"] = (
            json.dumps(android_payload(server_id, username, name),
                       indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    return payloads


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default="/etc/l2tp-manager/ikev2.json")
    p.add_argument("--users", default="/etc/l2tp-manager/ikev2-users.json")
    p.add_argument("--username", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--platform", choices=("ios", "android", "both"), default="both")
    p.add_argument("--display-name")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if os.geteuid() != 0:
        raise ProfileError("Root required")
    backend = backend_module()
    cfg = backend.check_config(backend.root_file(args.config))
    users = backend.check_users(backend.root_file(args.users))
    name = args.username
    if not backend.NAME.fullmatch(name):
        raise ProfileError("Invalid username")
    if name not in users:
        raise ProfileError("No matching IKEv2 EAP identity exists in the local registry")
    backend.check_certificate(cfg)
    private_dir(args.output_dir)
    display = args.display_name or ("Polaris IKEv2 - " + name)
    if not isinstance(display, str) or not (1 <= len(display) <= 80):
        raise ProfileError("Display name length must be 1-80 characters")
    outputs = build(cfg, name, args.platform, display)
    for filename in outputs:
        target = args.output_dir / filename
        if target.exists() or target.is_symlink():
            raise ProfileError("Refusing to overwrite existing profile: " + str(target))
    if args.dry_run:
        for filename in outputs:
            print("PROPOSED:", args.output_dir / filename)
        print("No profile exported or credentials disclosed")
        return
    created = []
    try:
        for filename, data in outputs.items():
            destination = args.output_dir / filename
            create_private(destination, data)
            created.append(destination)
    except BaseException:
        for destination in created:
            destination.unlink(missing_ok=True)
        raise
    for path in created:
        print("Created:", path)
    print("Profiles have no passwords, PSK or private keys.")
    print("NOT CONNECTABLE until server IKEv2, certificate trust, user credentials,")
    print("dual-stack pools, NAT/routing, firewall and real mobile tests pass.")


if __name__ == "__main__":
    try:
        main()
    except (ProfileError, FileNotFoundError, OSError, ValueError, KeyError,
            json.JSONDecodeError) as exc:
        sys.exit("ERROR: " + str(exc))
