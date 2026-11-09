# Optional IPv6 egress via PPP / L2TP and GRE

This is an **opt-in** configuration. The L2TP server in this repository uses
L2TP without IPsec; GRE and NAT66 **do not encrypt** the connection.

Changing an internal L2TP IPv4 address is NOT required for IPv6. The PPP IPv4
address identifies the client, whereas IPv6CP only negotiates link-local IPv6
on that PPP interface. Usable IPv6 also needs addressing and routing.

## Generate an IPv6 router address

Run the following from the repository on a machine with Python 3:

~~~sh
python3 tools/ipv6-gre.py generate-ula
~~~

The output gives a random RFC4193 **ULA /48**, a stable **router /128**,
a separate **LAN /64**, and its gateway. Save these values and use the SAME
router /128 on MikroTik, the L2TP server and the remote GRE gateway.
Do not regenerate the addresses at every boot. ULA is private; the gateway
can translate it to the verified public IPv6 address using NAT66.
If you own a genuinely delegated public prefix, route that instead.

## Host-specific configuration stays OUTSIDE Git

Create separate root-owned JSON configuration files on each Linux host.
Permissions must not allow group or world writes (0600 recommended).

Server-role JSON keys:

| Key | Meaning |
|---|---|
| role | String value server |
| client_ipv4 | IPv4 assigned to ONE PPP client |
| client_ipv6 | Router ULA /128 |
| lan_prefix | Optional, independent LAN ULA /64 |
| gre_interface | Existing GRE interface name on the server |
| gre_peer_ipv6 | REMOTE GRE IPv6 address |
| routing_table | Chosen unused IPv6 policy table integer |
| rule_priority | Chosen unused IPv6 rule priority integer; +1 if LAN enabled |

Gateway-role JSON keys:

| Key | Meaning |
|---|---|
| role | String value gateway |
| client_ipv6 / lan_prefix | Same client IPv6 addresses |
| gre_interface | Existing GRE interface name on gateway |
| gre_peer_ipv6 | REMOTE (server-side) GRE IPv6 address |
| wan_interface | Verified public IPv6 egress device |
| wan_ipv6 | Verified public IPv6 assigned to that interface |

The application code contains **no Polaris, Warden, GRE, IPv6 provider or
user-specific addresses**. All actual values are supplied per host.
The helper requires root and validates the config file owner/mode, address
families, prefix lengths, interface names, and routing collisions.

## L2TP server: dynamic PPP interface

Never assume the PPP interface will always be named ppp1; identify the client
by its assigned IPv4 peer. IPv6 is enabled only when IPv6CP is up.
For an active matching PPP interface, after setting PPP_IFACE from read-only
host inspection:

~~~sh
sudo python3 tools/ipv6-gre.py apply --dry-run \
  --config /etc/l2tp-manager/ipv6-server.json --interface "$PPP_IFACE"
~~~

Review route selection, GRE interface and unused table/priority first.
Remove --dry-run to apply. This installs the client IPv6 return route and a
source-only IPv6 policy table with an unreachable fallback; it does NOT touch
the IPv4 default route or an unrelated PPP client.

For automatic handling on reconnect, install administrator-owned wrappers in
both /etc/ppp/ip-up.d/ and /etc/ppp/ipv6-up.d/ that invoke the helper
with --interface "$1". Either PPP protocol may finish first; the helper
checks that both protocols are up and is idempotent. An ip-down.d wrapper may
call the down action to remove matching client routes. Source policies and
the unreachable fallback stay in place on disconnect to prevent WAN fallback.

## GRE IPv6 gateway

Verify IPv6 forwarding, the WAN default route, the WAN global address,
GRE IPv6 reachability, and existing ip6tables rules before changing anything.
If the WAN gets its default route from Router Advertisements, forwarding
may require accept_ra=2 on that WAN interface. Do not change host-wide
sysctl or firewall policies without understanding existing dependencies.

~~~sh
sudo python3 tools/ipv6-gre.py apply --dry-run \
  --config /etc/l2tp-manager/ipv6-gateway.json
~~~

Review then run without --dry-run. The helper installs narrow IPv6 return
routes, FORWARD rules and SNAT to the explicitly specified public WAN IPv6.
It neither flushes firewall tables nor configures GRE.

To persist gateway state, install a systemd oneshot unit running the same
apply command after GRE becomes available, with a matching down command
for deliberate decommission. Do not blindly save the entire Docker-managed
firewall using ip6tables-save/netfilter-persistent.

## MikroTik RouterOS 7

Use the L2TP client with the matching IPv4 address. Keep its existing
IPv4 default-route configuration unchanged. In IPv6 > Addresses, assign the
generated router ULA **/128** to THAT L2TP interface, with Advertise=no.
Then route IPv6 through that L2TP tunnel. A dedicated IPv6 routing table is
preferable if the router has other IPv6 uplinks. A default IPv6 route in the
main table affects other interfaces and LAN users too.

If LAN IPv6 is needed, assign the generated DIFFERENT /64 to the real LAN
interface, enable Router Advertisements for it, and route that prefix across
PPP/GRE as well. IPv6CP link-local addresses are not public IPv6 allocations.

Test IPv6 ping, external IPv6 address visibility (e.g. HTTPS ip echo),
source-policy route lookup, GRE counters and NAT66 counters.
Preserve ICMPv6 Packet Too Big for PMTU; MTU 1280 alone cannot guarantee
zero fragmentation, low latency or zero packet loss.

## Rollback

- MikroTik: remove only the newly assigned ULA and intended IPv6 route.
- Gateway: down --config removes exact helper-managed NAT/forward/route entries.
- L2TP server: down --config --interface removes matching client routes; the
  source policy and unreachable fallback remain fail-closed by design and
  must be deprovisioned separately after confirming they are no longer used.
- Do not flush nftables/iptables or delete other VPN/PPP interfaces.

**Deployment is NOT automatic** when you update or merge this repository.
Existing server config, PPP credentials and active tunnels remain unchanged.
