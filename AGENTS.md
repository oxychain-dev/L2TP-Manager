# AGENTS.md — Engineering and Operations Contract

> Scope: the entire repository. Read this file, `PLAN.md`, and the relevant implementation before making changes. This is an operationally sensitive networking project, not an isolated demonstration.
>
> Authority: repository changes may be performed using an authorized GitHub connection. A repository connection **does not** confer access to any Linux host or MikroTik router. Never report a host change, deployment, passed integration test, or a successful connection without observed evidence.

## 1. Mission and priorities

Build and maintain a portable, secure, production-conscious L2TP management solution that:

1. Supports controlled, reproducible L2TP/PPP deployment and per-user address management.
2. Allows host-local configuration of IPv4 addressing, ports, DNS, and PPP MTU/MRU; **never embeds an operator's machines, IP addresses, interfaces, gateways, or credentials in generic code**.
3. Supports opt-in IPv6 access for one selected L2TP client over an existing GRE tunnel to an independently operated IPv6 egress gateway.
4. Preserves unrelated services: SSH, existing L2TP peers, other VPNs, GRE, Cloudflare WARP, Docker, host routing, firewall administration, and persistent volumes.
5. Keeps changes narrow, idempotent, observable, reversible, and usable across supported systems.
6. Minimizes avoidable packet fragmentation, blackholes, retransmissions, latency, downtime, and configuration drift **without promising physically impossible zero loss or minimum ping**.
7. Separates reusable repository behavior from per-deployment configuration, credentials, and runbooks.

Priority order: prevent lockout/data loss > keep existing sessions/traffic working > security > correct forwarding/return paths > persistence/recovery > performance > convenience.

## 2. System model

Roles (logical, not hard-coded hostnames):

- **Ingress server:** Linux host running xl2tpd/pppd. It authenticates clients, terminates L2TP, and may forward selected clients through GRE. Its host default routes and unrelated tunnels must not be changed.
- **RouterOS client:** MikroTik or another PPP-compatible router. IPv4 peer address identifies the particular L2TP session. IPv6CP may establish only link-local IPv6; globally usable IPv6 requires additional addressing and routing.
- **GRE egress gateway:** separate Linux host with an existing GRE adjacency and a verified IPv6 egress. It can route a provider-delegated public IPv6 prefix or, if no public routed prefix exists, use tightly scoped ULA-to-public IPv6 SNAT.
- **Other co-resident networking:** Docker, WARP, site-to-site GRE, host SSH, firewalls, port forwards, user-managed routes, and other VPNs are out-of-scope unless explicitly included in an approved change.

Typical intended flow:

~~~text
Selected RouterOS L2TP client
     | PPP/L2TP, IPv4 peer + IPv6CP, PPP MTU/MRU
     v
Linux L2TP ingress (dynamic PPP interface per session)
     | IPv6 source policy route for ONLY that client's ULA /128 or LAN /64
     v
Existing GRE tunnel (IPv6 inside GRE over underlying transport)
     v
IPv6 egress gateway (return route; scoped FORWARD; public-prefix route or SNAT66)
     |
     v
IPv6 Internet
~~~

An independent IPv4 PBR table may send this selected client's IPv4 through GRE. Never conflate IPv4 PBR with IPv6 PBR. Existing clients may use different egress paths; one client's selection must not leak into another client's routing.

## 3. Non-negotiable operating rules

### 3.1 Inspect, diagnose, plan, change, validate

1. Define the requested result, blast radius, affected users and rollback criteria.
2. Inspect read-only evidence: versions, effective config, interfaces, link state, routes and rules, firewall backends/chains, persistent snapshots, services, active peers, and remote endpoint prerequisites.
3. Distinguish **observed fact**, documented behavior, hypothesis, and unknown. An interface that is UP does not prove end-to-end reachability.
4. Write a minimum-change plan: dependencies, order of operations, backups, interruption risk, and recovery.
5. Perform only authorized, reviewable changes; seek explicit approval before disruptive migration, security-policy replacement, bulk deletion, or service restart that terminates active sessions.
6. Validate real forwarding and persistence. Roll back just the resources owned by the change if validation fails.
7. Record the result and remaining risks.

