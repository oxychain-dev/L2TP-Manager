# PLAN.md — L2TP Manager Modernization and Dual-Stack GRE Egress

## IMPLEMENTATION STATUS — 2026-11-10 (development source, not production)

- Implemented and source-tested: configurable multi-client `tools/direct6-reconcile.py`, guarded PPP-hook+timer installer, scoped legacy pilot migration tool, global on-host PSK generator, and iPhone dual-family IKEv2 **candidate renderer** with per-user EAP registry. See [safe deployment gates](docs/STABLE-DEPLOYMENT-GATES.md).
- Verified historical live traffic: ordinary L2TP `.10` IPv4 and IPv6 direct Polaris; selected GRE `.11` IPv6 through Warden; IPv4 remote egress still requires fresh real-client verification.
- NOT VERIFIED OR DEPLOYED: new direct6 reconciler/installer on Polaris, new Warden IPv4 persistence, strongSwan IKEv2 endpoint, per-user IPsec enforcement, certificate/pool, iPhone dual-stack and controlled reboot/rollback tests.
- A global PSK file does not itself enable secure L2TP, distinguish user identities, or prevent plaintext downgrade. Without a separate protected endpoint, `ipsec-required` remains metadata only.
- The feature can be integrated into a development branch when source tests pass, while production/main release gates remain OPEN.

## ACTIVE STATUS AND DELIVERY PLAN — 2026-11-10

> **Canonical, evidence-based request/status tracker:** [Full Persian execution plan — every requirement, current status, prerequisites, milestones, acceptance criteria and rollback](docs/EXECUTION-PLAN-2026-11-10.fa.md).
>
> **Most recent verified outcome:** a *direct* ordinary L2TP client on ingress Polaris successfully sent 5/5 IPv6 pings and fetched its public IPv6 address via HTTPS after a manually applied PPP interface rebind. The client switched from ppp1 to ppp0, breaking the pilot's interface-specific rules. The manual repair worked, **but its rules are not persistent**.
>
> **Do not conflate:** (1) a successful packet-path test, (2) a running production-safe reconnect reconciler, (3) successful reboot, (4) generic multi-user support, and (5) deployed selective IPsec. These are distinct release gates.

| Request group | Latest evidence-based status | Next release gate |
|---|---|---|
| Ordinary L2TP IPv4 direct ingress | **Verified on one existing client** | Reconnect/regression and more users |
| Ordinary L2TP IPv6 direct ingress | **Verified pilot on one existing client; NOT persistent** | PPP-event reconciler, stable per-user allocation, WAN RA sync, reboot |
| Selected GRE IPv6 via remote egress | **Earlier real-client IPv6/HTTPS test passed; timers present** | Confirm current reconnection, fail-closed and reboot |
| Selected GRE IPv4 via remote egress | **Ingress source route + remote route/NAT present; not retested end-to-end** | Real-client IPv4 exit and gateway counters, persistence |
| All ordinary L2TP users dual-stack | **Not implemented generally** | Per-user allocation, lifecycle, CLI, tests |
| iPhone IKEv2/IPsec dual-stack, direct ingress | **Not deployed** | strongSwan, dual VIP pools, cert, authenticated test and IPv4/IPv6 egress |
| Selective global IPsec user policies | **Metadata/schema validation only** | Enforced credential/endpoint separation, plaintext-downgrade denial |
| General QA/security/reboot | **Partially completed** | Controlled failure/reconnect/reboot/rollback and PR review |

**Next implementation priority:** stabilize direct L2TP IPv6 after PPP renumbering (P1), then finish GRE IPv4 and all-user dual-stack (P2–P3), then iPhone IKEv2 (P4) and enforced optional IPsec (P5). Preserve existing production connectivity throughout.

**Historical note:** the sections M0–M10 and subsequent dated sections **below** are a cumulative roadmap and may describe earlier states. Prefer the linked active tracker when status statements conflict; do not silently treat historical pending work as complete.

---



> **Purpose:** execution-oriented roadmap covering the requirements established through the L2TP deployment, Linux firewall/persistence work, RouterOS troubleshooting, IPv4 GRE source routing, IPv6 over GRE, and generalization of this repository.
>
> **Status date:** 2026-11-09. Statements about live hosts are **historical operator-supplied observations**, not proof of their current state. GitHub repository edits do not equal production deployment.
>
> **Release rule:** a green syntax/allocator CI check is NOT a full integration test. Keep the implementation PR in Draft until critical safety and data-path acceptance criteria are met.

## 1. Objectives

### Primary user outcome

Provide a reliable, maintainable, host-independent implementation of:

~~~text
RouterOS L2TP client with an assigned private IPv4 peer
   -> encrypted transport when confidentiality is required (L2TP itself is unencrypted)
   -> Linux xl2tpd/pppd ingress
   -> per-client source-policy routing
   -> existing GRE tunnel
   -> independent Linux IPv6 egress gateway
   -> public IPv6 Internet
~~~

IPv4 routing for the selected L2TP client can use a separate source-policy GRE route. IPv6 forwarding is a distinct subsystem: the selected router (and optionally its LAN) receives a stable ULA allocation or a genuinely delegated public IPv6 prefix; the ingress routes only that source; the GRE gateway provides the return path and either routes the public prefix or performs narrowly scoped IPv6 SNAT.

No other clients should lose their existing IPv4/IPv6 routes, SSH access, port forwards, Docker bridges, Cloudflare WARP, or other VPN connectivity.

### Secondary objectives

- Configurable L2TP subnet, server address, client allocation pool, DNS, UDP port, PPP MTU/MRU, and optional per-client egress policy. No deployment-specific values in reusable source.
- Preserved and measurable PPP MTU/MRU 1280 for the current deployment, with TCP MSS clamping where appropriate and no broad MTU edits.
- Safe firewall and NAT ownership; reliable rules across restart, link flap, PPP reconnect, and host reboot without global firewall snapshot clobbering.
- Separate RouterOS routing and LAN IPv6 design that does not change existing IPv4 routing tables or unrelated IPv6 uplinks by default.
- Stable user assignment and service operations; secrets protected; minimal restarts.
- End-to-end validation, observability, performance measurement, and explicit rollback.
- Professional public documentation, tests, review protocol, and compatibility notes.

### Non-goals / exclusions

