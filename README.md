# L2TP Server Manager

Script interaktif untuk instalasi dan manajemen L2TP server di Ubuntu VPS. Dirancang untuk memberikan akses tunnel yang aman ke router MikroTik tanpa IP publik melalui port forwarding.

## Panduan Video

https://youtu.be/x9Py3JSm-aI

## Fitur Utama

- Instalasi otomatis L2TP server (tanpa IPsec)
- Manajemen user L2TP (tambah/hapus/edit)
- Port forwarding untuk akses service internal
- Monitoring status server real-time
- Integrasi systemd untuk service otomatis

## Cara Penggunaan

1. **Download dan jalankan script:**
   ```bash
   git clone https://github.com/safrinnetwork/L2TP-Manager/
   cd L2TP-Manager
   chmod +x l2tp-manager.sh
   sudo ./l2tp-manager.sh
   ```

2. **Pilih opsi 1** untuk instalasi L2TP server

3. **Pilih opsi 3** untuk menambah user L2TP

4. **Pilih opsi 7** untuk konfigurasi port forwarding

## Konfigurasi Jaringan

### Range IP VPN
- **Server IP**: 172.16.101.1
- **Client Range**: 172.16.101.10 - 172.16.101.100
- **DNS Servers**: 8.8.8.8, 8.8.4.4

### Port yang Digunakan
- **UDP 1701**: L2TP tunnel
- **Port custom**: Sesuai konfigurasi port forwarding

## Konfigurasi MikroTik Client

Untuk menghubungkan router MikroTik ke VPS:

```
/interface l2tp-client
add connect-to=IP_VPS_ANDA name=l2tp-out1 user=USERNAME password=PASSWORD
```

## Contoh Port Forwarding

Untuk akses Winbox MikroTik melalui VPS:
1. Tambah port forward: `IP_VPS:6000 -> 172.16.101.10:8291`
2. Akses Winbox via: `IP_VPS:6000`

## File Konfigurasi

Script ini mengelola file-file berikut:
- `/etc/xl2tpd/xl2tpd.conf` - Konfigurasi L2TP server
- `/etc/ppp/options.xl2tpd` - Opsi PPP untuk L2TP
- `/etc/ppp/chap-secrets` - Database autentikasi user
- `/etc/l2tp-forwards.conf` - Konfigurasi port forwarding
- `/etc/systemd/system/l2tp-forwards.service` - Service port forwarding

## Troubleshooting

### Masalah Koneksi
```bash
systemctl status xl2tpd              # Cek status service
journalctl -u xl2tpd -f              # Lihat log real-time
iptables -L -n                       # Verifikasi firewall
```

### Masalah Port Forward
```bash
systemctl status l2tp-forwards.service   # Cek status service forwarding
ps aux | grep socat                      # Cek proses socat
ss -tuln | grep PORT                     # Cek port listening
```

### Masalah IP Conflict
Jika terjadi konflik IP dengan jaringan lokal (misalnya dengan DHCP server router), script ini menggunakan range `172.16.101.0/24` yang tidak konflik dengan range umum seperti `10.x.x.x` atau `192.168.x.x`.

## Keamanan

- Menggunakan autentikasi CHAP (lebih aman dari PAP)
- Tanpa IPsec PSK (lebih sederhana)
- Firewall dikonfigurasi otomatis
- Validasi input untuk mencegah injection attack

## Persyaratan Sistem

- Ubuntu 18.04+ dengan IP publik
- Akses root atau sudo
- Koneksi internet stabil
- Port UDP 1701 terbuka

## Support

Untuk bantuan lebih lanjut:
- Cek log service: `journalctl -u xl2tpd`
- Status koneksi: Menu opsi 2

## Configurable L2TP IPv4 network (fork extension)

Network values are configurable without editing the installer source.
Machine-specific values must not be committed to this public repository.
On a fresh host, create a root-owned plain text config file at
/etc/l2tp-manager/network.conf (mode 0600; one key=value per line).

