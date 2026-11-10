#!/usr/bin/env bash
# Install the direct-L2TP IPv6 reconciler, isolated from existing PPP/GRE.
# Needs a separate reviewed, root-owned 0600 JSON config.
set -eu
if (( EUID != 0 )); then echo "Root required" >&2; exit 1; fi
if (( $# != 2 )); then
    echo "Usage: $0 /path/to/direct6-reconcile.py /absolute/path/to/direct6.json" >&2
    exit 2
fi
program=$1
config=$2
[[ -f "$program" && ! -L "$program" && -r "$program" ]] ||
    { echo "Invalid source program" >&2; exit 1; }
[[ "$config" == /* && -f "$config" && ! -L "$config" ]] ||
    { echo "Config must be an absolute regular path" >&2; exit 1; }
[[ $(stat -c %u "$config") == 0 && $(stat -c %a "$config") == 600 ]] ||
    { echo "Config must be root-owned, 0600" >&2; exit 1; }
for binary in python3 systemctl systemd-analyze install ip ip6tables ip6tables-save; do
    command -v "$binary" >/dev/null ||
        { echo "Missing $binary" >&2; exit 1; }
done
python=$(command -v python3)
dest=/usr/local/libexec/l2tp-manager/direct6-reconcile.py
service=/etc/systemd/system/l2tp-direct6.service
timer=/etc/systemd/system/l2tp-direct6.timer
hook=/usr/local/sbin/l2tp-direct6-ppp-hook
for target in "$dest" "$service" "$timer" "$hook"; do
    [[ ! -e "$target" && ! -L "$target" ]] ||
        { echo "Refuse overwrite: $target" >&2; exit 1; }
done
for dir in ip-up.d ipv6-up.d ip-down.d ipv6-down.d; do
    path="/etc/ppp/$dir/99-l2tp-direct6"
    [[ -d "/etc/ppp/$dir" && ! -e "$path" && ! -L "$path" ]] ||
        { echo "PPP hook conflict: $path" >&2; exit 1; }
done
for name in ip-up ipv6-up ip-down ipv6-down; do
    dispatcher="/etc/ppp/$name"
    [[ -r "$dispatcher" ]] && grep -q 'run-parts' "$dispatcher" ||
        { echo "PPP dispatcher not verified: $dispatcher" >&2; exit 1; }
done

"$python" -m py_compile "$program"
"$python" "$program" apply --dry-run --config "$config" ||
    { echo "Preflight failed: installation aborted" >&2; exit 1; }
umask 077
backup=$(mktemp -d /var/backups/l2tp-direct6-XXXXXX)
ip6tables-save > "$backup/ip6tables.v6"
ip -6 route show table all > "$backup/routes.v6"
ip -6 rule show > "$backup/rules.v6"
echo "Backed up pre-install evidence: $backup"

install -d -o root -g root -m 0755 /usr/local/libexec/l2tp-manager
install -o root -g root -m 0755 "$program" "$dest"
cat > "$service" <<EOF
[Unit]
Description=Reconcile ordinary L2TP direct IPv6 clients
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
ExecStart=$python $dest apply --config $config
TimeoutStartSec=25s
EOF
cat > "$timer" <<'EOF'
[Unit]
Description=Periodic ordinary L2TP direct IPv6 reconnection check
[Timer]
OnBootSec=25s
OnUnitInactiveSec=30s
Unit=l2tp-direct6.service
[Install]
WantedBy=timers.target
EOF
cat > "$hook" <<'EOF'
#!/usr/bin/env bash
# Never block pppd on route reconciliation.
systemctl --no-block start l2tp-direct6.service >/dev/null 2>&1 || :
EOF
chmod 0644 "$service" "$timer"
chmod 0755 "$hook"
for dir in ip-up.d ipv6-up.d ip-down.d ipv6-down.d; do
    ln -s "$hook" "/etc/ppp/$dir/99-l2tp-direct6"
done
systemd-analyze verify "$service" "$timer" ||
    { echo "Unit verification failed; do not enable timer" >&2; exit 1; }
systemctl daemon-reload
systemctl start l2tp-direct6.service
systemctl enable --now l2tp-direct6.timer
echo "Installed direct IPv6 reconciling timer; backup: $backup"
echo "Audit: systemctl show l2tp-direct6.service -p Result -p ExecMainStatus"