- No silent migration of live IPv4 addresses solely to enable IPv6.
- No assumption that an IPv4 address maps algorithmically to an IPv6 address.
- No promise of zero packet loss, zero fragmentation under every underlay, minimum achievable ping, or guaranteed speed.
- No implicit activation of GRE, Cloudflare WARP, Docker/UFW, or competing firewall controllers.
- No automatic deployment to live Linux/RouterOS machines from GitHub.
- No representation of plaintext L2TP or GRE as encrypted transport.
- No cleanup of unrelated persistent Docker volumes, routes, services, credentials, or packages.

## 2. Repository and deployment boundaries

### Repository baseline

- Fork repository: `oxychain-dev/L2TP-Manager`.
- Upstream baseline: `safrinnetwork/L2TP-Manager`.
- Implementation work: `feature/configurable-l2tp-network`.
- Review: Draft PR #1, which remains separate from `main` until explicitly merged.
- The project can be checked out in a second Git worktree. However, an operator has also switched the active source directory to the feature branch. This creates an **operational dependency** because the forwarding service executes from a Git source directory. Before service restart/update, verify the actual `ExecStart` and deployed commit. Do not casually merge or pull into that directory.
- Current source feature set includes configurable IPv4 defaults, an IPv4 address allocator, scoped PPP MSS installation, an optional IPv6/GRE helper, JSON examples, Markdown instructions, and basic CI. This is a **development milestone**, not proof of safe production deployment.

### Evidence already supplied (historical and deliberately generalized)

1. Ubuntu Linux ingress used xl2tpd/pppd with at least two concurrent RouterOS L2TP clients; one selected client was assigned its expected static IPv4 address and a dynamically numbered PPP interface.
2. Both clients negotiated IPv6CP link-local addresses; this alone did not provide a routable IPv6 Internet source.
3. The selected client's IPv4 ingress PBR returned the GRE interface when tested with `ip route get ... iif <actual PPP interface>`. A no-`iif` local-route probe earlier returned "Network is unreachable"; that result does NOT refute the forwarded-data-path lookup.
4. A corresponding IPv4 GRE egress policy service was active and enabled, and its dedicated table had a GRE default plus an unreachable fallback. The gateway's full IPv4 return/NAT path was NOT comprehensively validated.
5. Linux ingress and egress hosts had working GRE-link IPv6 addressing and a successful GRE-peer IPv6 ping sample.
6. Linux ingress had IPv4 and IPv6 forwarding enabled; the IPv4 forwarding sysctl was also found in a persistent configuration file.
7. The IPv6 egress gateway had forwarding enabled, a functional public IPv6 WAN path, and `accept_ra=2` on its WAN when its default route was RA-derived.
8. PPP MTU/MRU 1280 was observed in file/runtime; PPP-scoped TCPMSS rules existed in a saved netfilter-persistent rules file and match counters increased.
9. Host firewall output included Docker chains, stale application bridge/NAT rules, legacy UFW-named chains without the `ufw` executable, and public-facing management forward listeners. These require isolated cleanup/security review.
10. Short ICMP samples showed nonzero L2TP path loss, while GRE IPv6 peer ping showed no loss in a small sample. Long-lived fragmentation/retransmission counters also existed. **No root cause or throughput baseline was established.**
11. A ULA /48, router /128, LAN /64 and LAN gateway were generated by the helper on an operator host. Treat the values as **deployment-local artifacts**: they are not included in repository configuration, example defaults, or test data.
12. The remote gateway's IPv6 NAT/return-path and the router's routable IPv6 source/default-route configuration were not deployed and end-to-end validated in the presented evidence.

No code assistant has a confirmed live SSH, local CLI or RouterOS management session to these hosts. Recheck all prerequisites immediately before making operational changes.

## 3. Core invariants and acceptance criteria

| ID | Invariant / acceptance requirement | How to prove |
|---|---|---|
| INV-01 | No host-specific addresses, usernames, topology IDs or credentials in reusable code | Search source and review diff; only application defaults, schemas, tests with documentation ranges |
| INV-02 | No disruption to existing SSH, VPN clients, Docker, GRE, WARP or port forwards | Baseline and post-change active service/session/route comparisons |
| INV-03 | Selected IPv4 L2TP client uses GRE without affecting others | Forwarded `ip -4 route get ... iif` and real traffic on GRE; other clients retain original egress |
| INV-04 | IPv6CP negotiated but not confused with public IPv6 allocation | Link-local observed independently from ULA/public source address and default route |
| INV-05 | Selected IPv6 router /128 routed through GRE; LAN /64 only if requested | Client-source route, ingress PBR, egress return route, and test traffic |
| INV-06 | Gateway replies return to same client via GRE | Symmetric route/conntrack validation on egress and ingress |
| INV-07 | No unintended IPv4/IPv6 WAN fallback when GRE is unavailable | GRE-down negative test: selected flow fails closed; unrelated users continue |
| INV-08 | IPv6 Internet egress verified from actual MikroTik or LAN client | External IPv6 test and observed matching egress public address |
| INV-09 | IPv6 forwarding/RA stay correct when egress is a router | Effective WAN route and `accept_ra` after service/reboot |
| INV-10 | PPP 1280 effective; TCP MSS valid; ICMPv6 PMTU not blocked | Runtime MTU, SYN MSS capture if needed, PMTU testing, firewall ICMPv6 policy |
| INV-11 | Rules/routes survive restart, reboot, reconnect without duplication | Repeat start/stop/reconnect/reboot and count exact owned rules |
| INV-12 | Deployment is reversible without global flush/kill or losing management | Backup, targeted rollback run, SSH/service and client traffic still accessible |
| INV-13 | Credentials and secrets are protected | Permission validation, log sanitization, no secrets in CI/diff |
| INV-14 | Source change and deployment success reported separately | Exact commit, CI result, host verification proof |

## 4. Delivery roadmap

### M0 — Baseline, ownership and release boundaries

**Status: PARTIALLY COMPLETED (repository inspection and user logs); live deployment inventory pending.**
**Priority: P0.**

- [x] Identify upstream, authorized fork, feature branch, and Draft PR.
- [x] Inspect current repository modules and their relevant networking behavior.
- [x] Confirm that the GitHub connection has permission to edit the fork.
- [ ] Record a sanitized, deployment-local inventory outside Git: OS/kernel, architectures, actual packages/versions, init system, netfilter backend, default IPv4/IPv6, IPv6 RA, GRE/IPIP, WARP, Docker, provider firewall, RouterOS profile/table/LAN layout.
- [ ] Record current service `ExecStart`, source checkout/commit, config files, linked PPP accounts and any active maintenance sessions.
- [ ] Preserve backups of config, `chap-secrets` (securely), iptables/ip6tables/nft, current routes, units and persistent firewall definitions without pushing them to Git.
- [ ] Establish an out-of-band rescue/reconnect plan and a clear rollback owner before high-impact changes.
- [ ] Confirm the data-plane design: routed public IPv6 prefix vs ULA+NAT66; router-only /128 vs router + LAN /64; which RouterOS clients/LANs opt in.