Keys: VPN_SUBNET, VPN_IP_START, VPN_IP_END, VPN_LOCAL_IP, VPN_MTU,
VPN_MRU, VPN_DNS1, VPN_DNS2, L2TP_PORT.
Default pool remains 172.16.101.10-172.16.101.100 in
172.16.101.0/24. Default PPP MTU/MRU are both 1280.
The installer and IPv4 address allocator validate the configured pool.

IMPORTANT: Modifying the repository or changing the network config does
not migrate live PPP sessions, IP reservations, NAT, routes, firewall
snapshots, or router configurations. Do NOT rerun setup on a live shared
host merely to change an IPv4 pool: plan the migration separately.
IPv6 internet access does not require changing the IPv4 pool.

## Optional IPv6 over GRE (fork extension)

IPv6CP negotiates link-local addresses, not usable Internet IPv6
prefixes. The optional helper generates ULA addresses and uses
host-local JSON settings for client-scoped IPv6 routes and NAT66.
No user/server-specific address or interface is built into the code.

Read [IPv6 over GRE deployment](docs/ipv6-gre.md) and fill in the
per-host JSON templates under examples/. This feature does not alter
server settings unless an administrator explicitly deploys and runs
it, and does not configure MikroTik automatically.

SECURITY: L2TP without IPsec, GRE and NAT66 do not encrypt traffic.
Use a separate secure transport for confidential communications.


## Selected-client IPv4 GRE egress and optional IPsec policy

**IPv4 and IPv6 are independent.** A PPP client can reach the L2TP server and
even have successful IPv6 through GRE while still lacking IPv4 Internet through
the remote GRE gateway. Inspect the IPv4 GRE gateway's return route, NAT44,
forwarding and source-policy choice before changing the client's IPv4 pool.

The optional, client-scoped IPv4 egress tool, examples, guarded persistence
installer, and read-only/troubleshooting steps are in
[docs/ipv4-gre-egress.md](docs/ipv4-gre-egress.md).
It is not installed or enabled automatically.

For optional IPsec requirements, a global host-local policy file can record
per-user intent (`plaintext` vs `ipsec-required`), validated by
`tools/ipsec-policy.py`. **This is only a policy registry, not enforcement.**
Real selective IPsec needs a separate IPsec-only L2TP listener/endpoint,
working kernel IPsec/XFRM policy, a firewall that refuses plaintext
connections on that endpoint, and segregated user credentials. Until that
integration is implemented and tested, **do not claim user-specific IPsec
has been enabled**. See [docs/ipsec-selective.md](docs/ipsec-selective.md).

Security: the users-list command now masks stored passwords, but further
credential-handling audit and secure-transport support remain necessary.


### iPhone / iOS native IKEv2 clients

For selected iPhone users, prefer **native IKEv2/IPsec (separate
strongSwan backend)** rather than enabling L2TP/IPsec on the currently
running MikroTik L2TP listener. This uses a separate, non-overlapping
VPN address pool and individual EAP credentials or certificates.

See [iPhone IKEv2 deployment and authentication design](docs/iphone-ikev2.md).
The repo's existing IPsec policy registry is **metadata only**: an
actual IKEv2 responder, certificate validation, credential isolation,
firewall and routing integration have not been deployed by this project.


## Required default: direct dual-stack users

**All ordinary L2TP users and all iPhone IKEv2 users must have both IPv4
and IPv6 Internet connectivity, exiting directly through the L2TP
ingress/Polaris server rather than GRE/Warden.** Existing explicitly selected
GRE users keep their separate IPv4/IPv6 route and egress gateway.

