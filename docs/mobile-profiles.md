# Android and iPhone IKEv2 profiles — direct IPv4 + IPv6 through Polaris

**Implementation:** profile generator is in `tools/mobile-profiles.py`.
**Deployment:** source only; the supplied server audit did not establish a
running IKEv2 responder, trusted certificate, mobile address pools or
client Internet egress. An importable profile is not yet a working VPN.

## Separate these three components

1. Existing ordinary L2TP direct users and the selected GRE/Warden
   client continue unchanged.
2. iPhone and Android use independent IKEv2/IPsec, server authentication
   with an X.509 certificate, and **individual EAP-MSCHAPv2** identities.
   Their IPv4 and IPv6 virtual addresses must exit directly via Polaris.
3. The already generated root-only **global L2TP/IPsec PSK** is for a
   different, separately enforced L2TP/IPsec endpoint. It is NOT copied
   into IKEv2/EAP client profiles; a PSK alone cannot revoke individuals.

## Requirements before creating a functional user

- Verified, user-owned VPN DNS name and matching publicly trusted
  X.509 server certificate (DNS SAN, serverAuth and valid chain).
- Installed, audited strongSwan charon/swanctl with UDP 500/4500
  reachable, and no interference with current xl2tpd UDP 1701.
- Distinct, collision-checked virtual IPv4 and IPv6 client pools,
  traffic selectors `0.0.0.0/0` and `::/0`, valid mobile DNS.
- Source-aware public Polaris NAT44 and narrow ULA NAT66, XFRM-aware
  return path, ICMPv6 PMTU, forwarding and firewall validation.
- The host JSON for `tools/ikev2-dualstack.py` must contain actual
  verified `wan_interface`, `wan_ipv4`, `server_id`,
  `certificate`, `ipv4_pool`, `ipv6_pool`, and complete
  `excluded_ipv4` / `excluded_ipv6` arrays. Sample:
  `examples/ikev2-dualstack.json` (intentionally incomplete).
- None of the above are implied by a successfully created PSK file.

## Host audit — read-only

~~~bash
(
  echo '=== IKEv2 and L2TP sockets ==='
  sudo ss -H -lunp | grep -E ':(500|4500|1701)[[:space:]]' || true
  echo '=== IKEv2 packages ==='
  dpkg-query -W 'strongswan*' 'charon*' 2>/dev/null || true
  echo '=== VPN services ==='
  systemctl list-units --all --type=service --no-pager |
    grep -Ei 'strongswan|charon|ipsec|xl2tpd' || true
  echo '=== IPsec SA count (never dump keys) ==='
  sudo ip xfrm state count
  echo '=== Routing policies ==='
  ip -4 rule show
  ip -6 rule show
  echo '=== WAN default routes ==='
  ip -4 route show default
  ip -6 route show default
  echo '=== NAT scopes ==='
  sudo iptables -w 5 -t nat -S POSTROUTING
  sudo ip6tables -w 5 -t nat -S POSTROUTING
)
~~~

## Creating accounts and portable profiles

Use a checked-out, approved source version in a separate worktree
and verified secret-safe host config. `ikev2-dualstack.py` is a
**candidate renderer**, not an IPsec daemon installer.

1. Create the local root-owned EAP registry once using
   `sudo python3 tools/ikev2-dualstack.py init-users`.
   If it already exists, do not rerun. Audit instead.
2. Add an individual account interactively using
   `sudo python3 tools/ikev2-dualstack.py add-user --username "$VPN_USERNAME"`.
   The EAP password is read without shell echo and stays in the private
   server registry. Do not reuse plaintext L2TP credentials.
3. Generate a non-overwriting candidate server configuration using
   `tools/ikev2-dualstack.py render --output`, validate it with the
   installed strongSwan version, deploy it in a separately reviewed
   change and validate CHILD_SAs and NAT44/NAT66 **before users connect**.
4. After a trusted server certificate has been deployed, create a
   root-owned directory for client profiles:

~~~bash
(
  read -r -p 'Absolute path to approved L2TP-Manager checkout: ' source
  read -r -p 'Existing IKEv2 EAP username: ' vpn_user
  [ -f "$source/tools/mobile-profiles.py" ] || exit 1
  sudo install -d -o root -g root -m 0700 /etc/l2tp-manager/mobile-profiles
  sudo python3 "$source/tools/mobile-profiles.py" \
    --username "$vpn_user" \
    --output-dir /etc/l2tp-manager/mobile-profiles \
    --platform both --dry-run
)
~~~

