#!/usr/bin/env bash
# Shared global PSK distribution controls. Metadata is NOT IPsec enforcement.

psk_client_tool() {
    command -v python3 >/dev/null 2>&1 || {
        error "python3 is required for the PSK client manager."
        return 1
    }
    python3 "$SCRIPT_DIR/tools/psk-client-manager.py" "$@"
}

psk_choose_for_user() {
    local username="$1" choice
    [[ "$username" =~ ^[A-Za-z0-9_-]{3,32}$ ]] || return 1
    printf '\n%s\n' 'Shared-PSK client settings (this does NOT enforce IPsec-only):'
    psk_client_tool status --username "$username" || return 1
    printf '%s\n' '[1] Offer shared PSK configuration' \
        '[2] Stop offering shared PSK configuration' \
        '[0] Keep existing status'
    read -r -p 'Choose (0-2): ' choice || return 1
    case "$choice" in
        1) psk_client_tool set --username "$username" --offered yes ;;
        2) psk_client_tool set --username "$username" --offered no ;;
        0|'') return 0 ;;
        *) warning "No PSK changes (invalid choice)"; return 1 ;;
    esac
}

psk_global_settings() {
    local choice answer
    while :; do
        printf '\n%s\n' '=== Global L2TP/IPsec PSK ==='
        psk_client_tool global-status || return 1
        printf '%s\n' '[1] Show global PSK on this trusted terminal (confirmation required)' \
            '[2] Change/synchronize shared PSK (Enter=random 16; no active IPsec sessions)' \
            '[3] Reload strongSwan credentials (no restart)' \
            '[4] Restart only strongSwan (disconnects IPsec users)' \
            '[5] Restart xl2tpd (disconnects current PPP users)' \
            '[0] Back'
        read -r -p 'Choose (0-5): ' choice || return 1
        case "$choice" in
            1) psk_client_tool global-show || warning "Secret reveal cancelled/failed" ;;
            2)
                printf '%s\n' 'WARNING: global rotation invalidates the PSK held by every existing client.' \
                    'It updates only the owned global-PSK and active L2TP swanctl candidate files.' \
                    'Do not rotate until real client connectivity and recovery are validated.'
                psk_client_tool global-rotate || warning "Rotation not performed or failed"
                ;;
            3)
                if systemctl is-active --quiet strongswan.service; then
                    swanctl --load-creds --noprompt || warning "Credential reload failed"
                else
                    warning "strongSwan is inactive; no credentials reloaded."
                fi
                ;;
            4)
                printf '%s\n' 'Active IPsec connections will be interrupted.'
                read -r -p 'Type RESTART IPSEC to confirm: ' answer || return 1
                if [[ "$answer" == 'RESTART IPSEC' ]]; then
                    systemctl restart strongswan.service || warning "strongSwan restart failed"
                    systemctl is-active strongswan.service || true
                else
                    info "Cancelled."
                fi
                ;;
            5)
                printf '%s\n' 'WARNING: ALL current L2TP/PPP connections may be interrupted.'
                read -r -p 'Type RESTART L2TP to confirm: ' answer || return 1
                if [[ "$answer" == 'RESTART L2TP' ]]; then
                    systemctl restart xl2tpd.service || warning "xl2tpd restart failed"
                    systemctl is-active xl2tpd.service || true
                else
                    info "Cancelled."
                fi
                ;;
            0) return 0 ;;
            *) warning "Invalid choice" ;;
        esac
    done
}
