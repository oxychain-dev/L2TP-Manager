# IP-address L2TP/IPsec PSK for iPhone — staged rollout

## Objective: simple phone settings

Use the **existing Polaris public IPv4** as the server address,
the client's normal PPP username/password, and ONE machine-wide
IPsec pre-shared key. **No DNS name and no X.509 certificate
required for this legacy L2TP/IPsec PSK profile.**

Important: the machine PSK is **not** the individual PPP password.
The existing root-only key created by `tools/global-psk.py` is a
random 64-character secret. It is **not** the literal word
`oxychanin`; the latter is too short/predictable to use as a
network-exposed shared secret. Do not change the PSK to a public
project name or copy the key into this repository. Users enter the
actual provisioned private PSK in their device.

## Device support

| Client OS | IP-address L2TP/IPsec PSK |
|---|---|
| iPhone (supported iOS) | Native VPN type `L2TP`, supported by Apple |
| Android 11 or some older/vendor versions | If `L2TP/IPsec PSK` is available in system VPN settings |
| Android 12/13/14+ commonly | Native L2TP support removed. **Do not call IKEv2 PSK L2TP.** Use separate IKEv2/IPsec PSK endpoint/profile instead |

Official Apple: https://support.apple.com/en-ca/guide/security/sec802e8ab55/web

Android version compatibility reports:
https://www.watchguard.com/help/docs/help-center/en-US/Content/en-US/Fireware/mvpn/l2tp/l2tp_vpn_client_android.html

## Simple iPhone setup (AFTER server IPsec is deployed)

1. Settings > General > VPN & Device Management > VPN > Add VPN Configuration.
2. Select **Type: L2TP**.
3. **Server:** the verified public IPv4 of Polaris (not Warden).
4. **Account / Password:** the specific existing PPP username and its secret, separate from the machine PSK.
5. **Secret:** the correctly provisioned Global IPsec PSK (enter locally).
6. **Send All Traffic:** enabled if full-tunnel egress via Polaris is required.
7. Connect. On Polaris verify the **IKEv1 SA plus CHILD_SA and PPP session**;
   a PPP session without matching IPsec must not be called protected.

Do not use the staged IKEv2 EAP user `myphone` as a PPP/L2TP
account unless a separate PPP account with that exact identity
was intentionally created. Current EAP registry does NOT populate
`/etc/ppp/chap-secrets`.

## Staging the server candidate: NO LIVE CHANGE

On the already audited Polaris host, after updating a **separate**
development checkout, validate root-only PSK and derive the actual
public IPv4 default-route source. This tool **never displays the PSK**.

~~~bash
(
  set -eu
  repo="$HOME/L2TP-Manager-development"
  [ -f "$repo/tools/l2tp-ipsec-psk.py" ] || exit 1
  sudo python3 "$repo/tools/l2tp-ipsec-psk.py" audit
)
~~~

Stage a root-only candidate under an already existing root-only
configuration directory:

~~~bash
(
  set -eu
  repo="$HOME/L2TP-Manager-development"
  sudo python3 "$repo/tools/l2tp-ipsec-psk.py" stage \
    --output /etc/l2tp-manager/mobile-l2tp-ipsec.candidate.conf
  sudo stat -c '%U:%G %a %n' \
    /etc/l2tp-manager/mobile-l2tp-ipsec.candidate.conf
)
~~~

**DO NOT paste the generated candidate's content in support tickets or
chat — it contains the PSK.** It is a strongSwan `swanctl` candidate for
IKEv1 **transport mode**, narrowed to UDP L2TP port 1701. The script
does not install strongSwan, load the config or modify XFRM. The
candidate must be validated on an installed compatible strongSwan
release; it is not a preverified production config.

Before activation, inspect:

~~~bash
(
  echo '=== Existing VPN listener ownership ==='
  sudo ss -H -lunp | grep -E ':(500|4500|1701)[[:space:]]' || true
  echo '=== Installed IPsec packages ==='
  dpkg-query -W 'strongswan*' 'charon*' 'libcharon*' 2>/dev/null || true
  echo '=== Ubuntu package candidates ==='
  apt-cache policy charon-systemd strongswan-swanctl
  echo '=== PPP and effective routing ==='
  systemctl is-active xl2tpd
  ip -4 route show default
  echo '=== Safe XFRM state count, no keys ==='
  sudo ip xfrm state count
  echo '=== Firewall existing UDP 1701 policy ==='
  sudo iptables -S INPUT | grep -E '1701|policy|IPsec' || true
)
~~~

The installed IPsec service must be separately configured to bind UDP
500 and 4500, and firewall must allow IKE/NAT-T as required. Do not
reload existing `xl2tpd` or unrelated WARP/Docker rules. The
initial dedicated strongSwan service and its candidate config require
package checks, configuration validation, and a rollback plan before
loading.

**Critical enforcement boundary:** the plaintext UDP 1701 L2TP
listener remains reachable. The shared IKEv1 PSK does not turn a
selected PPP username into "IPsec required"; enforcing IPsec-only on
an already shared plaintext listener requires independently verified
XFRM-aware firewall scoping or an isolated encrypted endpoint.
Do not add a blanket DROP 1701 rule: it could disconnect existing
MikroTik clients. Test both the protected and the original plaintext
client before change completion.

## IPv4 and IPv6 caveat

IKEv1 L2TP/IPsec secures the *outer L2TP UDP session*. Client IPv4/IPv6
Internet routing remains the job of PPP and the source-policy/egress
configuration, not the IKEv1 PSK itself. Native iPhone L2TP's IPv6
support must be measured on an actual phone; a server-side IPv6
configuration does not prove that iOS receives a usable IPv6 address.
A successful encrypted VPN login is not proof of requested dual-stack.

## Validation and rollback before production

- IKEv1 SA established on UDP 500/4500; transport CHILD_SA protects
  L2TP UDP 1701; correct PPP user authenticated.
- Real IPv4 HTTPS echo through Polaris and IPv6 HTTPS if negotiated;
  verify current service policy does not route phone via GRE/Warden.
- Reconnect, multiple phones behind NAT, tunnel drop and no plaintext
  downgrade for IPsec-required users; test concurrent legacy MikroTik.
- Controlled restart/reboot and rollback without loss of remote
  management or existing port-forward/Docker/WARP sessions.

Upstream references:
- https://docs.strongswan.org/docs/latest/swanctl/swanctlConf.html
- https://docs.strongswan.org/docs/latest/features/natTraversal.html
- https://docs.strongswan.org/docs/latest/plugins/connmark.html