**Gate:** source/deployment boundaries and exact recovery plan documented and reviewed.

### M1 — Host-independent IPv4 VPN configuration

**Status: IMPLEMENTED IN FEATURE BRANCH; LIMITED CI SUCCESS; LIVE DEPLOYMENT NOT VERIFIED.**
**Priority: P1.**

- [x] Introduce per-host overrides for VPN CIDR, server address, pool endpoints, DNS, UDP port, MTU/MRU.
- [x] Remove hard-coded pool assumptions from the main IPv4 address allocator.
- [x] Add CIDR/pool consistency validation and a basic negative-regression test.
- [x] Use validated settings in key installer/firewall paths.
- [x] Default new PPP MTU/MRU to 1280 while retaining per-host override.
- [ ] Audit **all** remaining code paths and docs for encoded subnet, port, server address and interface assumptions (including uninstall, user editing, port forwarding, route manager and examples).
- [ ] Verify allocator behavior for large ranges, invalid octets, canonical CIDRs, user-space exhaustion, static-IP reassignments and duplicate entries.
- [ ] Verify configuration ownership and readability checks across supported Ubuntu/Debian versions; test denial on symlinks, malformed content, duplicates and unsafe permissions.
- [ ] Add migration tooling/design for existing in-use IPv4 pools; refuse to change an active pool by merely re-running install.
- [ ] Prevent installer from overwriting an existing working PPP config without explicit user choice, backup and rollback.

**Gate:** clean install and migration dry-run both reproducible; active users and routes unchanged unless a migration was explicitly approved.

### M2 — Firewall/NAT ownership and safe service lifecycle

**Status: HIGH-PRIORITY TECHNICAL DEBT, NOT COMPLETE.**
**Priority: P0 before merge/deployment of service changes.**

Observed code risks to address:

- [ ] Replace whole `iptables-restore` from `start_forwards()` with narrow project-owned rule reconciliation; do not replay shared Docker snapshots.
- [ ] Replace broad `pkill -f` patterns for socat and other processes with exact owned PID/process tracking.
- [ ] Make adding/removing rules idempotent and atomic; check for duplicates and preserve ordering with Docker/WARP/UFW/legacy/nft chains.
- [ ] Stop exposing default management ports to all IPv4 sources unless operator policy explicitly permits it; support allowlists and verify effective provider firewall.
- [ ] Avoid global `FORWARD ACCEPT` policies or broad subnet allow rules if narrower interface/state rules suffice.
- [ ] Avoid unnecessary restart of every `xl2tpd` session during account changes; implement safe reload or documented controlled restart.
- [ ] Scope uninstall to project-owned services/config/rules only; do not kill unrelated PPP peers, modify shared forwarding sysctls, erase journals, destroy unrelated persistent volumes, or purge shared dependencies.
- [ ] Deal explicitly with residual old application bridge/NAT rules **only after dependency discovery**. Never automatically purge unrelated bridges.
- [ ] Separate "disable IPv6 ingress" from "block required ICMPv6"; avoid violating PMTU and ND.
- [ ] Add netfilter/nft backend capability detection and tests for persistence conflict with dynamic Docker chains.
- [ ] Inventory effective `INPUT`, `FORWARD`, `POSTROUTING` chains and provider-side firewall before changing any policy.

**Gate:** replaying a forwarding service cannot rewrite unrelated firewall state; rollback preserves SSH and other tunnels.

### M3 — Harden and productionize IPv6/GRE helper

**Status: PROTOTYPE IN FEATURE BRANCH; NOT PRODUCTION-CERTIFIED.**
**Priority: P0 for IPv6 goal.**

Existing prototype: `tools/ipv6-gre.py` provides ULA generation, per-host role JSON, a selected PPP peer check, IPv6 policy/route manipulation, and gateway scoped IPv6 FORWARD/SNAT.

Work remaining:

- [ ] Add independent parser/config-schema tests; reject duplicate or conflicting policy priorities (including optional LAN rule priority +1), table collisions, interface transitions and overlapping ULA assignments.
- [ ] Test all `apply`/`down` operations under namespace-based simulated networking, including command failures partway through and rollback ownership.
- [ ] Verify dry-run performs **zero mutations**, and reports what would change rather than assuming success.
- [ ] Audit policy routing rule format and `ip -6 route` behavior for kernel/iproute2 differences; ensure a failed child command is never silently accepted.
- [ ] Verify IPv6 route and firewall-rule ordering versus WARP/other policies, Docker and existing egress security rules.
- [ ] Protect selected source from fallback to ingress WAN when GRE is down, including cold-boot gaps before a source policy is installed.
- [ ] Design predictable re-entry across duplicate PPP connect events, TCPMSS rule ownership and all IPv6 prefix changes.
- [ ] Implement robust dynamic PPP lifecycle integration using normal `ip-up.d`, `ipv6-up.d` and `ip-down.d` hooks without assuming any fixed PPP interface number.
- [ ] Ensure reconnect to a new PPP device withdraws the old route; removing one client must not remove another client's route.
- [ ] Handle gateway restart, link flap, RA refresh, SNAT public IPv6 change, ip6tables/nft backend differences and persistence.
- [ ] Make the egress IPv6 address choice dynamic or operator-validated; define what happens when public IPv6 rotates.
- [ ] Decide whether to support multiple clients and LAN prefixes natively. If not, reject conflicting second-client configuration and document one-client scope.
- [ ] Complete a precise deprovisioning path for source policy and fail-closed route; currently `down` intentionally leaves them for safety.
- [ ] Add route/NAT test fixtures and verify idempotent duplicate application and exact deletion.
- [ ] Make production tooling perform explicit preflight and provide an auditable rollback manifest.

**Gate:** simulated failure and reconnect tests pass; rollback and fail-closed semantics are proven, not merely documented.

### M4 — RouterOS client IPv6 behavior

**Status: PPP IPv6CP VERIFIED IN PRIOR OPERATOR OUTPUT; GLOBAL IPv6 UNCONFIGURED.**
**Priority: P0 for IPv6 goal.**

