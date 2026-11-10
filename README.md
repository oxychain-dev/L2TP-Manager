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
