# Shared L2TP/IPsec PSK account presentation — Phase 1 (development)

## Scope and security truth

The previously observed Polaris setup runs **one IKEv1/PSK L2TP
server connection** (`mobile-l2tp-psk`). It uses ONE **global** PSK from
`/etc/l2tp-manager/global-psk.secrets`. PPP usernames/passwords
live separately in `/etc/ppp/chap-secrets`.

**A user flag is NOT an IPsec authentication or authorization policy.**
Marking a user "offer shared PSK" **only** controls whether the manager
offers the common PSK in that user's copy-ready profile. It cannot
prevent that user from trying plaintext L2TP and does not create an
independent per-user IKE PSK. Anyone who already knows the global PSK
could still attempt IKE authentication, subject to PPP credentials.

For accounts that MUST use encryption, use a separately isolated
IPsec-only L2TP endpoint and negative authentication tests. See
[selective IPsec](ipsec-selective.md).

Current Android strongSwan VPN Client supports IKEv2, **not**
iPhone's IKEv1/L2TP PSK mode; this Phase-1 feature is not an
Android-IKEv2 user registry.

## New code (source, NOT automatically deployed)

- `tools/psk-client-manager.py`: metadata, secret-safe listing, exact
  one-user copy-ready display with interactive secret confirmation,
  globally shared PSK status and guarded rotation.
- `lib/psk-menu.sh`: interactive PSK profile preference, global
  status/reveal/rotation, dedicated credential reload, explicitly
  confirmed IPsec or L2TP service restart.
- `lib/users.sh`: menu actions 4, 6 and 7 integrate PSK preference,
  no routine `xl2tpd` restart for addition/edit and no default
  display of users' passwords.
- `lib/core.sh`: new passwords use CSPRNG and 12–64 character
  restricted no-whitespace PPP-compatible alphabet.
- `tests/test_psk_client_manager.py`: negative parsing, metadata,
  sensitive output access and shared-key formatting tests.

## Interactive workflow

With an *approved* separate checkout and only after verifying that
the exact code is suitable for the intended host, launch:

~~~sh
sudo bash l2tp-manager.sh
~~~

Use:
- **4 Add:** create a new PPP username/password and collision-free
  IPv4 from the configured pool. Choose whether to offer the shared
  PSK profile. No daemon restart is performed by the new add code.
- **6 Edit:** choose an existing username, optionally change PPP
  password and choose whether to offer the PSK. Existing static IP
  address editing is deliberately disabled for Phase 1, because
  GRE/IPv6 routing and forwards may reference that address.
- **7 List:** show accounts, private IP, port forwards, and whether
  common PSK info is offered. Enter one username for copy-ready
  details. Secrets appear only after typing `REVEAL` on a TTY.
  Both plaintext-only and PSK-offered accounts can be viewed; only
  offered accounts' display includes the common PSK.
- **15 Global PSK Settings:** view status, reveal to the trusted
  terminal, rotate the one global key (high impact), reload IPsec
  credentials or explicitly confirm restart of IPsec/L2TP.

No PSK or PPP password is printed by default. Never paste revealed
credentials into GitHub, chat, terminal logs, support screenshots or
URLs. Use private, controlled transfer to the intended client.

Equivalent root-only CLI operations (read-only except set/rotation):

~~~sh
sudo python3 tools/psk-client-manager.py list
sudo python3 tools/psk-client-manager.py global-status
sudo python3 tools/psk-client-manager.py status --username myiphone
~~~

`myiphone` is an already verified PPP account name from previous
operator evidence, **not** the separate EAP IKEv2 registry account
`myphone`. The above list/status commands do not print secrets.

To mark one user as eligible to receive the common PSK details:

~~~sh
sudo python3 tools/psk-client-manager.py set \
  --username myiphone --offered yes
~~~

This writes root-only metadata in
`/etc/l2tp-manager/psk-client-flags.json`. It **does not**
enforce IPsec-only authentication. To unmark use `--offered no`,
which does not revoke an already learned global PSK.

On a private interactive terminal only:

~~~sh
sudo python3 tools/psk-client-manager.py show --username myiphone
~~~

The secret-reveal operation refuses non-interactive or redirected
stdout; the output is intentionally NOT suitable for bulk logging,
clipboard automation, or subscription URLs. The profile's server
IPv4 is printed only if the IP appears in the configured strongSwan
snippet **and** is assigned to this host; otherwise it is marked
`unverified`.

## Global PSK change/synchronization is not a normal user edit

A new shared PSK affects **all** L2TP/IPsec devices holding the old
key, regardless of per-user offer metadata. Rotation is not the same
as editing an individual PPP password or removing a profile flag.