- [x] Verify that PPP profile allows IPv6 and an L2TP client can negotiate link-local IPv6 with Linux.
- [x] Verify that PPP IPv4 peer identity, tunnel MTU/MRU and ingress source PBR align for the selected client.
- [ ] Preserve existing RouterOS IPv4 routes, other L2TP clients, WAN failover, FastTrack rules, bridge/LAN policy and management access.
- [ ] Allocate/stably store one private ULA /128 for router and optional separate LAN /64, without publishing site-specific values.
- [ ] Decide whether the IPv6 feature targets the router only or its LAN devices as well.
- [ ] Assign router IPv6 to the **correct** L2TP interface and verify the source selection; no guessed interface name.
- [ ] Install a scoped IPv6 default route or source policy for selected router/LAN traffic, not a global main-table IPv6 default unless deliberately intended.
- [ ] When LAN support is enabled, discover the actual LAN bridge/interface, configure RA/SLAAC and DNS design, and verify the LAN's route and firewall policies.
- [ ] Check RouterOS 7 version-specific commands and whether PPP link-local gateway/default route choice is supported in the target build.
- [ ] Implement explicit RouterOS rollback for address, route, table, rule, and optional LAN RA changes.
- [ ] Test router-originated ICMPv6/HTTPS and, separately, LAN client IPv6/HTTPS; avoid interpreting one as proof of the other.

**Gate:** actual chosen router and (if selected) LAN clients can communicate over the intended IPv6 path without affecting other interfaces.

### M5 — GRE IPv6 egress gateway

**Status: IPV6 UNDERLAY AND PUBLIC EGRESS OBSERVED; RETURN ROUTES AND NAT66 NOT DEPLOYED/VERIFIED.**
**Priority: P0 for IPv6 goal.**

- [x] Confirm via operator output that the gateway has IPv6 forwarding, working IPv6 default route, and GRE IPv6 peer reachability.
- [x] Confirm that RA-based default route remains usable when WAN forwarding is enabled (effective `accept_ra` as applicable).
- [ ] Verify current WAN IPv6, gateway interface, and GRE peer at deployment time; compare with host-local JSON.
- [ ] Choose public routed-prefix routing if available; otherwise configure SNAT66 for only the assigned ULA /128 and requested LAN /64.
- [ ] Install source-specific IPv6 FORWARD and conntrack return rules without overriding security policy or Docker-managed chains.
- [ ] Install return routes to ingress GRE peer for every enabled ULA prefix.
- [ ] Verify conntrack reply path and SNAT address persistence when WAN IPv6 changes.
- [ ] Provide systemd-native persistence ordered after actual network/GRE readiness; avoid blind `ip6tables-save` of whole host.
- [ ] Ensure IPv6 PMTUD and required ICMPv6 message types are not dropped.
- [ ] Test route behavior under GRE down, WAN IPv6 down, gateway reboot and ingress reboot.
- [ ] Validate that any IPv6 service on the gateway itself is unaffected.

**Gate:** source from actual selected router reaches IPv6 Internet and replies return through GRE; no unselected client is SNATed or rerouted.

### M6 — IPv4 GRE return path and client routing isolation

**Status: INGRESS FORWARDED-PATH PBR OBSERVED; COMPLETE END-TO-END VALIDATION PENDING.**
**Priority: P1.**

- [x] Confirm selected client PBR routes forwarded IPv4 packets into the GRE interface with an `iif`-aware lookup.
- [x] Observe dedicated IPv4 policy table with GRE route and unreachable fallback, and enabled policy service.
- [ ] Confirm egress gateway supports IPv4 source routing, NAT (when required) and reverse route for the selected private peer.
- [ ] Verify actual Internet IPv4 exit address from the chosen RouterOS source, not from the Linux hosts.
- [ ] Test GRE failure and recovery, cold boot, concurrent PPP reconnect and other-user traffic isolation.
- [ ] Harden the ingress policy service for idempotence, table/rule collision, route changes and explicit deprovisioning.
- [ ] Document IP version separation: IPv4 PBR never automatically carries IPv6 traffic.

**Gate:** the selected IPv4 client routes through GRE by design and no other client changes route.

### M7 — Persistence, deployment and upgrade safety

**Status: SOME EXISTING PERSISTENCE OBSERVED; FULL RELEASE PROCESS NOT COMPLETE.**
**Priority: P0 before production rollout.**

- [x] Observe that ingress `netfilter-persistent` was enabled and contained PPP-scoped TCPMSS rules.
- [x] Observe operator-supplied persistent sysctl settings for IPv4/IPv6 forwarding on ingress.
- [x] Observe ingress PBR service enabled and active at the time of testing.
- [ ] Verify effective persistence of all settings after a controlled reboot/PPP reconnect; do not treat enabled unit alone as proof.
- [ ] Eliminate full-host firewall restore from unrelated service start paths (M2).
- [ ] Define immutable or pinned release checkout, configuration directory, permissions, backup snapshot, and maintenance rollout; do not run production services directly from a casually switched Git worktree.
- [ ] Add safe preflight, validate-only/dry-run, dependency ordering and post-start health checks.
- [ ] Use atomic update/symlink or similarly reversible deployment pattern; confirm service `ExecStart` before release change.
- [ ] Do not restart `xl2tpd` or manage all socat forwards during a simple doc/code update.
- [ ] Provide reversion for each changed file/route/rule/service without affecting other VPNs or host SSH.
- [ ] Define a staged rollout: lab -> selected client -> repeat reconnect -> service restart -> controlled reboot -> other clients.

**Gate:** all owned resources survive restart/reconnect exactly once; rollback is demonstrated.

### M8 — Latency, loss, fragmentation and throughput engineering

**Status: BASELINE PARTIAL; ROOT CAUSE UNKNOWN.**
**Priority: P1 after forwarding works safely.**

- [x] Observe PPP MTU 1280 in effective interface output and two scoped TCPMSS rules with nonzero match counters.
- [x] Observe nonzero packet loss in short tests on one PPP peer and historical fragmentation failures / retransmissions; these observations do not establish a cause.
- [ ] Measure end-to-end packet loss, jitter, RTT distribution and packet-size thresholds from the actual selected RouterOS source and optional LAN clients.
- [ ] Trace actual outer path: L2TP UDP/IPv4 and IPv6 inside PPP, GRE underlay, public WAN MTU, WARP overlap and any additional encapsulation.
- [ ] Capture SYN MSS/ICMPv6 Packet Too Big with narrow, privacy-preserving filters when troubleshooting PMTU.
- [ ] Compare controlled TCP/UDP throughput, CPU load, qdisc drops and retransmission deltas under comparable conditions; avoid broad packet dumps or secret logging.
- [ ] Do not change global `rp_filter`, `ip_no_pmtu_disc`, qdisc, ECN, offload or congestion-control settings without evidence and a reversible experiment.
- [ ] If performance problems remain, identify whether they arise from transport path, device CPU, provider routing, loss, fragmentation, firewall or NAT before tuning.
- [ ] Establish an SLO appropriate to measured baseline, not a fabricated latency guarantee.