See [Direct dual-stack architecture and preflight](docs/direct-dualstack.md).
Ordinary L2TP requires per-user routed IPv6 addressing in addition to
IPv6CP link-local; IKEv2 needs two non-overlapping IPv4/IPv6 virtual-IP pools,
IPv4/IPv6 traffic selectors and verified client dual-stack. A WAN on-link
IPv6 /64 is **not** automatically a delegated public VPN prefix. When no
routed public prefix is available, use separate ULA space and scoped NAT66
to the verified ingress public IPv6. No new live routes/firewall/IPsec
configurations are made by checking out this repository.


### Current execution status — 2026-11-10

See the [comprehensive, evidence-based Persian implementation and status plan](docs/EXECUTION-PLAN-2026-11-10.fa.md) and the [active PLAN.md status table](PLAN.md#active-status-and-delivery-plan--2026-11-10).

An ordinary L2TP client has now passed a real IPv6 ping and public-IPv6
HTTPS test through the ingress host **after a manual PPP interface rebind**.
The pilot is still nonpersistent and not generalized to multiple users.
The selective GRE user's IPv4 remote egress needs a fresh client-side
test; the iPhone IKEv2 responder and user provisioning are not deployed.
No GitHub commit or CI check implies production deployment.


### Scoped persistence and global shared IPsec key (development)

The repository now includes:
- `tools/direct6-reconcile.py` with an **independent PPP-aware per-client
  direct IPv6** reconciler. It does not use fixed ppp0/ppp1 names.
- `tools/install-direct6-persistence.sh` with a per-client-scoped
  systemd timer and PPP up/down callbacks, and
  `tools/adopt-direct6-pilot.py` for guarded removal of the old pilot.
- `tools/global-psk.py` which securely creates ONE root-owned global
  strongSwan legacy L2TP/IPsec PSK include file, without ever
  printing or committing the key.
- `tools/ikev2-dualstack.py` which validates input, manages a private
  iPhone EAP registry and renders an **inactive** dual-IPv4/IPv6
  strongSwan configuration candidate.
- Deliberately incomplete example JSON under `examples/`.

**Deployment is not automatic.** See
[Staged stable-deployment gates](docs/STABLE-DEPLOYMENT-GATES.md).
The existing live PPP/IPv6 pilot proved one ordinary client's direct
IPv6 path, but the new reconciler has NOT been field-tested or reboot
tested. StrongSwan remains uninstalled on the historically inspected
Polaris host; a PSK file or account metadata is not IPsec enforcement.

**IPsec choice:** Apple supports L2TP/IPsec with a shared machine PSK
and individual user credentials. On a shared unprotected L2TP/1701
listener, it is not safe to claim a subset of usernames is forced to
use IPsec. Use an independently authenticated, IPsec-only endpoint
and test plaintext denial before enabling protected accounts.
For iPhone IKEv2 individual users, the EAP/certificate design is
different from an L2TP global PSK.


## Android and iPhone — portable IKEv2 VPN profiles (development)

A **single separate** IKEv2/IPsec responder can serve Android and iPhone
with individual EAP-MSCHAPv2 users and **direct ingress/Polaris IPv4
and IPv6** egress (not GRE/Warden). Source support now includes:

- `tools/ikev2-dualstack.py`: root-only EAP account registry and an
  **inactive swanctl server candidate**, with validated IPv4/IPv6 pools.
- `tools/mobile-profiles.py`: portable password-free
  `username.mobileconfig` for Apple's native IKEv2 client and
  `username.sswan` for the Android strongSwan VPN Client.
- `tests/test_mobile_profiles.py`: format checks, full-tunnel fields
  and no PSK/password/private key embedded.

[Mobile setup, server prerequisites and commands](docs/mobile-profiles.md)

**Not yet deployed:** Polaris IKEv2 service, trusted hostname/certificate,
non-overlapping live virtual address pools, public-WAN NAT for IKEv2,
active mobile accounts, reconnect and IPv4+IPv6 phone tests.
The existing global L2TP/IPsec PSK remains a **different** machine-level
secret and is never distributed in IKEv2/EAP profiles. Profile generation
does not imply a working VPN.
