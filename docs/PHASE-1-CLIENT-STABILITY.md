# Phase 1 — IPsec/L2TP client compatibility and stable rollout

**Evidence cutoff:** user-provided Polaris console, 2026-11-14.
**Scope:** test, isolate failures and make an approved service stable.
**Not scope:** subscription tokens, web dashboard, bulk account enrollment,
per-user IPsec-only claims, full cross-platform provisioning.

## Verified deployed state

- Ubuntu 24.04; strongSwan 5.9.13 `charon-systemd` and `swanctl` installed.
- A protected local IKEv1 PSK `mobile-l2tp-psk` / `l2tp-transport`
  connection **was observed in `swanctl --list-conns`** after copying
  the generated candidate into an owned `conf.d` snippet.
- UDP 500/4500 have charon listeners; UDP 1701 remains owned by xl2tpd.
- The last observed `strongswan.service` is **running but disabled**;
  `xl2tpd` and `l2tp-direct6.timer` are active.
- No observed successful phone IKE_SA, CHILD_SA, PPP session for
  `myiphone` or HTTPS public-egress test; **not production stable**.
- Existing PPP user `myiphone` was listed with an assigned IPv4 peer;
  this is distinct from the offline IKEv2 EAP-only user `myphone`.
- No proof that plaintext L2TP is blocked for selected accounts;
  keep all existing users' access and do not claim per-user enforcement.

## Client decision matrix

| Type | Candidate protocol | Export/import now | Required live acceptance |
|---|---|---|---|
| iPhone/iPad | Native **L2TP/IPsec IKEv1 PSK** using existing public IP | Manual settings now; later support unsigned/signed Apple profile on explicit opt-in | IKEv1 SA + protected L2TP + PPP + IPv4, IPv6 if supported by the actual device |
| Android with vendor legacy L2TP option | L2TP/IPsec PSK only if device explicitly supports it | Manual; never assume across Android versions | Same evidence as iPhone |
| Modern Android using strongSwan VPN Client | **IKEv2**, not L2TP/IKEv1 | Existing `.sswan` generator targets IKEv2 EAP but **backend is not deployed** | Separate IKEv2 server, authentic user, both-family VIPs and egress |
| Modem | Vendor/firmware-specific L2TP/IPsec; perhaps unsupported | Generate vendor instructions only after detecting supported features | Tunnel stability and client routes verified |
| Router | Vendor/firmware-specific PPP/L2TP/IPsec or IKEv2 | No single universal profile; preserve existing GRE/WARP/client tunnels | NAT-T, reconnect, MTU, policy and return path |
| All | Catalog that selects protocol per client | **NOT** a single file, PSK, or protocol automatically usable everywhere | Each distinct device/protocol passes its own tests |

Apple officially supports native L2TP/IPsec password + pre-shared secret:
https://support.apple.com/en-ca/guide/security/sec802e8ab55/web

Apple accepts IP address or FQDN as L2TP server:
https://support.apple.com/en-ae/guide/deployment/dep73d1b38bc/web

The official Android strongSwan app supports only IKEv2:
https://docs.strongswan.org/docs/latest/os/androidVpnClient.html

## Retrieve the existing global IPsec secret on a trusted terminal

`/etc/l2tp-manager/global-psk.secrets` has already been audited as
root-owned 0600 and contains the generated global key; **the key is NOT
the individual PPP password**. Display it only on a physically trusted
terminal, do not paste its output into chats, browser URLs or logs:

~~~sh
(
  sudo sed -n 's/^: PSK "\([^"]*\)"$/\1/p' \
    /etc/l2tp-manager/global-psk.secrets
)
~~~

The private key inside quotes is entered as the **Secret** in the iPhone
native L2TP VPN settings. Users also enter their own PPP account and
PPP password. Do NOT rotate the global PSK during this test: doing so
would invalidate the staged connection and other already enrolled users.