**Gate:** measured data support any proposed optimization; no regression on unselected traffic.

### M9 — Security and maintainability

**Status: PARTIAL; SEVERAL KNOWN HIGH-RISK AREAS.**
**Priority: P0/P1.**

- [ ] Document clearly that base L2TP without IPsec is **unencrypted**; CHAP is authentication, not transport confidentiality.
- [ ] Review whether a secure tunnel/wrapper is required for credentials, router administration or sensitive traffic; do not silently alter the protocol.
- [ ] Constrain management forwards and avoid exposing Winbox/API broadly; make allowlisting and audit logging configurable.
- [ ] Remove password echoing and user database dumping from CLI/status/log paths; protect credential file permissions and backups.
- [ ] Review potentially unsafe `eval` and input sanitization patterns; replace with structured command construction and argument arrays.
- [ ] Review package installation and removal impact, especially package co-ownership with other services.
- [ ] Review scripts for unbounded loops, broad deletion, insecure temporary files, injection, symlink races, and failed-command handling.
- [ ] Clearly scope concurrent user editing and address allocation; avoid race-condition duplicate assignments.
- [ ] Establish minimum supported OS, package and RouterOS versions based on documentation and test matrix rather than blanket promises.

**Gate:** security review and high-impact change safety checklist pass.

### M10 — CI, integration tests and documentation

**Status: BASIC STATIC CI WORKING; ADVANCED TESTS PENDING.**
**Priority: P1 for first stable release.**

- [x] Add shell/Python syntax verification and basic address allocator regression check.
- [x] Add optional IPv6 helper, examples and initial GRE IPv6 deployment documentation.
- [x] Add `AGENTS.md` and this execution roadmap.
- [ ] Add ShellCheck and optional Python static type/lint validation, with reviewed rule suppressions.
- [ ] Add parameterized unit tests for IP-range validation, allocation, network config parser, ULA generator and host role JSON.
- [ ] Add hermetic, privileged Linux network namespace tests for routes/rules/NAT; skip safely if host CI cannot run them.
- [ ] Add mocks for failures, duplicate rules, conflicting prefix/table, premature PPP disconnect and GRE link loss.
- [ ] Test multi-client coexistence, IPv4/IPv6 source isolation, persistence and rollback in an integration environment.
- [ ] Ensure CI cannot access production secrets or apply host network changes.
- [ ] Document two separate scopes: repo setup/development versus per-deployment operations, config, safe rollout and RouterOS client setup.
- [ ] Update README to link AGENTS, PLAN, design, migration guide, security disclaimer, commands and validated compatibility matrix.
- [ ] Publish a versioned change log only after release gates pass.

**Gate:** defined critical tests and signed-off integration checklist pass; documentation matches code as deployed.

## 5. Recommended implementation order

1. **Protect current installation:** freeze automated restarts and identify exactly which deployed files systemd will run; keep active PPP/GRE/SSH available.
2. **Fix M2 service/firewall hazards before any source-code rollout:** whole firewall restore, broad process kills, accidental global forwarding changes and unclear rollback ownership.
3. **Finish M3 with safe test harness:** peer discovery, exact rule ownership, fail-closed behavior, reconnect hooks, and gateway idempotent SNAT.
4. **Complete M4+M5 on a selected client only:** stable ULA assignment, RouterOS route scoped to the intended tunnel, GRE transit, gateway return/NAT, real IPv6 HTTPS egress.
5. **Validate M6 and performance M8** with actual client traffic and underlay MTU analysis.
6. **Address M7 operational persistence** and perform controlled cold-boot/disconnect/reconnect/rollback tests.
7. **Complete M9/M10**, review Draft PR, then request explicit merge/deployment approval; no automatic production updates.

Dependencies:

~~~text
M0 baseline + rollback
    |
    +--> M2 firewall/lifecycle safety -----+
    |                                       |
    +--> M1 configurable addressing        +--> M3 IPv6 helper readiness
                                                |
                                    +-----------+-----------+
                                    |                       |
                                 M4 RouterOS            M5 GRE egress
                                    |                       |
                                    +-----------+-----------+
                                                |
                                       Real IPv6 egress test
                                                |
                                   M7 persistence / recovery
                                                |
                                 M8 performance + M9 security
                                                |
                                  M10 release gate / approval
~~~

## 6. Field validation matrix

Use actual host observations and validated operator-selected values. The following is a test specification, not a command to apply to any known host.

| Scenario | Expected outcome | Failure / rollback trigger |
|---|---|---|
| L2TP selected client connects | PPP address exactly matches reserved IPv4 peer; negotiated MTU 1280 and IPv6CP | Peer mismatch, duplicate peer, no IPv6CP |
| A second L2TP user connects | Independent PPP session, unchanged routes and management forwards | Wrong interface selection, other-user egress change |
| Client IPv4 route lookup (forwarded) | Dedicated GRE table chosen based on source and real incoming PPP interface | Uses main/WARP/other client route |
| Client IPv6 source lookup | Dedicated IPv6 GRE table; no fallback to host WAN | Inadvertent ingress public WAN egress |
| GRE IPv6 ping between Linux peers | Reachability and bounded latency; investigate failed probes | No route/reply, underlay MTU |
| Gateway IPv6 NAT / reverse | Only configured ULA flows mapped to verified public source | Missing return route, unexpected NAT scope |
| Real RouterOS IPv6 ping/HTTPS | IPv6 Internet works from configured router source | ICMP succeeds but HTTPS fails, path too big |
| LAN IPv6 (if enabled) | LAN /64 advertised only on intended interface, no other LAN altered | RA leakage or wrong interface |
| GRE failure | Selected client's traffic fails closed, others remain functional | Any traffic leakage through host WAN |
| Session reconnect / PPP rename | Routes attach to new matching client, old routes removed | Stale route or wrong PPP selected |
| Firewall restart / Docker restart | Exact project rules remain, Docker-managed rules do not disappear | Flushed/replaced unrelated chains |
| Gateway WAN RA change | Public IPv6 default remains reachable with forwarding | RA route loss, stale public IPv6 SNAT |
| Service restart and controlled reboot | All intended settings recover without duplicates | Missing route/NAT or lost access |
| Rollback | Only new rules/routes/services removed; unrelated services healthy | SSH/other VPN interruption |
| Network performance | RTT/loss/throughput measured versus baseline | Regressions, repeatable drops or PMTU blackholes |