Check the proposed file paths. Then run that exact `mobile-profiles.py`
command without `--dry-run` to create both files. It validates
that username exists in the EAP registry and that the server
certificate SAN matches the trusted IKE identity.

The files are root-only 0600 and contain **NO password, PSK or private
key**. Transfer them only to an authorized device and protect the copy.
The generator never overwrites an existing profile.

## iPhone — Apple configuration profile

- Output: `username.mobileconfig`, XML property list.
- VPN payload type: `com.apple.vpn.managed`; `VPNType=IKEv2`.
- Required identity fields: `RemoteAddress` and
  `RemoteIdentifier` are the verified VPN hostname;
  `LocalIdentifier` and `AuthName` identify the EAP account.
- Apple EAP fields: `AuthenticationMethod=None`,
  `ExtendedAuthEnabled=1`. `IncludeAllNetworks=1` requests
  full-tunnel routing, subject to Apple system exclusions.
- Install with Files/Safari, review the issuer/profile, then
  Settings > General > VPN & Device Management.
- Enter password on iPhone; do not put it into the profile.
  A generated unsigned profile may warn about an unknown signature:
  use trusted MDM or signed distribution for scale. Do not install
  unknown or untrusted VPN profiles.

## Android — strongSwan VPN Client

- Output: `username.sswan`, JSON profile for **strongSwan VPN
  Client**, not a stock Android VPN export.
- Type `ikev2-eap`, server address/identity and EAP identity.
- `split-tunneling.block-ipv4=true` and
  `split-tunneling.block-ipv6=true` avoid intentional bypass
  of unnegotiated routes; they do not replace assigned dual IPs.
- In strongSwan app select Import, review server identity and EAP
  account, then enter password privately. App import supports
  `.sswan` files via SAF/file picker.
- Trust the validated public CA, or provision a private CA correctly.
  Never disable server certificate validation.

## Acceptance — required on each real device

- Real IKE_SA and CHILD_SA for an authenticated user.
- Both virtual IP families assigned and full-tunnel routes installed.
- HTTPS IPv4 public echo and HTTPS IPv6 public echo show **Polaris**,
  NOT Warden. Check DNS A/AAAA and actual web traffic.
- Check reconnection between mobile data and Wi-Fi, IPv6 fail-closed,
  invalid account rejection and revocation of an existing account.
- Re-test current L2TP .10 and .11 for regressions; perform controlled
  reboot/rollback before declaring production readiness.

Official format and compatibility docs:
- https://developer.apple.com/documentation/devicemanagement/vpn
- https://developer.apple.com/documentation/devicemanagement/vpn/ikev2-data.dictionary
- https://docs.strongswan.org/docs/latest/os/androidVpnClientProfiles.html
- https://docs.strongswan.org/docs/latest/interop/ios.html


## Current operational correction — 2026-11-13

The operator verified on Polaris that `xl2tpd` owns UDP 1701,
`swanctl`/strongSwan are not installed, there is no IPsec SA
and `/etc/l2tp-manager/ikev2.json` is absent. Trying `init-users`
and `add-user` with the earlier backend failed because it incorrectly
read the absent server JSON before dispatching subcommands.

**Fixed in development:** `init-users`, `add-user` and `disable-user`
can operate on the root-only EAP credential registry *without*
the IKEv2 server host JSON. `audit` reports missing config without
failing. `render` still *requires* audited host JSON and server
certificate, as intended. This is source/CI-verified only; the
updated code needs to be fetched into Polaris's separate worktree.

For the first EAP credential registry on Polaris (do not rerun
`init-users` once the file exists):

~~~bash
(
  source="$HOME/L2TP-Manager-development"
  sudo python3 "$source/tools/ikev2-dualstack.py" audit
  sudo python3 "$source/tools/ikev2-dualstack.py" init-users
  sudo python3 "$source/tools/ikev2-dualstack.py" audit
)
~~~

To prepare an individually authenticated mobile account before
installing strongSwan, `add-user --username` prompts for a secret
interactively and records it in the root-only registry. This is a
**staged offline account**; no active IKE_SA, CHILD_SA or real VPN
access is created. Generate import files only after the real
server DNS name, X.509 certificate and two IP pools are configured.

Never insert a dummy DNS hostname, empty certificate, guessed VPN
address pool or a secret into tracked Git source just to silence
a missing config error. The existing global PSK file is unrelated
to iPhone/Android IKEv2 EAP authentication.
