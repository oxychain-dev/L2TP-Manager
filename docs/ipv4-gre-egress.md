# Selected-client IPv4 Internet over GRE: audit and safe reconciliation

This addresses a DIFFERENT path from the opt-in IPv6 NAT66 feature. A PPP
client can reach its Linux L2TP server, and IPv6 can successfully exit from
the remote gateway, while IPv4 Internet traffic still fails because GRE egress
lacks an IPv4 return route, IPv4 SNAT or correct source-policy route.

## Read-only evidence before doing anything

On the L2TP ingress host:
- Verify PPP IPv4 peer identity dynamically, and the currently active PPP
  interface; do not assume ppp1 will persist.
- Check forwarded IPv4 route lookup with the actual PPP interface as iif.
- Compare IPv4 rules and the dedicated table; inspect FORWARD, mangle and
  persistent rules without flushing tables.
- Audit l2tp6-polaris.service/.timer and PPP hooks, which are IPv6-specific.
  They are not the remedy for failed GRE IPv4 egress.

On the GRE gateway:
- Verify IPv4 forwarding is enabled, the GRE peer IPv4 is reachable and
  GRE client-source traffic actually chooses the intended public IPv4 WAN.
- Check selected client /32 return route through GRE.
- Check source-specific IPv4 NAT and both directions of FORWARD.
- Check reverse-path filtering (§net.ipv4.conf.*.rp_filter§), upstream gateway,
  WARP policy rules, and conflicts with Docker/nftables chains.
- If possible, observe packet/conntrack counters while a real selected client
  sends IPv4 traffic. No change to other client address ranges is needed.

## Opt-in helper

The per-host JSON file is external to Git and root-owned mode 0600.
Start from examples/ipv4-gre-egress.json, providing the values discovered
on the **egress** host:
- client_ipv4: only one L2TP peer's private IPv4 address
- gre_interface: verified GRE interface name
- gre_peer_ipv4: **remote ingress-side** GRE IPv4 next hop
- wan_interface: verified public IPv4 outbound interface

The helper tools/ipv4-gre-egress.py has no hard-coded servers, peers or
interfaces. On the gateway only, use:

~~~sh
sudo python3 tools/ipv4-gre-egress.py audit --config /etc/l2tp-manager/ipv4-egress.json
sudo python3 tools/ipv4-gre-egress.py apply --dry-run --config /etc/l2tp-manager/ipv4-egress.json
~~~

Inspect the proposed route/rules. If the forwarded route lookup does not
choose the configured WAN, stop and inspect WARP/policy routing before
applying. Once validated, the apply operation adds, only if missing:
1. One client /32 route via the remote GRE IPv4 next-hop;
2. Forwarding for that source from GRE to WAN;
3. Established/related return forwarding from WAN to GRE;
4. A client-and-egress-scoped IPv4 MASQUERADE rule.

Apply on the gateway only after reviewing the full host audit:

~~~sh
sudo python3 tools/ipv4-gre-egress.py apply --config /etc/l2tp-manager/ipv4-egress.json
~~~

Re-test real IPv4 traffic and verify the observed public IPv4 exit. If
needed, remove exact helper targets:

~~~sh
sudo python3 tools/ipv4-gre-egress.py remove --dry-run --config /etc/l2tp-manager/ipv4-egress.json
sudo python3 tools/ipv4-gre-egress.py remove --config /etc/l2tp-manager/ipv4-egress.json
~~~

Caution: if an exact matching rule existed before this helper was used,
the helper cannot prove ownership of that old rule. Record before-state and
review rollback first. No global flush, service restart or iptables-save.

### Persistence

Do not add a systemd startup unit until actual IPv4 egress works and
the running-state conflicts are understood. Use a dedicated oneshot
service, after the GRE and WAN interfaces are available, with a bounded
periodic timer for reconciliation if required by local network lifecycle.
Never install this helper through the L2TP ingress service or the IPv6
timer. Persistence is a separate, deliberately operator-reviewed step.

These scripts and docs **do not change any live host automatically**.
