# Phase 1 — Plain L2TPv2 multi-WAN MikroTik / Polaris

**Scope:** independent concurrent unencrypted L2TPv2/PPP clients to the *same*
Ubuntu VPS, with per-tunnel CHAP identities and different PPP peer addresses.
**Status:** source implementation + simulated tests, **NOT TESTED on live CA1+CA2**.
**Explicitly forbidden in this workflow:** enabling IPsec, PSK, WireGuard,
OpenVPN, MPPE, or changing the selected VPN country. No MikroTik mutations are
performed by the repository. The optional iPhone PSK feature remains separate.

**Security:** L2TP without IPsec or MPPE offers **no traffic confidentiality**.
CHAP only authenticates the PPP peer. Anyone on the path with suitable network
visibility may inspect L2TP payload data. Do not confuse authentication with
encryption. Do not expose MikroTik management services through public port forwards.

## Verified code baseline and reasons for change

- Source `lib/install.sh` configures `xl2tpd` LNS on UDP 1701, with
  `require chap = yes`, `refuse pap = yes`, `require-chap`, `refuse-pap`
  and `noccp` in the PPP options. These settings are **not changed**.
- `config/defaults.conf` defines the configured subnet, start/end of
  assignment pool and server PPP address; the pool is validated before use.
- Existing `lib/users.sh` account creation previously selected an address
  before a CHAP write with no shared lock; concurrent writers could reuse an IP.
- Legacy user deletion can restart `xl2tpd` and port-forwards, so the new
  independent multi-WAN path deliberately does **not** invoke it.
- `lib/services.sh` `start_forwards` uses broad `pkill -f socat` and restores
  saved iptables rules. Do not restart forwarding as an account-creation
  side effect; existing forward management needs separate review.
- Other routes on Polaris select certain existing PPP accounts for
  direct6/GRE; the new allocator preserves addresses already claimed in
  CHAP, active PPP interfaces, port-forward references, static route
  gateways, `direct6.json` and `ipv4-egress.json`.
- The observed system had `strongswan` active for an *optional* iPhone
  pilot, but `IKE_SAs: 0`. The presence of that service alone does not
  encrypt clients configured with `use-ipsec=no`; do not disable
  strongSwan globally to implement this feature.

## Independent session model

| Tunnel | RouterOS underlay | Linux VPN identity | Linux peer address | Encryption |
|---|---|---|---|---|
| CA1 | WAN1 FDD-PISHGAMAN | Existing CA1 account, preserve | Existing assigned address, preserve | None |
| CA2 | WAN2 LTE-IRANCELL | **New unique CHAP account** | **New free static IP under allocator lock** | None |
| CA3 (future) | WAN3 SHATELMOBILE | Another unique CHAP account | Another independently allocated IP | None |

The server must identify the PPP peer through the authenticated
**username + PPP session**, never by the WAN source IP. A single
public VPS IP and UDP 1701 port serve all connections. Distinct
RouterOS L2TP objects require underlay policy routing to ensure that
CA2 actually uses WAN2; do not rely on two `connect-to` values alone.

## VPS commands — isolated source checkout only

Preflight must inspect the actual `/etc/ppp/chap-secrets` and source
project network config, installed `xl2tpd`, route and NAT state. The
new CLI defaults to **read-only**. Do not change the live worktree
because `l2tp-forwards.service` launches the script from it.

CLI:
- `python3 tools/plain-l2tp-multiwan.py list` — configured accounts
  and assigned IPv4 (no passwords or keys)
- `python3 tools/plain-l2tp-multiwan.py sessions` — `pppN`, peer IPv4,
  username or clearly marked inference, byte counters and hook-based
  uptime when known
- `python3 tools/plain-l2tp-multiwan.py check` — duplicates and
  unknown PPP peers, warning for legacy wildcard address entries
- `python3 tools/plain-l2tp-multiwan.py health` — service status and
  forwarding flag; warns NAT/egress remain to be proved
- `sudo bash tools/install-ppp-session-hooks.sh --check` — verify
  optional identity hook installer prerequisites, **no changes**
- `sudo bash tools/install-ppp-session-hooks.sh --install` —
  **explicit opt-in** root-owned scripts in pppd ip-up.d/down.d;
  no daemon restart and no firewall changes. A new PPP connection
  must be made to generate an authenticated username mapping.

For the interactive operator:
`sudo bash l2tp-manager.sh`, then **menu 16** → option 4 adds
a CA2/CA3 plain account with CHAP only, atomic allocation and
no automatic Winbox/API forwarding. No strongSwan/PSK credential
generation or service restart is requested by this new path.
Options 1–3/5–6 inspect, diagnose, disable/enable/remove **disconnected**
accounts and report health. Legacy menu 4 still offers optional
PSK metadata; it uses the same locked PPP account writer.

### How allocation preserves old and new accounts

- The lock is held across CHAP parsing, active-kernel peer discovery,
  reserved-address checks, deterministic lowest-free IPv4 selection,
  and private atomic file replacement.