No unrequested global firewall flush, iptables-restore, ip6tables-restore, route flush, sysctl rewrite, Docker prune, package purge, broad pkill, service restart, or reboot.

### 3.2 No host-specific hardcoding

Do not embed real public/private deployment IPs, client usernames, ULA assignments, gateway addresses, GRE/WARP/Docker names, DNS choices, credential material, interface names, Unix usernames, routing-table IDs or policy priorities into general-purpose functions.

Allowed:
- Protocol constants and genuine application defaults, clearly labeled as defaults and overrideable.
- Exact repo-owned file paths and well-defined configuration schemas.
- Sanitized examples from TEST-NET / documentation address ranges, clearly marked non-executable.
- Values supplied in a validated host-local configuration or discovered from the running host.

Runtime discovery should use appropriate structured system tools (`ip`, `sysctl`, `ss`, PPP peer metadata, service manager, package database), fail on ambiguity, and never guess that a live client uses `ppp0` or `ppp1`. If a value represents policy/intent rather than something discoverable (egress gateway, routing table, LAN interface, choice of SNAT vs routed prefix), require explicit validated configuration.

This public repository must not contain specific deployment inventories or live credentials. Redact private infrastructure evidence before posting in GitHub Issues/PRs.

### 3.3 Source is not deployed state

- A successful PR, a cloned worktree, or a clean CI run does not prove any change was deployed or executed on a host.
- A running systemd service can execute a script directly from a Git working tree. Switching that worktree's branch changes what a later service invocation would run. **Do not casually run git switch/pull/reset in a service's live code directory.** Use an isolated worktree/release path and a controlled deployment with health check and rollback.
- A branch tracked by `origin` is not necessarily merged into `main`. Treat Draft PR features as under review.

## 4. Current repository layout and ownership

- `l2tp-manager.sh`: interactive entrypoint; any new option must preserve existing service CLI behavior.
- `config/defaults.conf`: application defaults and optional root-owned per-host network configuration.
- `lib/core.sh`: environment discovery, validated network settings, IPv4 pool allocation, firewall abstraction.
- `lib/install.sh`: installation, service setup, firewall/NAT rules and uninstallation.
- `lib/users.sh`: PPP account management; sensitive data handling; deterministic IP assignment.
- `lib/forwards.sh` and `lib/services.sh`: managed port forwards and service lifecycle.
- `l2tp-routes-manager.sh`: separately managed static routing functions.
- `tools/ipv6-gre.py`: experimental, opt-in per-client IPv6/GRE routing and gateway NAT helper. **Not yet certified production-ready.**
- `docs/ipv6-gre.md`: IPv6 architecture and manual deployment notes.
- `examples/ipv6-*.json`: intentionally empty per-host templates, not ready-to-apply production configurations.
- `tests/network.sh` and `.github/workflows/verify.yml`: existing static/allocator checks; not full integration proof.
- `PLAN.md`: development roadmap, requirements, evidence state, risks, validation gates, and remaining work.

When adding abstractions, reuse the existing layout. Avoid unnecessary new daemons, duplicated firewall managers, heavy dependencies, or a second global routing framework.

## 5. IPv4 / PPP contract

- VPN subnet, local PPP IP, allocation start/end, DNS, port, MTU and MRU are per-host settings validated before use.
- Reconcile configured address pool against existing `chap-secrets`, active PPP peers, routes, firewall NAT and forwarding rules. Reject duplicate allocation, overlap, invalid CIDR, or ambiguous migration.
- Keep existing users and their static addresses unchanged during upgrades. Never silently rewrite `chap-secrets`.
- The requested deployment uses PPP MTU=1280 and MRU=1280; keep these configurable in global code. New sessions must be checked at runtime (`ip -d link` / `ip -s link`), not only by reading a file.
- MSS handling should be scoped to forwarded PPP TCP SYN traffic, preferably PMTU-aware where verified. Do not globally force an MSS value or change physical/GRE/WARP MTU as a proxy for solving a PPP issue.
- IPv4 TCP MSS=1240 is the nominal no-option figure when the effective IPv4 path MTU is 1280; IPv6 TCP MSS=1220 is the nominal base-header figure. Neither number automatically proves end-to-end PMTU or applies to UDP/QUIC.
- IPv4 client source PBR is not enough: the GRE peer must have compatible forwarding, return route, and NAT as applicable. Make source/rule/table selection explicit and ensure no unsafe fallback to the ingress WAN.