## 7. Rollback and failure playbook

1. Stop **further rollout**, not every networking service, when a critical test fails.
2. Preserve read-only diagnostic evidence: current `ip -4/-6 rule`, exact policy tables, interface/PPP peer mapping, route lookups, netfilter rule counters, relevant service unit state and logs. Redact credentials.
3. If IPv6 egress fails, remove only the newly added RouterOS IPv6 route/address and exact gateway NAT/forward/return-route entries. Preserve established IPv4 L2TP and GRE.
4. On ingress, remove only the helper-owned client route when that client disconnects; retain fail-closed source policy until intentional deprovisioning, then verify and remove it separately.
5. If a source deployment is implicated, return the service to its previously verified release path/commit and perform a targeted service action if authorized; never flush host firewalls or reboot without an explicit recovery plan.
6. Revalidate SSH, every existing PPP client, WARP, Docker and GRE before declaring restoration complete.
7. Document failure cause as **hypothesis** until reproduced and correlated with evidence.

There is no universal, context-free rollback script that can safely delete live networking state across all hosts; resource ownership and current commands must be validated before deletion.

## 8. Unresolved design decisions (record choices before deploying)

- **Public IPv6 strategy:** delegated/routed IPv6 versus private ULA plus scoped NAT66.
- **Client scope:** router-only IPv6 /128 or router plus LAN /64.
- **RouterOS routing:** dedicated IPv6 policy/table for selected source versus intentional router-wide default; interplay with existing upstreams.
- **Peer association:** route keyed by PPP peer IPv4, account identity or another verified authenticated identifier; handling temporary IPv4 reassignment.
- **GRE down/fail-closed behavior:** source policy activation before interface exists, reconciliation while disconnected, and no bypass to other WAN/WARP routes.
- **Firewall ownership:** nftables-native rules, iptables-nft compatibility, or distribution-specific firewall manager; do not operate multiple unsynchronized sources of truth.
- **Gateway SNAT public IPv6:** fixed validated address versus dynamic discovery/refresh when provider changes it.
- **Client scaling:** one selected client vs multiple concurrent source-specific clients and LAN prefixes.
- **Encrypted transport:** continue plain L2TP for isolated trusted infrastructure only or add a secure encapsulation option.
- **Supported versions:** validated Ubuntu/Debian releases, xl2tpd/pppd, kernel/netfilter versions, MikroTik RouterOS 7 variants and architecture/resource limits.
- **Deployment model:** root-owned immutable versioned checkout and service units versus packaged installation.
- **Performance targets:** measurable baselines and bandwidth/latency acceptance thresholds defined by deployment.

## 9. Release checklist (must all be true)

- [ ] Critical M2 and M3 safety tasks complete, reviewed and tested.
- [ ] Source has no site-specific topology/IP/credential values, except clearly identified application defaults and documentation/test-only ranges.
- [ ] IPv4 pool/installer safe against existing installations and out-of-range input.
- [ ] Multi-client PPP session isolation, reconnect and IPv6 link-local negotiation tested.
- [ ] Public IPv6 connectivity proven from **actual RouterOS source** across PPP, GRE and gateway; return routing and NAT verified.
- [ ] IPv4 PBR verified independently; unrelated WAN/VPN routes unchanged.
- [ ] PPP MTU 1280, IPv6 PMTU/ICMPv6, TCP MSS and measured loss behavior validated.
- [ ] Gateway IPv6 forwarding, WAN RA/default route and firewall state preserved.
- [ ] Runtime persistence tested after service restart and reboot with no duplicate owned rules.
- [ ] SSH/management access and unrelated Docker/WARP/GRE/PPP verified healthy.
- [ ] Exact rollback performed and verified at least once in staging.
- [ ] CI checks + negative/unit/integration tests pass for the release commit.
- [ ] Security limitations documented and credentials protected.
- [ ] Draft PR reviewed, then explicitly approved for merge. Production deployment separately authorized and validated.

**Final status criterion:** repository completion, host deployment, and client IPv6 Internet reachability are three separate milestones. Never mark the entire project COMPLETE from a successful source commit or a successful GRE peer ping alone.


## 10. New findings and implementation, 2026-11-10

**Observed:** selected PPP client has a functioning link to the L2TP
ingress, but selected-client IPv4 public destinations timed out while a
different existing PPP client reached those destinations. Previously the
selected client's IPv6 route via GRE/WAN SNAT was independently verified.

**Inference, not confirmed cause:** IPv4 return routing, NAT44 and/or
forward policy on the GRE egress gateway may be missing or routing via
an unintended WAN/WARP table. The two previously installed l2tp6
persistence scripts manage IPv6 only; neither fixes this IPv4 issue.

### Repository additions

- [x] Add opt-in client-scoped `tools/ipv4-gre-egress.py` for IPv4 GRE
  return /32, NAT44 and stateful forwarding on the egress host only.
- [x] Fail safely if the verified forwarded source route does not choose
  the configured WAN; do not rewrite global default routes or WARP.
- [x] Add dedicated optional systemd oneshot+timer installer for IPv4
  reconciliation after tested application.
- [x] Add a root-owned global security policy schema and per-user
  `plaintext` / `ipsec-required` **metadata validation**.
- [x] Document why IPsec selection cannot be safely enforced by PPP
  username on one shared L2TP listener.
- [x] Add unit checks for listener separation, security-policy consistency,
  and narrow GRE IPv4 rule scope; mask stored passwords in list-users.

### Still NOT done

- [ ] Obtain current Warden read-only IPv4 `ip rule` / `ip route get ...
  iif gre` / `iptables -t nat` / `rp_filter` / reverse-route evidence
  before declaring a root cause or changing any host.
- [ ] Verify that the egress helper is conflict-safe with real Warden
  Docker/WARP/nft and is idempotent under reconnect and reboot.
- [ ] Test actual selected MikroTik client IPv4 to Internet after
  applying the smallest corrected gateway route/NAT scope.
- [ ] Deploy/validate persistence on live hosts only with approved
  rollback and clean baseline. Nothing in this repository is auto-deployed.
- [ ] Implement and test actual IPsec-enforced isolated L2TP endpoints
  with separate credential visibility and plaintext-denial policy.
- [ ] Verify protected accounts CANNOT authenticate on the plaintext
  listener; review IKE/ESP compatibility and multiple clients behind NAT.