- No new `*` dynamic-address account is minted. Existing wildcard
  accounts are preserved, but **new allocation is refused** until
  wildcard authorizations can be audited.
- No two managed static usernames are allowed the same assigned IP
  during normal create; active sessions with a conflicting peer are
  included in address occupancy.
- Deleted account IPs can only be reused if it is not live, no
  configured route, forward, direct6 or GRE egress depends on it.
  Existing disabled usernames retain their addresses.
- Configured assigned-IP mappings are stable across restarts because
  they are persisted in `chap-secrets`; the session-identity hook
  runtime state in `/run` is intentionally ephemeral.
- For correctness if `pppN` is rapidly reused, delayed `ip-down.d`
  events do **not** erase the most recent identity record. Only a
  matching **live kernel interface index** and peer IPv4 make a hook
  record trustworthy; obsolete records in `/run` are ignored and
  disappear at reboot or are overwritten by a later successful UP.
  If the hook is not installed, usernames are marked as inferred.

**Concurrency guarantee limitation:** external scripts editing
`chap-secrets` without observing the new lock can still race.
The manager uses a final source-file compare to detect most such
races, but a last-moment out-of-band writer still requires
administrative serialization. Migrate all account writers to this
tool before asserting global concurrency safety.

### Service / egress path

- Preserve `xl2tpd.conf`, `options.xl2tpd` and existing CHAP users.
  CHAP account changes do **not** intentionally restart the daemon;
  runtime pppd reread behavior must be verified on the actual host.
- The existing VPS may have broad subnet-scoped `MASQUERADE`, but
  policy routing/GRE or direct IPv6 steering can override individual
  client paths. No new broad NAT rule is installed in this change.
- On actual Polaris, check the effective `ip -4 rule show`,
  `ip -4 route get` from each PPP peer, `iptables-save` or nftables
  backend, related `conntrack` entries and the Linux public interface.
  The *observed* public IP from an HTTPS endpoint on CA1 and CA2 is
  the acceptance evidence; matching the configured NAT rule is not.
- Preserve existing forwards and **never** create public Winbox
  8291/API 8728 exposure by default. Do not restart the existing
  `l2tp-forwards.service` just to add an account.
- No packet-steering changes are made on Polaris. Client-connection
  selection across CA1/CA2 remains a RouterOS routing/NAT policy.

## RouterOS 7.25.1: independent WAN underlays

**Confirmed upstream capability:** RouterOS L2TP clients support
an endpoint syntax `connect-to=server-address@vrf-name`, allowing
a specific VRF routing table for the client transport. See the
official [MikroTik L2TP documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/2031631/L2TP)
and [VRF documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328206/Virtual%2BRouting%2Band%2BForwarding%2B-%2BVRF).
`/routing rule` `lookup-only-in-table` can prevent fallback when a
route is unavailable, but L2TP's local router-originated endpoint
must actually select the intended VRF (source-based rules alone may
not bind it).

**These are read-only discovery commands on RouterOS**, not a
configuration script:

~~~text
/system/resource/print
/interface/l2tp-client/print detail
/ip/vrf/print detail
/routing/table/print detail
/ip/route/print detail
/routing/rule/print detail
/ip/firewall/mangle/print detail
/ip/firewall/nat/print detail
/ip/firewall/filter/print detail
~~~

Before applying a proposed MikroTik configuration, operator must
verify actual WAN interface bindings, live WAN2 gateway/address,
existing WAN1-pinned /32 route to the VPS, available source-based
or VRF underlay, mangle/VRF precedence, route reachability,
DNS routing, NAT and kill switch.

Proposed *model* (do not paste as a live executable script):
1. Leave `L2TP-POLARIS-CA` / CA1 unchanged, with its existing
   CHAP identity and WAN1 route.
2. Give WAN2 a separate, actually configured VRF with a verified
   reachable default route through the WAN2 gateway. Ensure moving
   interface into VRF does not break its DHCP/LTE or existing routing.
3. Create a **second** L2TP client with a different CHAP identity
   and `use-ipsec=no`, `allow=chap`, and
   `connect-to=verified-VPS-address@verified-WAN2-VRF`.
   Set `add-default-route=no` and `disabled=yes` at staging; after
   audit, explicitly enable only the new CA2 interface.
4. If a route to the public VPS is already pinned to WAN1 in
   `main`, **do not delete or rewrite** it: CA2 must resolve
   its endpoint in WAN2's distinct VRF, not in the WAN1-pinned
   main table.
5. Place CA2 clients/routes into a **fail-closed** forwarding
   policy. On loss of both CA1/CA2, the selected traffic must
   remain dropped, not fall back to WAN1/WAN2 direct Internet.
6. For load distribution, classify only **new** client connections
   (e.g., RouterOS connection marks/PCC as supported), retain
   routing mark/selected tunnel for established flows, exclude
   unhealthy tunnels from new connections and keep original
   source/destination NAT return-path affinity.
7. MTU/MRU, upstream packet size, UDP/1701 reachability, CHAP
   credentials, timeout, reconnect, and WAN flapping require
   real-device validation. Multiple tunnels do not aggregate
   bandwidth for a single TCP flow.