## 6. IPv6 contract

1. **IPv6CP is not address delegation.** Link-local `fe80::` peers prove negotiated IPv6CP, not Internet IPv6 access.
2. For a non-delegated public IPv6 deployment, generate one random RFC 4193 ULA /48 per deployment; retain it durably. Allocate a distinct router /128 and, only if needed, an independent LAN /64. Do not regenerate at boot or reuse the GRE link's ULA prefix.
3. Where a real public prefix is routed to the client, prefer routed IPv6 over NAT66. Do not assign an on-link egress WAN /64 to an unrelated MikroTik.
4. On ingress, identify the correct PPP interface by the exact active IPv4 peer and IPv6 state; account for reconnection, reordered events, duplicate sessions, interface renaming, and disconnect cleanup. Do not route a prefix to another client's PPP device.
5. Use a **dedicated** IPv6 table and rule priority per intended source prefix or a collision-checked equivalent. Preserve main table and WARP policy. A fail-closed unreachable fallback is necessary when the GRE path disappears. Check precedence of other rules and potential conntrack/asymmetric routes.
6. On the GRE gateway, verify GRE IPv6 reachability, return route to the client ULA, WAN global IPv6, source-specific SNAT scope, and IPv6 forwarding before applying rules.
7. If the gateway learns its IPv6 default route via Router Advertisement while forwarding is enabled, check `accept_ra` behavior for the actual WAN. Linux `accept_ra=2` can be required; never alter unrelated interfaces blindly.
8. Do not block ICMPv6 Packet Too Big, Neighbor Discovery, or required error messages; PMTU discovery is essential. IPv6 minimum link MTU 1280 does not mean every encapsulated underlay packet can pass unfragmented.
9. For MikroTik, discover the real L2TP and LAN interfaces, inspect existing RouterOS IPv6 tables/routes/firewall, avoid an unintended global `::/0` in the main table, and choose a dedicated routing table/policy when other IPv6 uplinks exist.
10. Distinguish an internal ULA, a delegated public IPv6 source, an existing global interface address, and the **observed public egress IPv6** seen by an Internet echo service.

Before enabling a production IPv6 feature, the full forward and reverse paths must be verified. Multi-client and multi-prefix support must isolate tenants; a single-client helper must not be misrepresented as a complete multi-tenant manager.

## 7. Firewall, NAT, and persistence contract

- Inspect `iptables` backend (nf_tables vs legacy), `nft` rules, chain order, policies, counters, UFW presence, Docker rules, `netfilter-persistent` ownership, and any provider firewall.
- Do not assume UFW is present just because legacy `ufw-*` chains exist. Do not silently install or activate a competing firewall.
- Scope rules by validated source/destination prefix, interface, direction, conntrack state, and protocol; use idempotent check-before-add, explicit ownership and reversible removal.
- Preserve access to SSH and other management planes. Never replace `INPUT`/`FORWARD` policy remotely without verified alternate access and rollback.
- Do not treat an internal routing policy as encryption or source IP restriction as authenticated access. Restrict exposed MikroTik Winbox/API forwards to authorized sources and strongly prefer secure management.
- Never replay the **entire** `/etc/iptables/rules.v4` from an unrelated start-forwards service; doing so can overwrite dynamic Docker/firewall state. Define rules owned by this project and manage them narrowly.
- Do not blindly call `netfilter-persistent save` on shared hosts: it can capture stale Docker, old bridges, and transient rules. Build explicit persistence and ordered/conditional restoration of only project-owned resources.
- Account for GRE/WARP/Docker/PPP boot ordering and subsequent reconnections. Persist both forward and return path decisions, not just one side.
- Do not remove residual Kasm/Docker bridge rules or mounts without read-only dependency checks. An old interface with no carriers is evidence to inspect, not license to flush unrelated tables.
- Uninstallation must undo **only** owned resources; never disable shared IPv4/IPv6 forwarding, kill all pppd processes, vacuum host journals, remove unrelated volumes or routes, or purge packages used elsewhere.

## 8. Implementation standards

### Bash