- [ ] Add runtime enforcement status to per-user management UI only
  after authoritative XFRM/SA and listener checks exist.
- [ ] Audit other code that still prints passwords outside list-users.

**Security gate:** per-user IPsec policy validation is NOT equivalent to
IPsec protection. Do not enable or advertise per-user IPsec until an
enforcement path passes negative plaintext-bypass tests.


## 11. Selective iPhone IKEv2 implementation track

- [x] Verify Apple's native IKEv2 authentication support and strongSwan
  iOS interoperability requirements.
- [x] Document a separately authenticated iPhone IKEv2/IPsec backend,
  avoiding modifications to existing MikroTik L2TP sessions.
- [ ] Audit real IKEv2/strongSwan package state, UDP 500/4500 ownership,
  certificate identity/SAN, public DNS, firewall/XFRM and route policies.
- [ ] Decide whether iPhone VPN traffic exits at ingress or the remote
  GRE gateway; assign a **distinct**, conflict-checked virtual-IP pool.
- [ ] Implement a validated, host-neutral IKEv2 profile and secret backend;
  test IKEv2 EAP-MSCHAPv2 and/or EAP-TLS on real iOS.
- [ ] Link global user policy to the relevant IKEv2 credential backend
  and, when 'IPsec-required' is intended, **disable that account's plaintext
  L2TP authentication** to prevent downgrade.
- [ ] Prove user revoke, invalid user rejection, no plaintext bypass,
  no address collision, no WARP/GRE leaks, IPv4/IPv6 return routing,
  and unaffected existing sessions.
- [ ] Productionize with targeted firewall rules, versioned secure config,
  no global service restart and tested rollback.

See `docs/iphone-ikev2.md`. The current `tools/ipsec-policy.py` only
records L2TP endpoint policy intent; it is **not yet integrated with
strongSwan** and should not be presented as operational iPhone IKEv2 support.


## 12. Non-GRE user requirement: mandatory IPv4 + IPv6 via ingress

**New scope requirement:** all ordinary L2TP users and all native
iPhone IKEv2 clients have **both** IPv4 and IPv6 routed directly out
the ingress server. Only explicitly opted-in GRE L2TP clients continue
to use the remote GRE gateway in both address families.

- [x] Add documented service-class matrix and source/prefix isolation
  design under `docs/direct-dualstack.md`.
- [ ] Verify usable ingress IPv4/IPv6 WAN routes, configured global
  IPv6 addresses and available **routed** client prefix or scoped
  ULA+NAT66 fallback.
- [ ] Select separate, collision-checked ULA allocations for ordinary
  L2TP clients versus iPhone IKEv2 clients versus existing GRE peers.
- [ ] Implement persistent per-L2TP-client IPv6 /128 assignment,
  dynamically discovered PPP device return route, optional per-LAN
  /64 route, on-client source selection and direct-WAN scoped egress.
- [ ] Implement strongSwan IKEv2 server with **two address pools**
  (IPv4 and IPv6), full-tunnel dual-family selectors, certificates,
  individual accounts, and direct-WAN egress policies and scoped NAT.
- [ ] Verify strongSwan iOS compatibility: server certificate SAN,
  send_cert=always, EAP-MSCHAPv2/EAP-TLS, IPv6 local_ts including ::/0.
- [ ] Implement per-client profile source-policy isolation:
  direct L2TP -> ingress both, iPhone -> ingress both,
  selected GRE -> GRE gateway both.
- [ ] Prove real IPv4 and IPv6 HTTPS exit addresses **from each client
  class**; do not infer success from a working server WAN.
- [ ] Test IPv6 PMTU, WARP policy interactions, reconnect/reboot and
  exact rollback; preserve SSH, Docker, existing PPP/GRE, NAT and
  port forwarding.

**Not yet deployed:** direct IPv6 addressing for ordinary L2TP,
strongSwan IKEv2 or dual-stack iPhone client pools. Do not mark these
requirements complete or give a live iPhone username/password command
until IKEv2 credentials and runtime service are provisioned and tested.


## Android/iPhone portable profile milestone — 2026-11-13

- [x] Implement **password-free iPhone .mobileconfig** generator for
  Apple-managed IKEv2, server DNS/certificate identity and EAP user.
- [x] Implement **password-free Android .sswan** generator for strongSwan
  VPN Client, individual EAP user and dual-family full-tunnel leak blocks.
- [x] Validate identities against the existing private IKEv2 user
  registry, use root-owned output directory and prevent overwrites.
- [x] Add unit tests verifying XML/JSON syntax, no embedded password,
  no L2TP/IPsec global PSK and intended both-family profile settings.
- [x] Document exact mobile import and server prerequisites in
  [docs/mobile-profiles.md](docs/mobile-profiles.md).
- [ ] Audit/obtain public DNS and trusted server cert, and validate
  non-overlapping real iPhone/Android IPv4/IPv6 VIP pools.
- [ ] Deploy actual strongSwan IKEv2 service and root-only EAP users
  with approved firewall/XFRM/NAT/routing, not from unreviewed auto-run.
- [ ] Produce real device-user profile files from verified host config
  and activate them only after IKE/CHILD SA validation.
- [ ] Validate Android and iPhone IPv4+IPv6 HTTPS public Polaris
  egress, Wi-Fi/mobile transitions, invalid user rejection,
  live account revocation, reconnect, reboot, rollback and L2TP
  regression.
- [ ] Integrate optional Global L2TP/IPsec PSK with a separate
  enforced listener if required; this is NOT required for IKEv2/EAP.

**Scope note:** source-level generators are finished; operational mobile
VPN provision, server security and actual client acceptance are NOT.


## Simple IP-only L2TP/IPsec PSK request — 2026-11-13

- [x] Verify iOS L2TP/IPsec PSK supports an IP address rather than DNS/certificate.
- [x] Identify modern Android 12+ native L2TP client removal and
  separate IKEv2/IPsec PSK compatibility requirements.
- [x] Add candidate-only `tools/l2tp-ipsec-psk.py` to use
  the existing secure random on-host global PSK; never print secret.
- [x] Add pure tests and [operator runbook](docs/ip-only-l2tp-ipsec.md).
- [ ] Audit installed charon version, Ubuntu packages, UDP 500/4500,
  source IP, existing plaintext 1701 and XFRM Netfilter policy.
- [ ] Install strongSwan safely and load validated IP-only IKEv1
  transport PSK connection; confirm iPhone native L2TP connection,
  matching IKE/CHILD SA and PPP username.
