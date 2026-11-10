# iPhone VPN clients — native IKEv2/IPsec without disturbing existing L2TP

## Scope and support

Apple iPhone natively supports IKEv2/IPsec (and also L2TP/IPsec for manual
configuration). For new iPhone users, **prefer IKEv2/IPsec** to L2TP/IPsec:
IKEv2 is a separate VPN protocol and does not need an xl2tpd/pppd tunnel.

Relevant upstream references:

- [Apple VPN security: supported protocols](https://support.apple.com/en-ca/guide/security-pdf/sec802e8ab55/web)
- [Apple VPN.IKEv2 configuration](https://developer.apple.com/documentation/devicemanagement/vpn/ikev2-data.dictionary)
- [strongSwan iOS/macOS interoperability](https://docs.strongswan.org/docs/latest/interop/ios.html)
- [strongSwan roadwarrior virtual IPs and EAP](https://docs.strongswan.org/docs/latest/config/quickstart.html)
- [strongSwan forwarding](https://docs.strongswan.org/docs/latest/howtos/forwarding.html)

The current repository's user IPsec metadata validator is **NOT an IKEv2
responder, certificate manager or strongSwan deployment mechanism**.
Nothing in this document silently installs or configures strongSwan.

## Intended isolation

~~~text
Existing MikroTik L2TP users --> existing xl2tpd/pppd UDP 1701 --> existing routes
iPhone selected users -------> IKEv2/IPsec UDP 500/4500 -> strongSwan -> separate virtual IP pool
                                                       -> explicitly chosen IPv4/IPv6 egress
~~~

Running both protocols on one Linux host may be possible because the IKEv2
listener is distinct from the L2TP listener. This **must be verified** for
the actual IPsec stack, existing XFRM policies, public interfaces, firewall
and service bindings. Do not enable L2TP/IPsec on the existing listener
just to support iPhone IKEv2 users.

User scope is enforced by *credentials/protocol endpoint*, not a PPP account's
description field. Only users provisioned with valid IKEv2 EAP credentials
or approved client certificates can authenticate to the IKEv2 service.
If the same identity also has plaintext L2TP credentials, that identity
is still allowed to use plaintext L2TP. A policy claiming "IPsec required"
must also **revoke/deny its plaintext L2TP authentication path**.

## Recommended mobile authentication

1. Server authenticates with an X.509 certificate whose SAN matches the
   configured server FQDN or IP identity exactly; use a certificate chain
   trusted by iPhone (or explicitly deploy the private CA correctly).
2. Client authenticates with individual EAP-MSCHAPv2 credentials, or
   EAP-TLS/client certificates when centralized certificate lifecycle
   management is available.
3. Prefer distinct user credentials from PPP CHAP until there is a secure,
   tested identity provider and explicit policy enforcement.
4. Do not commit any passwords, pre-shared keys, private keys, customer
   identifiers, certificate private material or host IP/FQDNs to Git.
5. Avoid weak/reused PSKs. A shared PSK does not reliably distinguish
   individual iPhone users.

iOS and strongSwan support EAP-MSCHAPv2 and EAP-TLS; not every EAP method
is supported. StrongSwan's iOS interoperability guidance requires the
server certificate's subjectAltName to match the IKE identity and advises
setting "send_cert = always" when applicable to manual iOS clients.

## Host-independent deployment design

The host-local IKEv2 configuration should require independently validated:

- IKEv2 server identity and certificate/key locations;
- public-facing interface and effective UDP 500/4500 exposure;
- IPsec backend and plugin versions; current XFRM policies and SAs;
- distinct, non-overlapping IPv4 virtual-IP pool, and optionally IPv6 pool;
- authenticated client identity store (individual EAP secrets or certificates);
- full-tunnel versus split-tunnel traffic selectors, DNS and lifecycle rules;
- whether selected iPhone users should exit the ingress host or the
  existing GRE egress gateway;
- per-pool forward/reply routing, NAT44 if necessary, IPv6 routing or NAT66,
  reverse-path filtering and PMTU/ICMPv6 policy;
- explicit no-plaintext-fallback assertion for any 'ipsec-required' user;
- firewall reconciliation/persistence without whole-table restore;
- safe rollback that does not stop xl2tpd, PPP, GRE, WARP or Docker.

Do not share an address pool between PPP and IKEv2, or route the entire
encrypted client pool through GRE before testing return routing.

For access to GRE/remote Internet egress, write source-specific policy
rules for the **actual assigned IKEv2 virtual-IP pool**; the PPP client
address rules from the L2TP implementation do not automatically apply.

### Staged server inspection (read-only)

Determine what is already installed and bound, using the actual host:

~~~bash
(
  echo '=== IKE / L2TP listeners ==='
  sudo ss -H -lunp | grep -E ':(500|4500|1701)[[:space:]]' || true
  echo '=== Installed IPsec clients and daemons ==='
  for cmd in swanctl ipsec charon-systemd; do
    command -v "$cmd" || true
  done
  echo '=== XFRM ==='
  sudo ip xfrm state count
  sudo ip xfrm policy list
  echo '=== Existing services ==='
  systemctl list-units --all --type=service |
    grep -Ei 'strongswan|charon|ipsec|xl2tpd' || true
  echo '=== Firewall backend ==='
  sudo iptables --version
  echo '=== IPv4 and IPv6 policy ==='
  ip -4 rule show
  ip -6 rule show
)
~~~

This command does not install or restart services and does not create
credentials. Share only sanitized outputs. **Do not paste raw
`ip xfrm state list` output**: it can expose IPsec key material.
`ip xfrm state count` avoids displaying Security Association keys.
XFRM policies may still expose peer IPs and internal selectors.

### iPhone manual VPN form (after server is deployed)

On iPhone: Settings > General > VPN & Device Management > VPN > Add VPN
Configuration > Type **IKEv2**. Enter:

| iPhone field | Source |
|---|---|
| Description | Local descriptive name chosen by operator |
| Server | Verified public server FQDN/IP of IKEv2 endpoint |
| Remote ID | Exact authenticated identity in server certificate SAN |
| Local ID | As specified by the chosen IKEv2 authentication profile |
| User Authentication | Username and password for EAP-MSCHAPv2, or certificate profile |
| Username | Individual IKEv2 user identity |
| Password | That user's independently managed IKEv2 secret |
| Proxy | Off unless the deployment explicitly needs one |

Do not copy another user's VPN profile or distribute EAP passwords inside
public configuration profiles. The final option labels vary with iOS release.
VPN access depends on reachable UDP 500/4500 and matching certificate trust;
a complete setup must be checked end to end.

## Acceptance and security gates

- [ ] Authorized iPhone can negotiate IKEv2 and an authenticated CHILD_SA.
- [ ] Another identity without IKEv2 credentials is rejected.
- [ ] An "IPsec required" identity is also **rejected on the old plaintext
      L2TP endpoint**, if that is a policy requirement.
- [ ] IPsec virtual IP is within the expected independent pool and does not
      collide with active L2TP/PPP addresses.
- [ ] IPv4 and (if enabled) IPv6 egress appear at the chosen public
      gateway with correct forward/reverse routes and NAT.
- [ ] No user leaks over a fallback ingress WAN/WARP path when GRE fails.
- [ ] Existing MikroTik L2TP/PPP, Docker, WARP and SSH remain healthy.
- [ ] Reconnect, mobile/Wi-Fi transition, credential revoke and reboot pass.
- [ ] Secrets/keys never appear in public repo or routine logs.

**State:** architectural guide only. Do not mark iPhone IKEv2 active, or
individual users "IPsec-enforced", until actual server configuration and
negative/plaintext-bypass tests are verified.


## Mandatory direct dual-stack iPhone profile

In this project's target design **all iPhone IKEv2 users require both
IPv4 and IPv6 Internet through the ingress/Polaris WAN**. They do not
exit through GRE/Warden. The IKEv2 service must provide separate,
non-overlapping IPv4 and IPv6 virtual-IP pools, and accept full-tunnel
traffic selectors for both IPv4 and IPv6:
`0.0.0.0/0` and `::/0`. A missing IPv6 VIP, selector, route, or verified
IPv6 HTTPS egress means dual-stack is NOT complete.

Use a genuinely routed public IPv6 client pool if provided by the ISP,
or per-deployment ULA + narrowly scoped NAT66 to the ingress host's
verified WAN IPv6. Do not assume the WAN on-link /64 is routed to clients.
IKEv2 IPsec XFRM/SAs own the return path; do not use PPP route hooks for
these accounts. Examine NAT exemption for return packets matching IPsec
policies, along with effective source policy versus WARP.

strongSwan documents that iOS with an IPv6 pool needs `::/0` included
in the server's `local_ts`; see
https://docs.strongswan.org/docs/latest/interop/ios.html.
Exact deployment requirements and read-only audit:
[Direct dual-stack egress](direct-dualstack.md).

**No iPhone account creation command is operational until a verified
IKEv2 service, trusted certificate identity, separate pools and
credential backend have actually been deployed.** Editing policy
metadata alone does not create or secure a live user.