## Phase-one acceptance procedure

### Gate A: server baseline (before a test)

1. Verify the expected strongSwan connection is loaded, not merely
   that the daemon and port listeners exist.
2. Verify `xl2tpd` is active and both direct and GRE client sessions/
   routes remain unchanged. Save scoped rules, route and service
   evidence **without dumping xfrm keys or PPP secrets**.
3. Use the bundled read-only script from the approved separate checkout:

~~~sh
(
  read -r -p 'Absolute path to checked-out L2TP-Manager: ' source
  [ -f "$source/tools/ipsec-phase1-audit.py" ] || exit 1
  sudo python3 "$source/tools/ipsec-phase1-audit.py"
)
~~~

Never run a `git switch` in the directory used by live production
services. Check out `development` in the separate worktree first.

### Gate B: one iPhone pilot

1. Enter VPN type **L2TP** using verified Polaris public IP, a valid
   **PPP** username/password and the **global machine PSK**.
2. Start the phone VPN while observing auth failures and SAs:
   `sudo swanctl --list-sas` and a short bounded
   `sudo journalctl -u strongswan.service -n 50 --no-pager`. Protect
   private source IPs in any shared logs; never share private keys.
3. Correlate established **IKE SA + CHILD SA + matched PPP peer**
   for the selected user. A nonzero global XFRM SAD count alone is
   not proof that the selected username is protected.
4. Verify HTTPS IPv4 public address **on the phone**, and compare to
   verified Polaris egress. Test IPv6 if the phone really negotiates
   it; mark unsupported/unknown instead of faking a dual-stack pass.
5. Test Wi-Fi↔cellular switching, reconnect, incorrect PPP password,
   incorrect PSK, multiple devices behind NAT and repeated login.

### Gate C: non-regression

- Existing ordinary L2TP client with directly routed IPv4/IPv6
  remains reachable; selected GRE/Warden client stays on its own
  source policy, regardless of current dynamic `pppN` interface.
- No interruption of SSH, Docker, WARP, port forwarding, DNS or
  selected live users; capture precise delta and rollback trigger.
- Confirm firewall provider path for UDP 500/4500 and **no
  unintentional IPsec-only authentication guarantee** on shared 1701.

### Gate D: persistence and rollback

- No boot enable until Gates A-C pass for at least one real client.
- Record verified file ownership, include path, active service unit,
  intended startup order, service enabled state, power-cycle window,
  VPN reconnect and access to an out-of-band management console.
- On failure, stop only `strongswan.service` (after confirming this
  host's separate IPsec use); do not restart or remove xl2tpd, PPP
  peers or Docker and never flush global firewall chains.
- Stage reversible backups of project-owned config before enabling
  service at boot; confirm restored baseline after rollback.
- Document at least one successful reboot test before marking
  persistence verified.

## Interpreting observed strongSwan warnings

Plugin “failed to load” warnings for optional plugin names are not by
themselves proof of a failed connection. In the live client trial
diagnose actual IKE proposal matching, PSK auth, NAT-T, ESP/transport
selectors, PPP auth and network connectivity.

The `swanctl --list-conns` output used `dynamic[udp/l2f]`: `l2f`
is a service-name presentation of UDP port 1701, not evidence of
a wrong configured port. The observed config was loaded; real phone
auth/traffic is still unverified.

## Explicitly deferred items

- Enforcing "IPsec required" by PPP username on the same plaintext
  listener. Requires isolated endpoints/auth policy with negative
  downgrade tests. Existing policy tool is metadata only.
- Modern Android IKEv2 PSK/EAP service deployment, valid strongSwan
  proposals and client app compatibility. `.sswan` generator exists
  for **EAP** but no live backend is evidenced.
- User-chosen names, generated device profiles for modem/router/all,
  self-service provisioning, dashboard, invitation links and
  subscription URLs. See [future portal architecture](FUTURE-SELF-SERVICE.md).
