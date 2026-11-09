#!/bin/bash
# Core Utilities Library
# Made by Mostech
# GitHub: https://github.com/safrinnetwork/

# Logging functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check if line is a comment or empty (used for config file parsing)
is_comment_or_empty() {
    [[ "$1" =~ ^#.*$ ]] || [[ -z "$1" ]]
}

# Unified "Press Enter to continue" prompt
press_enter() {
    echo -e "\n${CYAN}Press Enter to continue...${NC}"
    read -r
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root!"
        exit 1
    fi
}

# Execute command with error checking
exec_cmd() {
    local cmd="$1"
    local error_msg="$2"

    if ! eval "$cmd" >/dev/null 2>&1; then
        [[ -n "$error_msg" ]] && error "$error_msg"
        return 1
    fi
    return 0
}

# =============================================
# OS & Environment Detection
# =============================================

# Detect OS distribution and version
detect_os() {
    local os_id=""
    local os_version=""

    if [[ -f /etc/os-release ]]; then
        os_id=$(. /etc/os-release && echo "$ID")
        os_version=$(. /etc/os-release && echo "$VERSION_ID")
    fi

    echo "${os_id}:${os_version}"
}

# Initialize network variables (lazy-load, called from main scripts)
init_network_vars() {
    # Only set if not already set
    if [[ -z "$PUBLIC_IP" ]] || [[ "$PUBLIC_IP" == "Unable to detect" ]]; then
        PUBLIC_IP=$(get_public_ip)
        export PUBLIC_IP
    fi

    if [[ -z "$DEFAULT_INTERFACE" ]]; then
        DEFAULT_INTERFACE=$(get_default_interface)
        export DEFAULT_INTERFACE
    fi
}

# =============================================
# Firewall Abstraction (iptables/nftables)
# =============================================

# Detect firewall backend and set appropriate commands
detect_firewall_backend() {
    # Check if iptables command exists
    if ! command -v iptables >/dev/null 2>&1; then
        echo "none"
        return 1
    fi

    # Check which backend iptables uses
    local iptables_version
    iptables_version=$(iptables --version 2>/dev/null || echo "")

    if echo "$iptables_version" | grep -q "nf_tables"; then
        echo "nft"
    elif echo "$iptables_version" | grep -q "legacy"; then
        echo "legacy"
    else
        # Default: assume nft on modern systems
        echo "nft"
    fi
}

# Add firewall rule (works with both iptables backends)
firewall_add_rule() {
    iptables "$@" 2>/dev/null
}

# Delete firewall rule
firewall_del_rule() {
    iptables "$@" 2>/dev/null
}

# Check if firewall rule exists
firewall_check_rule() {
    iptables "$@" 2>/dev/null
}

# Save firewall rules (cross-distro)
firewall_save_rules() {
    mkdir -p /etc/iptables 2>/dev/null

    if command -v iptables-save >/dev/null 2>&1; then
        iptables-save > /etc/iptables/rules.v4 2>/dev/null
        return $?
    fi
    return 1
}

# Restore firewall rules (cross-distro)
firewall_restore_rules() {
    if [[ -f /etc/iptables/rules.v4 ]] && command -v iptables-restore >/dev/null 2>&1; then
        iptables-restore < /etc/iptables/rules.v4 2>/dev/null
        return $?
    fi
    return 1
}

# =============================================
# Port Detection (cross-distro, no netstat)
# =============================================

# Check if a port is listening - works across all distro versions
# Uses only ss (part of iproute2, always available)
is_port_listening() {
    local port="$1"
    local proto="${2:-tcp}"

    # Use ss with exact port match to avoid false positives
    # (e.g., port 80 matching 8080)
    if [[ "$proto" == "tcp" ]]; then
        ss -tln state listening 2>/dev/null | awk '{print $4}' | grep -qE "(^|:)${port}$"
    else
        ss -uln state unconnected 2>/dev/null | awk '{print $4}' | grep -qE "(^|:)${port}$"
    fi
}

# Check if a port is in use (listening or in config)
port_in_use() {
    local port="$1"

    # Check if port is listening on the system
    if is_port_listening "$port" "tcp"; then
        return 0
    fi

    # Check if port is in forwards config
    if grep -q ":${port}:" "$FORWARDS_CONFIG" 2>/dev/null; then
        return 0
    fi

    return 1
}

# =============================================
# Input Validation
# =============================================

validate_ip() {
    local ip="$1"
    if [[ $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        local IFS='.'
        local -a octets=($ip)
        for octet in "${octets[@]}"; do
            if (( octet > 255 )); then
                return 1
            fi
        done
        return 0
    fi
    return 1
}

validate_port() {
    local port="$1"
    if [[ $port =~ ^[0-9]+$ ]] && (( port >= 1 && port <= 65535 )); then
        return 0
    fi
    return 1
}

validate_username() {
    local username="$1"
    if [[ $username =~ ^[a-zA-Z0-9_-]{3,32}$ ]]; then
        return 0
    fi
    return 1
}

validate_password() {
    local password="$1"
    if [[ ${#password} -ge 6 && ${#password} -le 64 ]]; then
        return 0
    fi
    return 1
}

validate_forward_name() {
    local name="$1"
    if [[ $name =~ ^[a-zA-Z0-9_-]{2,20}$ ]]; then
        return 0
    fi
    return 1
}

# Variable sanitization function
sanitize_input() {
    local input="$1"
    # Remove potentially dangerous characters
    echo "$input" | sed 's/[;&|`$(){}\\\<>]//g'
}

# =============================================
# Random Generation
# =============================================

# Generate random username
generate_random_username() {
    local prefixes=("user" "client" "vpn" "l2tp" "remote" "mobile" "laptop" "office" "home" "guest")
    local prefix=${prefixes[$RANDOM % ${#prefixes[@]}]}
    local number=$(printf "%04d" $((RANDOM % 10000)))
    echo "${prefix}${number}"
}

# Generate random password
generate_random_password() {
    local length=${1:-12}
    local chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%^&*"
    local password=""

    # Ensure at least one character from each category
    local uppers="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    local lowers="abcdefghijklmnopqrstuvwxyz"
    local numbers="0123456789"
    local symbols="@#$%^&*"

    # Add one from each category
    password+=${uppers:$((RANDOM % ${#uppers})):1}
    password+=${lowers:$((RANDOM % ${#lowers})):1}
    password+=${numbers:$((RANDOM % ${#numbers})):1}
    password+=${symbols:$((RANDOM % ${#symbols})):1}

    # Fill the rest randomly
    for ((i=4; i<length; i++)); do
        password+=${chars:$((RANDOM % ${#chars})):1}
    done

    # Shuffle the password
    echo "$password" | fold -w1 | shuf | tr -d '\n'
}

# =============================================
# Network Utilities
# =============================================

# Get public IP (with curl availability check)
get_public_ip() {
    # Check if curl is available
    if ! command -v curl >/dev/null 2>&1; then
        # Try wget as fallback
        if command -v wget >/dev/null 2>&1; then
            local ip=$(wget -qO- --timeout=5 ifconfig.me 2>/dev/null)
            [[ -n "$ip" ]] && echo "$ip" && return 0
        fi
        echo "Unable to detect"
        return 1
    fi

    local ip=$(curl -s -4 --max-time 5 ifconfig.me 2>/dev/null)
    if [[ -z "$ip" ]]; then
        ip=$(curl -s -4 --max-time 5 icanhazip.com 2>/dev/null)
    fi
    if [[ -z "$ip" ]]; then
        ip=$(curl -s -4 --max-time 5 ipinfo.io/ip 2>/dev/null)
    fi
    if [[ -z "$ip" ]]; then
        ip="Unable to detect"
    fi
    echo "$ip"
}

# Get default network interface
get_default_interface() {
    local interface=$(ip route | grep default | awk '{print $5}' | head -n1)
    if [[ -z "$interface" ]]; then
        interface=$(ip link show | grep -E "^[0-9]+: (eth|ens|enp)" | head -n1 | cut -d: -f2 | tr -d ' ')
    fi
    echo "$interface"
}

# Get system information (cross-distro compatible)
get_system_info() {
    local os_info=""
    local cpu_info=""
    local ram_info=""
    local disk_info=""

    # OS Info
    if [ -f /etc/os-release ]; then
        os_info=$(grep "PRETTY_NAME" /etc/os-release | cut -d'"' -f2)
    else
        os_info="Unknown"
    fi

    # CPU Info - use LANG=C to ensure English output regardless of locale
    if command -v lscpu >/dev/null 2>&1; then
        local cpu_model=$(LANG=C lscpu | grep "Model name" | head -n1 | cut -d':' -f2 | xargs)
        local cpu_cores=$(LANG=C lscpu | grep "^CPU(s):" | head -n1 | awk '{print $2}')
        cpu_info="$cpu_model ($cpu_cores cores)"
    else
        cpu_info="Unknown"
    fi

    # RAM Info - use 'free' without -h to avoid parsing human-readable suffixes
    if command -v free >/dev/null 2>&1; then
        ram_info=$(free -m | awk '/^Mem:/ {printf "%d MB / %d MB (%.1f%% used)", $3, $2, ($3/$2)*100}')
    else
        ram_info="Unknown"
    fi

    # Disk Info
    if command -v df >/dev/null 2>&1; then
        disk_info=$(df -h / | awk 'NR==2 {printf "%s / %s (%s used)", $3, $2, $5}')
    else
        disk_info="Unknown"
    fi

    echo "OS:$os_info"
    echo "CPU:$cpu_info"
    echo "RAM:$ram_info"
    echo "Storage:$disk_info"
}

# Cached version of get_system_info (called once per session)
_CACHED_SYSTEM_INFO=""
get_system_info_cached() {
    if [[ -z "$_CACHED_SYSTEM_INFO" ]]; then
        _CACHED_SYSTEM_INFO=$(get_system_info)
    fi
    echo "$_CACHED_SYSTEM_INFO"
}

# =============================================
# User & IP Management
# =============================================

# Check if username already exists
username_exists() {
    local username="$1"
    grep -q "^$username\s" "$CHAP_SECRETS" 2>/dev/null
}

# Check if IP is already assigned
ip_already_assigned() {
    local ip="$1"
    grep -q "\s${ip}$" "$CHAP_SECRETS" 2>/dev/null
}

# Convert an IPv4 address to a 32-bit integer without external dependencies.
vpn_ipv4_to_int() {
    local -a octets
    local octet
    [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    IFS=. read -r -a octets <<< "$1"
    [[ ${#octets[@]} -eq 4 ]] || return 1
    for octet in "${octets[@]}"; do
        [[ "$octet" =~ ^(0|[1-9][0-9]{0,2})$ ]] || return 1
        (( 10#$octet <= 255 )) || return 1
    done
    printf '%u\n' "$(( (10#${octets[0]} << 24) | (10#${octets[1]} << 16) | (10#${octets[2]} << 8) | 10#${octets[3]} ))"
}

vpn_int_to_ipv4() {
    local n="$1"
    printf '%d.%d.%d.%d\n' "$(( (n >> 24) & 255 ))" "$(( (n >> 16) & 255 ))" "$(( (n >> 8) & 255 ))" "$(( n & 255 ))"
}

# Fail before modifying services or firewall if the pool is ambiguous.
validate_vpn_network_settings() {
    local base prefix ipnet ipstart ipend iplocal mask broadcast
    if [[ ! "$VPN_SUBNET" =~ ^([0-9.]+)/([0-9]{1,2})$ ]]; then
        error "VPN_SUBNET must be a canonical IPv4 CIDR"
        return 1
    fi
    base=${BASH_REMATCH[1]}
    prefix=${BASH_REMATCH[2]}
    if (( 10#$prefix < 8 || 10#$prefix > 30 )); then
        error "VPN_SUBNET must have prefix length /8 through /30"
        return 1
    fi
    prefix=$((10#$prefix))
    ipnet=$(vpn_ipv4_to_int "$base") || { error "Invalid VPN_SUBNET address"; return 1; }
    ipstart=$(vpn_ipv4_to_int "$VPN_IP_START") || { error "Invalid VPN_IP_START"; return 1; }
    ipend=$(vpn_ipv4_to_int "$VPN_IP_END") || { error "Invalid VPN_IP_END"; return 1; }
    iplocal=$(vpn_ipv4_to_int "$VPN_LOCAL_IP") || { error "Invalid VPN_LOCAL_IP"; return 1; }
    mask=$(( (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF ))
    broadcast=$(( ipnet | (0xFFFFFFFF ^ mask) ))
    if (( (ipnet & mask) != ipnet || ipstart <= ipnet || ipend >= broadcast ||
          iplocal <= ipnet || iplocal >= broadcast || ipstart > ipend ||
          (ipstart & mask) != ipnet || (ipend & mask) != ipnet ||
          (iplocal & mask) != ipnet || (ipend - ipstart + 1) > 4096 ||
          (iplocal >= ipstart && iplocal <= ipend) )); then
        error "VPN subnet, pool and local address conflict or are out of range"
        return 1
    fi
    vpn_ipv4_to_int "$VPN_DNS1" >/dev/null || { error "Invalid VPN_DNS1"; return 1; }
    vpn_ipv4_to_int "$VPN_DNS2" >/dev/null || { error "Invalid VPN_DNS2"; return 1; }
    if [[ ! "$VPN_MTU" =~ ^[0-9]{4}$ || ! "$VPN_MRU" =~ ^[0-9]{4}$ ]] ||
       (( VPN_MTU < 1280 || VPN_MTU > 1500 || VPN_MRU < 1280 || VPN_MRU > 1500 )); then
        error "VPN_MTU and VPN_MRU must be 1280..1500"
        return 1
    fi
    if [[ ! "$L2TP_PORT" =~ ^[0-9]{1,5}$ ]] ||
       (( 10#$L2TP_PORT < 1 || 10#$L2TP_PORT > 65535 )); then
        error "Invalid L2TP_PORT"
        return 1
    fi
}

# Allocate from the configured pool; no assumptions about a specific /24.
get_next_available_ip() {
    validate_vpn_network_settings || return 1
    local start end n candidate
    start=$(vpn_ipv4_to_int "$VPN_IP_START") || return 1
    end=$(vpn_ipv4_to_int "$VPN_IP_END") || return 1
    for ((n=start; n<=end; n++)); do
        candidate=$(vpn_int_to_ipv4 "$n")
        if ! awk -v target="$candidate" '
            $1 !~ /^#/ && $4 == target { found=1; exit }
            END { exit found ? 0 : 1 }
        ' "$CHAP_SECRETS"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

# =============================================
# Port Generation
# =============================================

# Generate random port (range 1000-9999)
generate_random_port() {
    echo $((RANDOM % 9000 + 1000))
}

# Generate unique port
generate_unique_port() {
    local max_attempts=100
    local attempt=0

    while (( attempt < max_attempts )); do
        local port=$(generate_random_port)
        if ! port_in_use "$port"; then
            echo "$port"
            return 0
        fi
        ((attempt++))
    done

    return 1
}