The guarded global rotation:
- Requires an interactive terminal; answer `yes` or `y` to a clear confirmation before typing a new PSK.
- Rejects nonzero or unreadable kernel IPsec SA counts and inactive
  strongSwan; expects root-owned secret and known owned config files.
- Inspects the global and active PSK separately; permits repairing an already-mismatched pair, but refuses unknown/extra strongSwan connections or active IPsec sessions.
- Accepts a manually entered **8–64-character** printable ASCII secret (letters, digits and simple punctuation; no spaces, quotes or backslashes). Pressing Enter generates a random **16-character** secret. Existing manually changed 18-character or original 64-character keys are accepted as migration inputs, including if they differ between global and active files.
- Updates the
  global file and owned active/candidate snippet(s), then requests
  credential reload. On failure tries to restore all changed files
  and previously loaded credentials.
- Shows the *new* common PSK only on the private interactive console;
  all previously enrolled PSK clients must be updated.
- Does NOT restart `xl2tpd`, interrupt existing PPP users automatically,
  fix provider firewall, or prove actual IKEv1 client compatibility.

**Risk:** there is no fully atomic transaction spanning disk files,
the IKE daemon and all remote clients; rollback and live connectivity
must be verified. Only rotate within a controlled maintenance window
after an actual successful client test. Never rotate only to silence
optional plugin warnings.

The global PSK is not a per-user secret. A lost global PSK requires
coordinated rotation of ALL provisioned devices.

## Known remaining Phase-1 blockers and release gates

1. **No real iPhone protected session has been observed:** before
   success, demonstrate IKE_SA+CHILD_SA on UDP 1701, the selected PPP
   username and IPv4 HTTPS egress measured from the phone.
2. Validate actual iOS L2TP security proposals and NAT-T,
   authentication failure behavior and multiple devices behind NAT.
3. Validate PPP credential file syntax and permissions and whether a
   newly added user can authenticate without restarting `xl2tpd`
   on the installed system.
4. Run non-regression checks for existing direct and GRE users,
   IPv4/IPv6 paths, Docker, WARP and forward services.
5. Test rollback, reconnect and boot/reboot persistence before any
   "stable production" tag.
6. Fix separately: plaintext-only/PSK-only *enforcement* cannot be
   accomplished with a boolean user flag on the shared UDP listener.
7. Existing legacy user deletion, full forward management and
   complete migration of static user IPs remain separate reviews.
   Do not claim all project bugs are fixed from source tests alone.
8. In the last host log, strongSwan was loaded but had `IKE_SAs: 0`.
   The IPv4 FIB table-220-not-found message may be normal if that
   table is only used for IPv6; inspect effective IPv4 rules before
   treating it as an error.

### Rollback of this feature's metadata

`psk-client-flags.json` only describes which clients are offered a
copy of the global PSK; it does not affect xl2tpd/strongSwan behavior.
Do not delete it to "revoke" VPN access. Revert code through the
separate checkout; restore `chap-secrets` from its operator-created
backup only with a planned maintenance action. If rotation fails,
check the current effective strongSwan credentials without
printing the PSK and validate real client authentication.

References:
- https://docs.strongswan.org/docs/5.9/swanctl/swanctlConf.html
- https://docs.strongswan.org/docs/latest/swanctl/swanctlLoadCreds.html
- https://docs.strongswan.org/docs/latest/support/faq.html


### Repair the previously observed Polaris mismatch

The operator observed a root-only global PSK of **18 characters** while
the active strongSwan L2TP snippet contains a **different** secret.
The old 64-character-only validator rejects this existing setup; it
does not mean the IKEv1 connection failed or that a user connected.

On a verified, isolated new release checkout:

~~~sh
sudo python3 tools/psk-client-manager.py global-status
sudo python3 tools/psk-client-manager.py global-rotate
sudo python3 tools/psk-client-manager.py global-status
~~~

Or launch the existing interactive L2TP Manager and choose
**15 → 2**. Type `yes` (or `y`) at the initial confirmation prompt, then:
- press **Enter** for a randomly generated 16-character PSK, or
- enter your own 8–64-character printable ASCII secret twice;
  no need to memorize or paste a multi-line Python program.

The manager checks for a zero active IKE/XFRM SA count, backs up
each owned file (0600 in a 0700 directory), writes the chosen PSK to
the global and owned active/candidate snippets, then reloads IKE
credentials with `swanctl --load-creds --clear --noprompt`.
Any failure attempts restoration of old files and credentials.
Do **not** claim that the new secret works on iPhone until one actual
IKE/CHILD SA and PPP/IPv4 end-to-end test passes.

**Critical:** This affects ALL existing clients using the shared PSK.
Changing a user's "PSK offered" setting does not change the key or
revoke old users. Do not disclose the new secret in GitHub, chats,
terminal logs or URLs.