- Explicit Bash shebang and compatible Bash syntax; quote expansions; use arrays where appropriate.
- Validate environment and privileges, inputs, network ranges, interfaces, dependencies and configuration ownership.
- Avoid `eval`, arbitrary sourcing of instance configuration, unsanitized regular expressions in path/username matching, and unbounded loops.
- Make changes idempotent and atomic where practical; back up existing files before modifying; validate syntax before reload.
- Keep error propagation visible: do not claim success if a firewall or sysctl command silently failed.
- Avoid global side effects in library sourcing and avoid restarting all L2TP sessions to add a single user unless demonstrated necessary.
- Never print stored passwords or authentication databases to general logs, CLI diagnostics, GitHub CI, or pull requests.

### Python

- Prefer Python standard library for the optional IPv6 helper; validate IP networks with `ipaddress`.
- Treat JSON as untrusted data, enforce root ownership/permissions on operational configs, and reject inconsistent roles, prefixes and routing priority/table conflicts.
- Do not use shell execution to assemble network commands. Fail safely on missing links, conflicting policies, missing dependencies, or disabled IPv6 forwarding.
- Design dry-run as **read-only** and clearly mark unknown host state; never print secret values.
- Rollback should remove only exact helper-owned rules/routes and must not remove pre-existing lookalikes.
- Reconciliation after partial failure, link flap, restart, and reconnect is mandatory before calling a helper production-ready.

### RouterOS

- Support documented RouterOS 7 syntax and actual discovered interface/table names. Avoid broad configuration exports containing secrets.
- Keep routing changes explicit, scoped, and reversible. Distinguish router-originated traffic from LAN transit.
- Verify FastTrack/connection tracking/firewall interactions; do not assume router IPv6 and client LAN IPv6 use the same source policy.
- Document any material protocol limitation of the installed device/CPU and preserve existing WAN failover routes.

## 9. Observability and performance

Measure rather than assert:

- PPP session state, MTU/MRU, IPv6CP peers, route selection, NAT/forward counters, GRE interface counters and errors.
- External public IPv4/IPv6 egress from the selected client, not just from the ingress or gateway host.
- RTT distribution, packet loss, jitter, throughput, TCP retransmits, `IpFragFails` deltas, CPU load, and queue drops under relevant traffic.
- Compare with baselines and repeat under equivalent conditions. Aggregate historical counters cannot establish which tunnel or traffic caused a failure.
- Test payload sizes and outer encapsulation (GRE/IP/UDP/L2TP/PPP) when assessing fragmentation. Preserve PMTUD and ICMP/ICMPv6.
- Avoid arbitrary congestion control, qdisc, offload, or kernel tuning without an observed bottleneck and rollback criterion.

## 10. Test, review and release gates

Minimum checks for any change:

- Syntax: `bash -n`, Python compilation, shell lint/static analysis where practical.
- Unit/negative cases: CIDR boundaries, allocator collisions, malformed/untrusted config, IPv4/IPv6 validation, idempotency, duplicate policy priorities, missing PPP peer, stale interface, conflicting firewall rule, partial failure.
- Integration: ephemeral Linux network namespaces/veth/PPP simulation where practical; inspect resulting routes, iptables/nft changes, and rollback.
- Reconnect/reboot: start order, PPP index changes, GRE loss/return, WAN RA loss/refresh, Docker service restart, concurrent user connections, static IP reassignment.
- End-to-end: actual RouterOS IPv6 source; gateway observed SNAT; HTTPS IPv6 egress; no unauthorized traffic from other clients; no lost SSH/other VPN traffic.
- No CI privileged operations against real hosts. CI green means **the specific CI checks passed**, not full production readiness.
- Changes must have an impact note, evidence, reproducible validation, and rollback. Keep high-risk networking PRs in Draft until their release gates are satisfied.

Current PR/source features are not a license to deploy automatically. See `PLAN.md` for known gaps and required milestones.

## 11. Working agreement for agents

When asked to implement a feature:

