#!/usr/bin/env bash
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
# shellcheck disable=SC1091
source "$root/config/defaults.conf"
source "$root/lib/core.sh"

validate_vpn_network_settings
[[ "$(vpn_ipv4_to_int 0.0.0.0)" = 0 ]]
[[ "$(vpn_int_to_ipv4 16909060)" = 1.2.3.4 ]]
if vpn_ipv4_to_int 256.1.1.1 >/dev/null; then exit 1; fi
if vpn_ipv4_to_int 01.2.3.4 >/dev/null; then exit 1; fi

VPN_SUBNET=10.44.0.0/20
VPN_IP_START=10.44.0.10
VPN_IP_END=10.44.1.50
VPN_LOCAL_IP=10.44.0.1
VPN_MTU=1280
VPN_MRU=1280
validate_vpn_network_settings

f=$(mktemp)
trap 'rm -f -- "$f"' EXIT
CHAP_SECRETS=$f
printf '%s\n' 'alpha * secret 10.44.0.10' > "$f"
[[ "$(get_next_available_ip)" = 10.44.0.11 ]]

VPN_LOCAL_IP=10.44.0.11
if validate_vpn_network_settings >/dev/null 2>&1; then exit 1; fi
VPN_LOCAL_IP=10.44.0.1
VPN_IP_END=10.45.0.1
if validate_vpn_network_settings >/dev/null 2>&1; then exit 1; fi
echo "network configuration tests passed"
