#!/usr/bin/env bash
# Install an opt-in, isolated systemd reconciliation timer for IPv4 GRE egress.
# Requires that the standalone egress helper was tested successfully first.
# This does not touch xl2tpd, PPP, GRE, WARP, Docker or system firewall snapshots.
set -eu

if (( EUID != 0 )); then echo "ERROR: Run as root" >&2; exit 1; fi
if (( $# != 2 )); then
    echo "Usage: $0 path/to/ipv4-gre-egress.py /absolute/path/to/egress.json" >&2
    exit 2
fi

source_script=$1
config=$2
[[ -f "$source_script" && ! -L "$source_script" && -r "$source_script" ]] ||
    { echo "ERROR: Invalid source script" >&2; exit 1; }
[[ "$config" == /* && -f "$config" && ! -L "$config" ]] ||
    { echo "ERROR: Config must be an existing absolute regular path" >&2; exit 1; }
[[ $(stat -c %u "$config") == 0 && $(stat -c %a "$config") == 600 ]] ||
    { echo "ERROR: Config must be owned by root and mode 0600" >&2; exit 1; }

python=$(command -v python3) || { echo "ERROR: Missing Python" >&2; exit 1; }
for program in systemctl systemd-analyze install iptables ip; do
    command -v "$program" >/dev/null || { echo "ERROR: Missing $program" >&2; exit 1; }
done
target_dir=/usr/local/libexec/l2tp-manager
target="$target_dir/ipv4-gre-egress.py"
unit=/etc/systemd/system/l2tp-ipv4-gre-egress.service
timer=/etc/systemd/system/l2tp-ipv4-gre-egress.timer

for path in "$target" "$unit" "$timer"; do
    if [[ -e $path || -L $path ]]; then
        echo "ERROR: Refusing to overwrite $path" >&2
        exit 1
    fi
done

"$python" -m py_compile "$source_script"
"$python" "$source_script" apply --dry-run --config "$config" ||
    { echo "ERROR: Preflight failed. Nothing installed." >&2; exit 1; }

umask 077
backup=$(mktemp -d /var/backups/l2tp-ipv4-egress-XXXXXX)
iptables-save > "$backup/iptables.v4"
ip -4 route show table all > "$backup/routes.v4"
ip -4 rule show > "$backup/rules.v4"
echo "Readonly pre-change backup: $backup"

install -d -m 0755 "$target_dir"
install -o root -g root -m 0755 "$source_script" "$target"

cat > "$unit" <<EOF
[Unit]
Description=Reconcile selected L2TP client IPv4 GRE egress on gateway
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
ExecStart=$python $target apply --config $config
EOF

cat > "$timer" <<'EOF'
[Unit]
Description=Retry selected-client GRE IPv4 egress reconciliation
[Timer]
OnBootSec=25s
OnUnitInactiveSec=60s
Unit=l2tp-ipv4-gre-egress.service
[Install]
WantedBy=timers.target
EOF

chmod 0644 "$unit" "$timer"
systemd-analyze verify "$unit" "$timer" ||
    { echo "ERROR: systemd verification failed; timer NOT enabled" >&2; exit 1; }
systemctl daemon-reload
systemctl start l2tp-ipv4-gre-egress.service
systemctl enable --now l2tp-ipv4-gre-egress.timer
echo "Installed independent IPv4 egress timer; backup: $backup"
echo "To audit: systemctl status l2tp-ipv4-gre-egress.timer"
