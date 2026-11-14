# Future roadmap — multi-device profiles, user dashboard and subscription URLs

**Status: DESIGN ONLY. Not implemented, not deployed, not security audited.**
**Priority:** after Phase 1 client transport/PPP connectivity, dual-stack
egress, reboot recovery and regression gates have passed.
Implementation requires independent approval and threat modeling.

## Phase 2A — administrator-controlled account/profile generator

Command-line interface (proposed):

~~~text
vpnctl client create
  -> Enter logical client name
  -> Select platform: iphone | android | modem | router | all
  -> Select an available, actually supported protocol
  -> Select access policy: legacy-plaintext | optional-ipsec | ipsec-required
  -> Validate per-user username, password policy and address allocation
  -> Confirm selected protocol and account scope
  -> Create/reconcile host-local account transactionally
  -> Emit only compatible, per-device configuration profile(s)
  -> Validate server state and provide safe rollback evidence
~~~

Non-negotiable design:
- **No guessed client protocol:** iPhone L2TP/IPsec PSK, modern Android
  strongSwan IKEv2 EAP and routers/modems require distinct configuration.
  `all` produces a capability-checked bundle, not one misleading config.
- Unique app identities, collision-free PPP address assignment,
  independent credentials, strongly authenticated operator role,
  predictable error messages, explicit IPsec/plaintext admission.
- **Do not equate a flag in a database with IPsec enforcement.**
  Protected-only users must not retain valid plaintext authentication.
- No password/PSK in shell arguments, logs, Git, browser query strings
  or world-readable ZIP archives; sensitive bundles encrypted and
  short-lived. Prefer user entry of password on the device.
- Existing `tools/mobile-profiles.py` creates only *inactive*
  Android strongSwan IKEv2-EAP/Apple IKEv2-EAP profiles today.
  Do not reuse those artifacts for legacy L2TP/IPsec without a
  separate format implementation and real import tests.
- Do not assume creating/removing PPP accounts can be done with zero
  `xl2tpd` interruption. Inspect the existing account-manager
  behavior and demonstrate reload/restart effects before automation.
- Audit new accounts against reserved GRE/direct address assignments,
  ports, static routes and 4 existing historical users; do not
  inherit or overwrite existing client routing by accident.

## Phase 2B — end-user HTTPS web portal and dashboard

Requirements:
- A browser user enters **username + password** on a login page,
  with rate limiting, lockout/backoff, secure password hashing,
  optional 2FA, CSRF mitigation, session rotation, HTTP-only
  Secure SameSite cookies, TLS and strict origin validation.
- Each authorized user sees only **their own** subscription link,
  device compatibility, configuration/connection instructions,
  allowed public server endpoint, account status and download
  links. Never disclose another user's account or source IP.
- The dashboard offers supported device-specific files and
  **does not provide secret keys, PSKs, or private authentication
  data in HTML by default**.
- Support user-requested password rotation and device/session
  revocation, with anti-enumeration responses and audit events.
- Exported profile/QR downloads need access-control checks,
  content-type and Content-Disposition restrictions, cache-control:
  no-store, per-download expiry, and intentional device confirmation.
- The web tier must not run as root, must not have direct read
  permission to global secrets or `/etc/ppp/chap-secrets`; use
  a narrowly scoped privileged provisioning helper/socket with
  strict input validation, transaction log, and least privilege.
- Avoid bespoke cryptography and avoid mixing public HTML service
  with the VPN daemon's privileged control plane. Restrict
  firewall, path permissions and dependency footprint.
- Implement bounded DB schema/migrations, backup, restore,
  audit trail, healthchecks and explicit rollback.

## Phase 3 — one-time invitation and subscription design

**Two different token types. Do not confuse them.**

### One-time enrollment invitation

1. An authorized operator generates a cryptographically random
   **single-use invitation URL**, not a username/password URL.
2. Store only a **hash** of the invitation token, with tenant/role,
   issuance time, short absolute expiry, attempt budget,
   operator ID and unused/consumed/revoked state.
3. Token grants only permission to attempt enrollment and choose an
   available username + password. It does **not** grant VPN access.
4. Submission validates input, uniqueness, scope, password strength,
   address collision and server readiness; a single DB transaction
   atomically consumes the token and reserves the account. A failed
   create must not silently orphan an active VPN login.
5. Provisioning is a separate bounded, idempotent privileged action.
   The invitation must not permit arbitrary routes, host commands,
   file paths, policy changes or another user's credentials.
6. A fresh authenticated HTTPS session redirects to the own-user
   dashboard after successful provisioning; duplicate or replayed
   tokens fail with non-enumerating responses. Avoid token leakage
   via Referrer headers, analytics, third-party scripts and access logs.

### Read-only subscription URL

- A *separately minted*, revocable, user-scoped subscription token is
  required if external clients must periodically fetch metadata.
  It is distinct from the consumed invitation and independent of the
  dashboard login cookie.
- Serve a device-specific, **secret-minimized** manifest with verified
  URL schema, format/version, protocol, app instructions and expiration.
  If a profile contains a global machine PSK or PPP password, never
  expose it through a bearer link by default; require an authenticated
  per-user protected reveal/transfer with explicit policy approval.
- Use TLS, token hash at rest, scopes, short expiry/rotation, bounded
  downloads, no third-party redirects, `Cache-Control: no-store`,
  no-cache proxies, `Referrer-Policy: no-referrer`, audit and revocation.
- A single-use invitation cannot simultaneously behave as a durable
  repeatedly polled subscription. Provide a separate scoped token.
- Downloaded profiles must not claim universal compatibility:
  iPhone L2TP, Android IKEv2, modem and router are different.

## Future user stories and acceptance tests

- Admin selects `client name` then `iphone|android|modem|router|all`,
  receives only device-supported profile formats, distinct auth
  identities, non-colliding addresses and a reproducible rollback.
- 100+ concurrent invitations never create duplicate user names,
  reuse consumed tokens, overwrite existing users or reveal global PSK.
- Lost/stolen invitation can be revoked before use; repeated use
  returns denial and cannot reissue credentials.
- A user login cannot enumerate, fetch or alter another user's
  account/profile/secret.
- A stolen subscription link can be revoked independently from the
  user's VPN password, and cannot read other accounts.
- Password rotation, disabling the VPN account and session revocation
  take effect in the real PPP or IKE backend, not just the dashboard.
- Logs, metrics, error responses and monitoring never expose passwords,
  tokens, PSK or private keys.
- Full end-to-end scenario includes VPN authentication, IPsec SA
  binding when required, IPv4/IPv6 egress as genuinely supported,
  reconnect and reboot.
- Performance/resource tests reflect the small Linux VPS baseline;
  do not introduce an unbounded web stack into an existing live router.

## Delivery gates and ownership

- **Now (Phase 1):** only existing Linux VPN stack, client test
  runbook, minimal read-only audit and safe on-host PSK retrieval.
- **Phase 2:** detailed security design + implementation PRs for
  admin CLI and dashboard, unit/integration tests, staging deployment.
- **Phase 3:** private enrollment/subscription API with audited
  credentials and one-time token semantics, load and abuse tests.
- **Never:** commit actual site IPs, project PSK, user passwords or
  live device configs to the public GitHub repository.

References:
- https://support.apple.com/en-ca/guide/security/sec802e8ab55/web
- https://docs.strongswan.org/docs/latest/os/androidVpnClient.html
- https://docs.strongswan.org/docs/latest/swanctl/swanctlConf.html
