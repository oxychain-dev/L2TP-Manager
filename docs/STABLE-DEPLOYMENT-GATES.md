# Production safety gates — direct L2TP IPv6, GRE and optional IPsec PSK

**State:** reviewed source architecture, not verified live deployment.
**Current prerequisites:** live dual-stack pilot on one client, Warden
IPv4 NAT/return route installed but not reverified with client traffic,
and existing IPv6 GRE persistence timers.

## A. Stable direct dual-stack L2TP (ingress Polaris)

The new `tools/direct6-reconcile.py` accepts **one site-local root-owned
0600 JSON** config: `wan_interface`, `wan_ipv6`, `direct_prefix`,
`table`, `priority` and an array of client `peer_ipv4`/`client_ipv6`
mappings. It must never contain the selected GRE client's addresses.
See `examples/direct6-clients.json` (intentionally incomplete).

The reconciler discovers live PPP peers, repairs /128 return routes,
uses the current `networkd` WAN RA next-hop, manages ONLY its dedicated
`L2TP_DIRECT6` forwarding chain and per-client SNAT, and retains
a fail-closed unreachable fallback. Rules are keyed by peer, not by
a stale `ppp0`/`ppp1` interface name.

1. Audit WAN IPv6 and `ip -6 rule`. Choose a **free priority before
   the effective WARP source rule**, and a dedicated table already
   verified as belonging to the existing Pilot. Never use a guessed
   priority or overwrite another service's routes.
2. Write a root-owned JSON using only verified client assignments.
   Do not allocate GRE client or overlapping prefixes.
3. Audit and dry run without changing active networking:

~~~sh
sudo python3 tools/direct6-reconcile.py audit --config /etc/l2tp-manager/direct6.json
sudo python3 tools/direct6-reconcile.py apply --dry-run --config /etc/l2tp-manager/direct6.json
~~~

4. After review, install separately via
   `tools/install-direct6-persistence.sh`, which makes a root-only
   backup, installs one oneshot/timer and four PPP up/down hooks,
   and runs the bounded reconciliation. It does NOT restart
   xl2tpd, WARP, Docker, GRE, iptables-persistent or networkd.
5. Test actual IPv4/IPv6 traffic from the client and public IPv6
   source. Only after success, review removal of the **old pilot**
   using `tools/adopt-direct6-pilot.py` dry-run with the
   **observed original policy priority**, then execute `--apply`.
   This removes only tagged old pilot FORWARD/NAT entries and exact
   old source policy, never GRE or new owned entries.
6. Reconnect the test client, verify its new PPP number and the
   owned chain, NAT counters, HTTPS and public source. Reboot
   **only in a planned maintenance window with access recovery**.
7. Rollback: disable the new timer, remove ONLY the four
   `99-l2tp-direct6` hook symlinks after verifying their targets,
   run `direct6-reconcile.py remove` with the same root config,
   and verify policy and firewall. Do not restore full iptables
   snapshots; note this rollback intentionally leaves the client
   IPv6 path disabled, rather than reinstalling the fragile pilot.

## B. Persistent selected GRE client IPv4

Before installing `tools/install-ipv4-egress-persistence.sh` on Warden,
verify a **fresh real MikroTik IPv4 traffic test** through GRE and
the exact Warden public IPv4. Route/NAT installation or zero counters
alone is not sufficient proof. Use the checked client-scoped
`tools/ipv4-gre-egress.py` helper and documented dry-run first.
Existing Polaris GRE and Warden IPv6 timers must not be replaced.

## C. One Global PSK for selected L2TP/IPsec clients

Generate a **single strong PSK** in
`/etc/l2tp-manager/global-psk.secrets`, mode 0600 root-owned,
with `tools/global-psk.py init`, then `audit`. The key does not
appear in Git, command arguments, logs, CI output or these docs.

The file uses strongSwan legacy `ipsec.secrets` include syntax:
`: PSK "..."`. On an actual **isolated and IPsec-enforced L2TP
listener**, strongSwan's installed secrets configuration may
include the private file. Do NOT configure this include on an
uninspected production IKE daemon, and do not restart current
xl2tpd to attempt to enable IPsec for just a PPP username.

- A shared PSK authenticates the VPN endpoint/device, **not**
  an individual user. Each user needs separate PPP CHAP credentials,
  or a separate IKEv2 EAP/certificate identity.
- Requiring IPsec only for selected L2TP accounts cannot be
  enforced merely by changing PPP metadata when all users share
  the same unprotected UDP 1701 listener and credentials.
  Require separate L2TP/IPsec-only endpoint (or equivalent
  effective segmentation), protected credential visibility and
  negative plaintext-bypass tests before marking IPsec required.
- On iPhone, L2TP/IPsec supports shared machine PSK plus a
  separate user password. Native IKEv2 with a shared PSK
  **alone** does not give per-user revocation/authorization.
  Our preferred per-user iPhone flow is certificate-authenticated
  IKEv2 plus individual EAP password/certificate.
- If the PSK leaks, revoke and rotate it for every affected device.

Official references:
- https://support.apple.com/en-ca/guide/security/sec802e8ab55/web
- https://docs.strongswan.org/docs/latest/howtos/securityRecommendations.html

## D. iPhone IKEv2 direct dual-stack (NOT deployed)

`tools/ikev2-dualstack.py` validates distinct IPv4/IPv6 VIP pools,
exclusion CIDRs, WAN/public server identity, X.509 certificate SAN and
root-owned EAP registry. It supports `audit`, `init-users`,
`add-user`, `disable-user` and `render` of an **inactive candidate**
`swanctl` configuration. It does not install StrongSwan, alter
firewall/routing, open UDP 500/4500, terminate live SAs, or install
user credentials in a running daemon.

**Prerequisites not yet provided:** trusted RSA server X.509
certificate with exact SAN, real DNS server identity, selected VIP
pools without conflicts, installed service version, XFRM/NAT
policy and independent iOS test. For IPv6 full tunnel iPhone
`local_ts` must include `::/0`.

The generated config must be checked with the actual StrongSwan
version, then separately deployed with a rollback, audited firewall
and direct Polaris NAT44/NAT66. **Do not label the iPhone service
or a user active until real IPv4 and IPv6 HTTPS and user revocation
tests succeed.**

## Release and branch safety

Merging tested source into a `development` branch is not
deploying or releasing it to `main`. Keep `main` unchanged until
runtime reconciliation, reboot, rollback and selective IPsec
enforcement are verified. Never check out a different Git
branch inside an active service's script directory without first
checking that service's paths and restart dependencies.