- [ ] Verify no plaintext downgrade for any account that is
  explicitly required to use IPsec, without breaking current
  MikroTik plaintext users. Do not claim 'IPsec required' yet.
- [ ] Add independent IP-only IKEv2/IPsec PSK server and mobile
  candidate for modern Android, with separate IPv4/IPv6 pools;
  do not pretend Android's IKEv2 mode is L2TP.
- [ ] Confirm real IPv4/IPv6 public Polaris egress on mobile,
  reconnect, NAT-T concurrency and reboot/rollback before release.

**Current PSK is a generated private random secret**, NOT the literal
user-proposed short label. Do not put fixed/predictable PSK into Git.


## Current focus: Phase 1 mobile IPsec client testing & stable production gate (2026-11-14)

**Verified from latest operator console:** strongSwan 5.9.13 installed,
`strongswan.service` running but disabled from boot at last successful
trial; `swanctl --list-conns` displays `mobile-l2tp-psk` with an IKEv1
transport child; UDP 500/4500 bound by charon, UDP 1701 by xl2tpd;
`xl2tpd`/`l2tp-direct6.timer` active. The **global PSK** is protected
root-only and the connection's secret was loaded without being shown.
No client-side protected authentication or Internet test observed yet.

**Already source-implemented:** `tools/l2tp-ipsec-psk.py` candidate
renderer, mobile IKEv2-EAP profile formats, unit tests, and a
read-only phase-one audit. See:
[Phase 1 client and stability gates](docs/PHASE-1-CLIENT-STABILITY.md).

### P0: Phase 1 — connection validation before production

- [x] Source: generate an isolated IKEv1 L2TP/IPsec PSK config for
  the existing Linux host; PSK is a strong generated secret, not a
  public project name or embedded username password.
- [x] Host: install strongSwan 5.9.13 with swanctl and successfully
  load `mobile-l2tp-psk`. Keep existing L2TP/IPv6 services active.
- [x] Source: add a read-only audit with negative tests and no PSK
  output. **Not yet executed on Polaris**.
- [ ] Prove real **iPhone** IKEv1 SA, protected transport CHILD_SA,
  simultaneous PPP session and IPv4 HTTPS egress from Polaris.
- [ ] Measure native iPhone L2TP IPv6 support (do not assume a
  dual-stack pass) and document IPv4-only behavior if observed.
- [ ] Verify selected existing direct and GRE L2TP paths, active
  forwards and remote administration remain unaffected.
- [ ] Reconnect and test multi-client NAT-T concurrency, rejected
  wrong PSK/PPP password, route/MTU and reconnection after roaming.
- [ ] Validate startup order/restart/reboot/recovery/rollback, then
  enable strongSwan persistence **only** after approval.
- [ ] Determine the independent protocol path for **Android**:
  vendor L2TP capability or dedicated IKEv2 backend (EAP/PSK
  depending tested Android client). Do not label current Android
  EAP profile as an active VPN.
- [ ] Test actual modem/router firmware and supported transport
  before generating configuration; no universal profile assumption.
- [ ] For truly `ipsec-required` accounts, implement isolated
  protected listener and prove rejection over plaintext L2TP.
- [ ] Produce concise pass/fail evidence for each device, protocol,
  IPv4+IPv6 route, service and rollback criterion.

### P1: Phase 2 — account and per-device profile generator (design only)

- [ ] Define CLI accepting client display name and platform
  `iphone | android | modem | router | all`, with automatic
  protocol capability validation and fail-closed unknown devices.
- [ ] Create actual PPP or IKEv2 user only after allocating a
  collision-free address and validating server authentication scope.
- [ ] Create compatible per-device files with no plaintext global
  secrets by default; require optional secure transfer for
  applicable PSK/PPP credentials.
- [ ] Unit/integration tests for reruns, concurrent requests,
  credential rotation, user disable, rollback and route persistence.

### P2: Phase 3 — HTTPS self-service + one-time onboarding (design only)

- [ ] Build a non-root dashboard with own-user login/session,
  own-device compatibility view, account status, profile download
  and revocation; no cross-account disclosure.
- [ ] Operator creates a random one-use invitation URL with
  token hash at rest, bounded expiry, scoped account rights,
  throttling and atomic consume during username/password signup.
- [ ] Create real account transactionally from chosen credentials
  with audited privileged helper and no arbitrary host command input.
- [ ] Redirect successfully enrolled user to authenticated
  personal dashboard; provide individually revocable subscription
  URL separate from the **consumed one-time invitation**.
- [ ] Security review: TLS, CSRF, cookies, rate limits, abuse,
  token leakage, profile caching, per-user authorization, audit
  redaction, backups and disaster recovery.
- [ ] Performance/load tests suitable for a small VPN VPS.

Full design contract:
[Future self-service and subscription architecture](docs/FUTURE-SELF-SERVICE.md).

**Release statement:** completion of source tasks is not proof of
live protected mobile access or a stable service. The Phase 2/3
features are intentional future work, not represented as deployed.

**Branch consolidation as observed before this work:** `main` and
`feature/configurable-l2tp-network` are already ancestors of
`development` (no commits missing); new Phase-1 source is proposed
through a dedicated PR into development without rewriting main.


## Phase 1 — Shared PSK / PPP user-management clarification (2026-11-14)

- [x] Add root-only per-user **PSK offered** distribution metadata;
  it is neither access control nor per-user IKE authentication.
- [x] Integrate menu add/edit/list with default secret redaction
  and explicit single-account, terminal-only credential reveal.
- [x] Add global PSK status, guarded rotation/reload and
  separately confirmed strongSwan/xl2tpd restarts.
- [x] Prevent routine xl2tpd restarts when adding/editing PPP users.
  Protect new passwords with CSPRNG and restrict unsafe static-IP
  edits while GRE/direct6/forward dependencies exist.
- [x] Source syntax/unit tests; these do NOT certify production.
- [ ] Execute real iPhone IKEv1+CHILD_SA+PPP+IPv4 Internet test.
- [ ] Verify actual Polaris authentication updates and all existing
  PPP/GRE/WARP/Docker/forward routes without regressions.
- [ ] Test the global PSK rotation/rollback during a scheduled
  maintenance window, not while production users are active.
- [ ] Prove reconnect, multi-client NAT-T and reboot recovery.
- [ ] If per-user IPsec-only is later required, build an isolated
  endpoint and demonstrate plaintext login rejection.
- [ ] Only after acceptance publish a stable Phase-1 release.

Full runbook: [PSK account management](docs/PHASE1-PSK-USERS.md).
Source code and CI green are not evidence of deployed, tested VPN.