Official references:
- RouterOS L2TP properties:
  https://help.mikrotik.com/docs/spaces/ROS/pages/2031631/L2TP
- RouterOS VRF endpoint binding:
  https://help.mikrotik.com/docs/spaces/ROS/pages/328206/Virtual%2BRouting%2Band%2BForwarding%2B-%2BVRF
- RouterOS routing rules and lookup-only:
  https://help.mikrotik.com/docs/spaces/ROS/pages/59965508/Policy%2BRouting
- RouterOS packet forwarding/policy order:
  https://help.mikrotik.com/docs/spaces/ROS/pages/328084/IP%2BRouting

## Acceptance protocol (no results fabricated)

All items below are **NOT TESTED** on the actual MikroTik/Polaris pair
until operator provides direct evidence.

| # | Test | Required evidence | Status |
|---|---|---|---|
| 1 | CA1 connects | existing PPP identity and address intact | NOT TESTED |
| 2 | CA2 joins during CA1 | simultaneous distinct `pppN` interfaces and CHAP identities | NOT TESTED |
| 3 | Unique PPP IPv4 | no duplicate configured or live peer addresses | NOT TESTED |
| 4 | Both clients reach HTTPS IPv4 | direct external reachability through each tunnel | NOT TESTED |
| 5 | Same CA egress address | both external IPv4 observations equal the actual VPS WAN public IP | NOT TESTED |
| 6 | New account without CA1 drop | timestamps of CA1 traffic + PPP uptime before/after add | NOT TESTED |
| 7 | Disconnect CA2, CA1 intact | CA1 uptime and traffic unchanged | NOT TESTED |
| 8 | Reconnect CA2 | same static PPP peer address and HTTPS egress | NOT TESTED |
| 9 | Duplicate allocation rejected | isolated tests + negative live test in maintenance | NOT TESTED |
| 10 | Restart preserves users | backup, planned maintenance, CHAP entries unchanged | NOT TESTED |
| 11 | Port forwards intact | previous owned forwards responsive; no new exposures | NOT TESTED |
| 12 | Management ports protected | effective VPS/provider firewall + RouterOS rules | NOT TESTED |
| 13 | No loops/asymmetry | route lookups, no repeated TTL/dead routes, conntrack | NOT TESTED |
| 14 | Upgrade old single tunnel | CA1 still works with no conversion | NOT TESTED |
| 15 | Fresh install | disposable test instance with default CHAP, no forced encryption | NOT TESTED |
| 16 | Rollback | restore snapshot on test host, CA1 reconnect and egress | NOT TESTED |

Offline Python tests use mocked kernel interfaces/CHAP and do
**not** certify `xl2tpd`'s actual session demultiplexing or
NAT behavior. Those are product release gates.

## Upgrade and rollback (VPS)

1. Backup actual `chap-secrets` and project settings with private
   root-only permissions, preserve existing PPP account IPs and
   active sessions. Keep a separately cloned/reviewed checkout;
   do not swap the source path used by `l2tp-forwards.service`
   during an active session.
2. Validate script syntax/unit tests, current active `pppN` and
   route behavior, then use **menu 16** solely for new plain
   accounts. Do not select installer/uninstaller, legacy delete
   path or forward-restart commands.
3. Keep the original CA1 CHAP line untouched. If CA2 must be
   removed, confirm that its PPP interface is disconnected and
   that no forward/route/direct6/GRE config references its IP.
4. Restore CHAP from the private backup only when justified and
   when external writers/clients are coordinated. The new CLI
   does not modify xl2tpd.conf, PPP options, firewall or NAT.
5. On rollback, return to original source checkout, validate
   `l2tp-forwards.service` source dependency, remove the
   optional session-identity hook only if ownership verified,
   and confirm the existing CA1 PPP session and external egress.
6. If code deployment or dynamic DNS/VRF changed WAN endpoint
   unexpectedly, stop and use MikroTik's separately approved
   RouterOS rollback strategy. No live MikroTik changes
   were executed in this repository task.

## Remaining known issues / not addressed here

- Existing legacy `start_forwards` and `stop_forwards` use broad
  `pkill -f`, firewall restore and route delete/add. Full scoped
  replacement requires a separate maintenance/recovery test.
- Legacy menu 5 delete still restarts all of `xl2tpd` after
  explicit confirmation; new menu 16 avoids this high-impact path.
- Existing global PSK is shared for optional iPhone L2TP/IPsec;
  unselected metadata does not technically forbid anyone already
  knowing that PSK from using it. Plain clients use
  `use-ipsec=no` and keep CHAP only.
- Custom scripts that edit `chap-secrets` without acquiring the
  same lock are an out-of-band race; do not claim guaranteed
  concurrency across arbitrary writers.
- RouterOS model, firmware, hardware CPU constraints and actual
  WAN routing have not been measured by connected tools.
- No live dual-tunnel egress or kill-switch test performed:
  **release status remains pre-production**.
