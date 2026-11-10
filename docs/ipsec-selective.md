# Global IPsec policy with selectively protected L2TP users

## Security boundary

**Do not promise per-user IPsec enforcement on a shared L2TP UDP listener.**
PPP/CHAP authenticates a username after initial L2TP packet reception,
whereas IPsec transport policy is established and enforced below L2TP and
before PPP authentication. A flag keyed only by the eventual PPP username
cannot prevent that username from being used over an unencrypted listener.

In particular, adding `ipsec=true` to a user record is **NOT** enforcement.

### Safe policy architecture

- Maintain host-local **global policy** in
  `/etc/l2tp-manager/ipsec-policy.json` (root-owned mode 0600).
- Every user is assigned either `plaintext` or `ipsec-required`.
- A `ipsec-required` user needs an **IPsec-only, isolated L2TP endpoint**:
  separate verified listener address/instance or equivalent isolated
  network namespace and firewall + IKE/IPsec policies, supported by the
  installed daemon. An encrypted and plain user must not share the same
  exact L2TP listening address/port or a plaintext escape path.
- Require independent strongSwan/other maintained IPsec daemon deployment
  and mandatory kernel XFRM/IPsec enforcement for the protected endpoint.
  Audit actual encrypted SAs and drop plaintext UDP L2TP there.
- Do not place PSKs, passwords, certificates, endpoint IPs or site-specific
  credentials in the GitHub repo. Use secrets stores and role-appropriate
  file permissions.
- Multiple L2TP/IPsec clients behind the same NAT can have transport-mode
  selector/connmark limitations; do not assume working multi-client SAs
  without a compatibility test.

## Repository implementation today

`tools/ipsec-policy.py` validates **configuration/intent**, not runtime
IPsec or XFRM enforcement. `examples/ipsec-policy.json` starts with the
global mode disabled and no users or endpoints.

Global config fields:

~~~json
{
  "global": {
    "mode": "disabled",
    "default_user_policy": "plaintext"
  },
  "endpoints": {},
  "users": {}
}
~~~

When dedicated IPsec/plain listeners have actually been created, the
administrator can change `mode` to `dedicated-endpoints` and enter
independent endpoints with keys `transport` (plaintext or ipsec),
`bind_ipv4` (real bound unicast address) and `l2tp_udp_port` (actual UDP port).
Every explicit user mapping has `policy` and `endpoint` keys. A policy
validator prevents mapping a protected user to a plaintext endpoint.

Validate the host-local file with:

~~~sh
sudo python3 tools/ipsec-policy.py validate
sudo python3 tools/ipsec-policy.py status
~~~

Select policy metadata for an **existing** user after creating and auditing
the endpoint:

~~~sh
sudo python3 tools/ipsec-policy.py set-user \
  --username "$L2TP_USERNAME" \
  --policy ipsec-required \
  --endpoint "$SECURE_ENDPOINT_NAME"
~~~

Both variables must be validated administrative selections. This command
updates local metadata only: it does **not** configure xl2tpd, install an
IPsec daemon, enforce a plaintext firewall deny, or change an active
user's authentication or L2TP port. The command reports this explicitly.

## Remaining implementation work (blocked before secure production use)

1. Verify OS packaging, strongSwan backend (swanctl vs legacy), existing
   XFRM policies and whether the host has distinct bindable addresses.
2. Implement isolated L2TP listening instances and credentials confined
   to the intended endpoint. Review IPv4 address allocation collisions,
   pppd instance options, daemon lifecycle and UDP 1701 binding.
3. Implement independent IPsec-only firewall enforcement (drop unprotected
   L2TP on the protected endpoint), validate established SAs and the
   RouterOS build's supported L2TP/IPsec algorithms.
4. Prove that a protected account **cannot** log in via the plaintext
   endpoint, including users behind NAT and reconnections.
5. Add safely managed secret input, certificate/PSK rotation, audit trail,
   fail-closed behavior and rollback to dedicated encrypted deployments.
6. Integrate endpoint selection with CLI account management only after
   a negative authentication test confirms no plaintext downgrade.

**Until those gates pass, do not mark "per-user IPsec enabled".**

Relevant upstream references:
- https://docs.strongswan.org/docs/latest/plugins/connmark.html
- https://docs.strongswan.org/docs/latest/howtos/ipsecProtocol.html
- https://ppp.samba.org/pppd.html