1. Read the affected existing code and documented system behavior.
2. Summarize observed evidence, unknowns, the narrowest useful change, and rollout risk.
3. Implement and test on a separate branch/worktree; do not modify an actively executed deployment tree.
4. Use small related commits; update tests and docs with the change.
5. For any GitHub action, report exact repository, branch, commit, PR, and check status. Do not report merges/deployments unless performed and verified.
6. Provide safe, host-neutral commands or scripts, requiring validated operator input for policy decisions; no fake executable IPs or interfaces.
7. Distinguish DONE / IN PROGRESS / NOT STARTED / BLOCKED with evidence. Do not erase unresolved problems by rewriting the plan.
8. If live-host access is unavailable, stop at code/docs and give explicit operator-run validation; never claim remote state was changed.

### Definition of done

A feature is done only when its documented acceptance tests pass for its promised scope, its real-host prerequisites are understood, its failure/rollback path is tested, and sensitive or host-local configuration is not embedded in the public repository.

## 12. Primary references

- Project documents: `README.md`, `docs/ipv6-gre.md`, `PLAN.md`.
- Linux kernel IPv6 forwarding / RA: https://docs.kernel.org/networking/ip-sysctl.html
- Policy routing: https://man7.org/linux/man-pages/man8/ip-rule.8.html
- MikroTik PPP/IPv6: https://help.mikrotik.com/docs/spaces/ROS/pages/132350049/PPP%2BAAA
- RFC 4193 (ULA): https://www.rfc-editor.org/rfc/rfc4193
- RFC 8200 (IPv6): https://www.rfc-editor.org/rfc/rfc8200

Check upstream documentation against the exact installed system versions. Sources are supporting references, not instructions to execute commands blindly.


### Mandatory direct dual-stack service classes

All non-GRE users must have **real IPv4 AND IPv6 Internet** through the
ingress server (ordinary L2TP and iPhone IKEv2). Only explicitly
selected GRE L2TP users use the remote GRE egress in both families.
Implement per-client source/route isolation, not a global change to the
host default route. Do not publish dual-stack readiness if either client
family cannot reach an external public destination.

Ordinary PPP IPv6CP link-local is insufficient; allocate stable per-user
IPv6 /128 (optional LAN /64), dynamic PPP return route and direct IPv6
egress with routed public prefix or scoped ULA NAT66. IKEv2 needs
separate IPv4/IPv6 VIP pools and XFRM-aware forwarding. iOS with IPv6
pool requires IPv6 default traffic selector ::/0. The ingress WAN
on-link /64 is not proof of delegated routing to clients. See
`docs/direct-dualstack.md`.


## Phase-one operational priority and future onboarding contract (2026-11-14)

These instructions supplement, not replace, the networking/privilege
contract above. The operator's immediate goal is reliable selective
L2TP/IPsec access on Polaris **without affecting existing plaintext
L2TP users or selected GRE/WARP paths**. Later goals are multi-device
client/profile creation, HTTPS dashboard and one-time invitation URLs.

**Phase-one authority:** the user has supplied console evidence from
Polaris, not an authorized remote shell. Source PRs cannot assert
actual server state. Observed strongSwan connection load is a
configuration check, **not** proof of completed IKE_SA/CHILD_SA or
end-to-end phone access. Source of truth for latest observed state:
`docs/PHASE-1-CLIENT-STABILITY.md`.

1. Build and test the actual selected iPhone L2TP/IPsec connection
   first. Require successful kernel IPsec SA + protocol-scoped
   CHILD_SA, matching PPP identity, traffic from the client and
   non-regression of existing clients. Do not enable daemon at boot
   until acceptance/recovery gates pass.
2. Do not claim shared PSK enforces per-user IPsec on a shared UDP
   1701 listener. For protected-only users, use isolated protected
   listener/auth admission and prove plaintext downgrade rejection.
3. Do not imply Android strongSwan app accepts legacy IKEv1/L2TP
   profiles. It supports IKEv2; an EAP/IKEv2 service must be separately
   deployed/tested. A client-select-all action selects multiple
   supported artifacts, not one universal config.
4. Every diagnostic uses read-only discovery and redacts PSK,
   passwords, XFRM keys, auth tokens and private certificates.
   An on-host trusted operator may view a secret for local transfer,
   but never paste it into chat, Git, URLs, logs or bulk dashboards.
5. Existing root-only `global-psk.secrets` is one machine-level
   secret. It is distinct from PPP passwords and IKEv2 EAP registry;
   new clients do not inherit EAP records as PPP users.
