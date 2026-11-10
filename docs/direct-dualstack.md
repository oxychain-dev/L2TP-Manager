# Direct dual-stack egress: ordinary L2TP and iPhone IKEv2

**Status:** approved architecture requirement, NOT a deployed feature.
The selected GRE client must retain its separate source-policy and remote
egress configuration.

## User classes

| Class | Protocol | IPv4 source | IPv6 source | Internet egress |
|---|---|---|---|---|
| l2tp-direct | xl2tpd/PPP | Existing client peer | Stable per-client IPv6 /128 (optional routed LAN /64) | Ingress server WAN, both families |
| ikev2-direct | strongSwan IKEv2/IPsec | Separate IKEv2 virtual IP pool | Separate IKEv2 IPv6 virtual IP pool | Ingress server WAN, both families |
| l2tp-gre | Selected existing PPP client | Assigned IPv4 peer | Assigned ULA /128 (optional LAN /64) | Existing GRE egress gateway, both families |

Client authentication, traffic classification and source routing must be
explicit. Never infer protocol or egress from a username suffix. Existing
GRE IPv4/IPv6 source policies are **not** a direct-user default.

## Addressing and egress isolation

1. Prefer a genuinely **routed/delegated public IPv6 prefix** when the
   upstream provider confirms it. The public IPv6 /64 on the host WAN is
   an *on-link* subnet, not proof it may be delegated to VPN clients.
   Do not distribute it without upstream routes or a reviewed proxy-NDP
   mechanism that provider policy permits.
2. If no public routed prefix exists, use RFC4193 ULA assignments and
   scoped IPv6 SNAT (NAT66) to the ingress host's verified public IPv6.
   Use separate, non-overlapping address space for direct L2TP clients,
   IKEv2 clients, selected GRE clients, and GRE tunnel transit.
3. Keep a durable per-client mapping of IPv6 /128 and optional LAN /64.
   Never regenerate a user's IPv6 address on reconnect or reboot.
4. Allocate a **distinct non-overlapping IPv4 pool for IKEv2**, separate
   from PPP, Docker, GRE inner IPv4, WARP, LAN and other pools.
5. Direct users must use the ingress WAN for *both* IPv4 and IPv6.
   Inspect the effective IPv4/IPv6 rules and WARP tables before adding
   source policies. Use narrow, collision-checked policies only when
   required; never change host default routes globally.
6. Preserve existing GRE-client PBR priority and fail-closed protection;
   direct NAT must not match and translate the GRE client prefix.

## Ordinary L2TP users

- PPP IPv6CP only negotiates link-local IPv6. It does **not** assign a
  routable public IPv6 address or a LAN prefix.
- Dynamically associate the active PPP peer with the authenticated account
  and its stable assigned IPv6 /128; install the corresponding return route
  on the actual PPP device. Do not assume ppp0/ppp1 interface numbers.
- For a LAN behind the router, separately route a distinct /64 and configure
  Router Advertisement only on that router's real LAN interface.
- Apply scoped IPv6 FORWARD and optional NAT66 on the ingress WAN if using
  ULA. Existing IPv4 NAT44 may already work: inspect before duplicating it.
- Use PPP ip-up/ip-down/ipv6-up/ipv6-down events with robust concurrency,
  reconciler, session changes and exact rule ownership.
- Existing L2TP without IPsec remains unencrypted and must not be described
  as an IPsec-secured service.

## iPhone IKEv2 users

- IKEv2/IPsec is a distinct service and **does not use PPP hooks**.
- strongSwan's swanctl supports assigning an IPv4 VIP and an IPv6 VIP
  from separate pools: connections.<profile>.pools refers to both pool
  names. Both user address families must be verified on the phone.
- Configure children.local_ts to include BOTH 0.0.0.0/0 and ::/0 for
  a full tunnel; strongSwan's iOS documentation specifically states
  that ::/0 is necessary when an IPv6 pool is used.
- Authenticate the server with a trusted X.509 certificate; its SAN
  must match the IKE identity entered as Remote ID. For manually
  configured iOS clients, strongSwan recommends RSA certificates and
  send_cert=always.
- Prefer individual EAP-MSCHAPv2 or EAP-TLS credentials and separate
  account provisioning. A user who must use IPsec must NOT also retain
  a working plaintext L2TP authentication path.
- Verify routing and NAT44 for the IPv4 VIP pool and routed IPv6 or
  scoped NAT66 for ULA IPv6 VIPs on the ingress WAN. Examine XFRM/
  Netfilter policy exemptions so NAT does not corrupt outbound IPsec
  return packets. Preserve ICMPv6 Packet Too Big.
- IKEv2 virtual IP return paths are controlled by IKEv2/XFRM; do not
  add a PPP-route for an IKEv2 user.
- No iPhone packets should be routed over the GRE egress gateway in
  this design. Do not assume IPsec is installed until daemons, UDP
  500/4500 listeners, authenticated CHILD_SA and client tests prove it.

## Mandatory read-only ingress-host audit

Run on the ingress host before any new direct IPv6 route or IPsec setup.

~~~bash
(
  echo "=== Current IPv4 and IPv6 defaults ==="
  ip -4 route show default
  ip -6 route show default
  echo "=== Host public IPv6 addresses ==="
  ip -6 addr show scope global
  echo "=== Policy routing ==="
  ip -4 rule show
  ip -6 rule show
  echo "=== PPP peers ==="
  for path in /sys/class/net/ppp*; do
    [ -e "$path" ] || continue
    iface=$(basename "$path")
    ip -o -4 addr show dev "$iface"
    ip -o -6 addr show dev "$iface"
  done
  echo "=== Forwarding sysctls ==="
  sysctl net.ipv4.ip_forward
  sysctl net.ipv6.conf.all.forwarding
  echo "=== NAT scopes ==="
  sudo iptables -w 5 -t nat -S POSTROUTING
  sudo ip6tables -w 5 -t nat -S POSTROUTING
  echo "=== IKE/L2TP sockets ==="
  sudo ss -H -lunp | grep -E ':(500|4500|1701)[[:space:]]' || true
  echo "=== StrongSwan installation ==="
  dpkg-query -W 'strongswan*' 'charon*' 2>/dev/null || true
  echo "=== XFRM SA count (not secrets) ==="
  sudo ip xfrm state count
)
~~~

Never publish raw ip xfrm state list: kernel SA output may expose secret
key material. Do not run installation scripts or restart services while
another VPN and host SSH access rely on the same network.

## Acceptance criteria

- Standard L2TP client: real IPv4 AND IPv6 Internet reachability and
  public exit addresses belonging to the ingress host.
- iPhone: established authenticated IKEv2 SA plus IPv4 and IPv6 VIPs,
  separate EAP credentials, IPv4 and IPv6 HTTPS showing ingress egress,
  and successful Wi-Fi/mobile reconnect.
- Selected GRE client: its IPv4 AND IPv6 public egress remain the GRE
  gateway's; other users do not inherit this route.
- No address overlap, plaintext downgrade, firewall/WARP route leakage,
  lost SSH/Docker/GRE/PPP services, or unwanted default-route changes.
- Controlled reconnect, restart, persistence and exact rollback tests
  pass before enabling additional users.

**Deployment status:** source documentation only. No IKEv2 service, user
accounts, direct PPP IPv6 routing or IPv6 NAT66 was changed on a live host.

Primary references:
- https://docs.strongswan.org/docs/latest/features/vip.html
- https://docs.strongswan.org/docs/latest/interop/ios.html
- https://docs.strongswan.org/docs/latest/howtos/forwarding.html
