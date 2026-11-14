#!/usr/bin/env bash
# Plain L2TP multi-WAN provisioning. NO IPsec/MPPE/encryption changes.

plain_l2tp_tool() {
    command -v python3 >/dev/null 2>&1 || {
        error "python3 required for plain L2TP account management"
        return 1
    }
    python3 "$SCRIPT_DIR/tools/plain-l2tp-multiwan.py" "$@"
}

plain_l2tp_create() {
    local username password chosen
    validate_vpn_network_settings || return 1
    printf '%s\n' 'Separate username + unique static PPP IP per physical WAN.'
    printf '%s\n' 'Plain L2TP + CHAP ONLY. No encryption and no automatic public forwards.'
    read -r -p 'New CA2/CA3 PPP username: ' username || return 1
    validate_username "$username" || { error "Invalid username"; return 1; }
    read -r -s -p 'PPP password (12-64 safe characters): ' password || return 1
    echo
    validate_password "$password" || { error "Invalid PPP password"; return 1; }
    read -r -p 'Type CREATE PLAIN ACCOUNT to confirm: ' chosen || return 1
    [[ "$chosen" == 'CREATE PLAIN ACCOUNT' ]] || { info "Cancelled"; return 0; }
    if ! add_user_to_system "$username" "$password" ""; then
        error "Account unchanged; inspect allocator error"
        return 1
    fi
    printf 'Created user %s with static PPP peer IPv4 %s\n' "$username" "$ADDED_USER_IP"
    printf '%s\n' 'PSK profile distribution disabled for this user (not an IPsec access policy).'
    printf '%s\n' 'No daemon restart, NAT rewrite, firewall opening or route change requested.'
    printf '%s\n' 'Do not paste the PPP password into logs or GitHub.'
}

plain_l2tp_change() {
    local action username confirmation
    read -r -p 'Username: ' username || return 1
    validate_username "$username" || { error "Invalid username"; return 1; }
    echo 'Only disconnected accounts may be disabled/removed. Remove references first.'
    read -r -p 'Action (disable/enable/remove): ' action || return 1
    case "$action" in disable|enable|remove) ;; *) error "Invalid action"; return 1;; esac
    confirmation="CONFIRM $action $username"
    read -r -p "Type '$confirmation' to proceed: " typed || return 1
    [[ "$typed" == "$confirmation" ]] || { info "Cancelled"; return 0; }
    if plain_l2tp_tool "$action" --username "$username"; then
        if [[ "$action" == remove ]]; then
            psk_client_tool prune || warning "Stale PSK distribution label not cleaned"
        fi
    else
        error "Account unchanged; inspect active sessions/referenced routes"
        return 1
    fi
}

plain_multiwan_menu() {
    local choice
    while true; do
        echo
        echo "=== PLAIN L2TP / MULTI-WAN (NO IPsec, NO MPPE) ==="
        echo '[1] Configured accounts (no secrets)'
        echo '[2] Active PPP sessions / username / IP / counters'
        echo '[3] Detect conflicts and unknown live peers'
        echo '[4] Add independent CA2/CA3 account (no restart)'
        echo '[5] Disable, enable or remove a disconnected account'
        echo '[6] L2TP and forwarding service health'
        echo '[0] Return'
        read -r -p 'Choice: ' choice || return 1
        case "$choice" in
            1) plain_l2tp_tool list ;;
            2) plain_l2tp_tool sessions ;;
            3) plain_l2tp_tool check ;;
            4) plain_l2tp_create ;;
            5) plain_l2tp_change ;;
            6) plain_l2tp_tool health ;;
            0) return 0 ;;
            *) warning "Invalid choice" ;;
        esac
    done
}