6. Live source and future portal remain separate: prefer a narrow
   privileged provisioning helper, no root-running web service, no
   direct reads of password DB, no background secret exposures.
7. An enrollment **invitation** is single use (atomic consume,
   expiry, hash-at-rest); a **subscription** is a separate, scoped,
   revocable read token. No token grants unsupervised root actions.
8. The multi-device CLI/dashboard/one-time URL are **future design
   only**, unless separate tests and verified deployment evidence
   explicitly establish completion. Track milestones in
   `docs/FUTURE-SELF-SERVICE.md` and `PLAN.md`.
9. Git branch ancestry must be compared before a merge: ancestor
   branches already included in development do not require a
   fabricated or empty merge. Never force-merge or rewrite the main
   production branch to satisfy a request for development integration.
10. Stable means tests plus observed production behavior, persistence,
    reboot/reconnect, rollback, user isolation and no regressions.
    CI success alone does not confer this status.


## Global PSK account workflow guardrails (2026-11-14)

The operator clarified that their requested "IPsec user" means a PPP
user to whom the already existing GLOBAL PSK is offered. Do not
pretend a user flag creates an independent IKE key, enforces
encrypted-only traffic or revokes a PSK already learned.

List accounts without secrets by default. Copy-ready details for one
user require an interactive private console and an explicit reveal
confirmation. Account add/edit must not restart active L2TP sessions
automatically or rewrite static IPs used in direct6/GRE/PBR.

A global PSK rotation requires explicit confirmation, no active
IPsec SAs, scoped rollback and coordinated changes on ALL clients.
Never use a service restart to silence optional swanctl plugin
warnings. Distinguish swanctl credentials reload from a disruptive
strongSwan or xl2tpd restart.

Do not claim Phase-1 defect-free or stable from source tests.
Require real iPhone IKE/CHILD_SA, PPP and client egress validation.
See [Phase-1 PSK runbook](docs/PHASE1-PSK-USERS.md).


## Plain L2TP dual-WAN scope and security (2026-11-14)

- A separate mandatory workflow supports concurrent **unencrypted**
  L2TPv2/PPP/CHAP accounts without PSK or MPPE. Do not migrate,
  disable or alter the independent optional iPhone strongSwan/PSK
  configuration to satisfy plain L2TP requirements.
- Never imply CHAP provides payload confidentiality; plain L2TP
  traffic is observable to suitable intermediaries.
- Preserve CA1 static address and WAN1 /32 binding. Each additional
  CA session gets a distinct username, static PPP address and
  RouterOS WAN-specific underlay. Never identify a session by
  source public WAN IP alone.
- Only modify `chap-secrets` under the manager account lock,
  with conflict checks from active PPP interfaces, configured
  routes, forwards, direct6/GRE references, private backup
  practices and no automatic daemon restart.
- Do not open public Winbox or API management ports by default,
  duplicate NAT rules, restart Docker/PPP, or modify RouterOS
  from a VPS-side tool.
- Show session identity as verified only when backed by a
  pppd authentication hook with matching kernel interface
  generation; otherwise label the username inference clearly.
- Use RouterOS `connect-to=address@VRF` only after verifying the
  actual WAN2 VRF/gateway and existing routing policies. Treat
  fail-closed behavior, kill switch and per-flow tunnel affinity
  as a separate on-device integration test.
- The 16 real-device tests in `docs/PLAIN-L2TP-MULTIWAN.md` remain
  NOT TESTED until observed; passing CI means only source tests.


## Latest iPhone field evidence and issue tracking boundary

Observed on Polaris: real IKEv1 ESTABLISHED + ESP CHILD_SA INSTALLED + two-way counters and a simultaneous PPP peer allocated to the prior iPhone account. Do not repeat the earlier claim that **no** iPhone IPsec session was ever established. Do not claim verified authenticated PPP identity, public egress, reconnect or production stability without those distinct tests.

GitHub Issues are disabled for this repository and creation returns HTTP 410. [ISSUE-BACKLOG.md](ISSUE-BACKLOG.md) contains issue drafts, not actual GitHub Issues; enable Issues in repository settings before publishing. Continue using `development` only; do not create unrelated branches to work around issue settings.
