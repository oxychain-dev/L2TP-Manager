#!/bin/bash
# Users Library
# Made by Mostech
# GitHub: https://github.com/safrinnetwork/

add_user_manual() {
    echo -e "\n${YELLOW}✏️  Manual User Entry...${NC}"
    local username password ip_addr
    
    # Get public IP for display
    local PUBLIC_IP=$(get_public_ip)
    
    # Username validation
    while true; do
        read -p "Enter username (3-32 chars, alphanumeric, _, -): " username
        username=$(sanitize_input "$username")
        
        if [[ -z "$username" ]]; then
            error "Username cannot be empty"
            continue
        fi
        
        if ! validate_username "$username"; then
            error "Invalid username. Use 3-32 characters (letters, numbers, _, -)"
            continue
        fi
        
        # Check if user already exists
        if username_exists "$username"; then
            error "User '$username' already exists!"
            continue
        fi
        break
    done
    
    # Password validation
    while true; do
        read -r -s -p "Enter password (12-64 safe characters): " password
        echo
        
        if [[ -z "$password" ]]; then
            error "Password cannot be empty"
            continue
        fi
        
        if ! validate_password "$password"; then
            error "Password must be 12-64 allowed characters (letters, digits, @ . _ + = ! % : -)"
            continue
        fi
        
        break
    done
    
    # Auto-assign next available static IP
    if ip_addr=$(get_next_available_ip); then
        info "Auto-assigned next available static IP: $ip_addr"
    else
        error "No available static IPs in range. Please check IP assignments."
        return 1
    fi
    
    # Port forwarding setup
    echo -e "\n${CYAN}🔄 Port Forwarding Setup:${NC}"
    echo -e "${YELLOW}Choose port forwarding option:${NC}"
    echo -e "   ${GREEN}[1]${NC} 🎯 Standard MikroTik (Winbox + API)"
    echo -e "   ${GREEN}[2]${NC} 🛠️  Custom ports"
    echo -e "   ${GREEN}[3]${NC} ⏭️  Skip port forwarding"
    echo
    echo -e "${YELLOW}Enter your choice (1-3): ${NC}"
    echo -ne "${GREEN}▶ ${NC}"
    read forward_choice
    
    local create_forwards=false
    local custom_ports=()
    
    case $forward_choice in
        1)
            create_forwards=true
            info "Will create standard MikroTik forwards (Winbox + API)"
            ;;
        2)
            echo -e "\n${YELLOW}Custom Port Setup:${NC}"
            echo "Enter ports to forward:"
            echo "• Single port: 22"
            echo "• Multiple ports: 22,80,443"
            echo "• With description: 22:SSH,80:HTTP,443:HTTPS"
            echo
            read -p "Enter ports: " port_input
            
            if [[ -n "$port_input" ]]; then
                # Split by comma and process each port
                IFS=',' read -ra port_array <<< "$port_input"
                for port_spec in "${port_array[@]}"; do
                    port_spec=$(echo "$port_spec" | xargs) # trim whitespace
                    
                    if [[ "$port_spec" =~ ^[0-9]+:[^:]+$ ]]; then
                        # Format: port:description
                        custom_ports+=("$port_spec")
                        local port_num=${port_spec%%:*}
                        local desc=${port_spec#*:}
                        echo "Added: Port $port_num ($desc)"
                    elif [[ "$port_spec" =~ ^[0-9]+$ ]]; then
                        # Format: just port number
                        if [[ "$port_spec" -ge 1 && "$port_spec" -le 65535 ]]; then
                            custom_ports+=("$port_spec:Port$port_spec")
                            echo "Added: Port $port_spec"
                        else
                            warning "Invalid port number: $port_spec (valid range: 1-65535)"
                        fi
                    else
                        warning "Invalid format: $port_spec"
                    fi
                done
                
                if [[ ${#custom_ports[@]} -gt 0 ]]; then
                    create_forwards=true
                    info "Will create ${#custom_ports[@]} custom port forward(s)"
                else
                    info "No valid ports specified"
                fi
            else
                info "No ports specified"
            fi
            ;;
        3)
            info "Skipping port forwarding setup"
            ;;
        *)
            warning "Invalid choice. Skipping port forwarding."
            ;;
    esac
    
    # Add user to system
    add_user_to_system "$username" "$password" "$ip_addr"
    
    # Handle port forwarding after user creation
    local winbox_port="" api_port="" custom_forward_info=""
    
    if [[ "$create_forwards" == "true" ]]; then
        echo -e "\n${YELLOW}Setting up port forwards...${NC}"
        
        if [[ $forward_choice -eq 1 ]]; then
            # Standard MikroTik forwards
            local port_info port_output
            if port_output=$(create_user_port_forwards "$username" "$ip_addr" 2>/dev/null); then
                # Extract port numbers - scan all lines for the port pair pattern
                while IFS= read -r line; do
                    if [[ "$line" =~ ^[0-9]+,[0-9]+$ ]]; then
                        IFS=',' read -r winbox_port api_port <<< "$line"
                    fi
                done <<< "$port_output"
                info "Standard MikroTik port forwards created successfully"
            else
                warning "Failed to create standard port forwards. You can add them manually later."
            fi
        elif [[ $forward_choice -eq 2 && ${#custom_ports[@]} -gt 0 ]]; then
            # Custom port forwards
            local success_count=0
            local forward_details=()
            
            for port_spec in "${custom_ports[@]}"; do
                local int_port=${port_spec%%:*}
                local description=${port_spec#*:}
                local ext_port=$(generate_unique_port)
                local forward_name="${username}-${int_port}"
                
                if add_port_forward_rule "$forward_name" "$ext_port" "$ip_addr" "$int_port" "$description for $username"; then
                    forward_details+=("$ext_port:$int_port:$description")
                    ((success_count++))
                else
                    warning "Failed to create forward for port $int_port"
                fi
            done
            
            if [[ $success_count -gt 0 ]]; then
                info "Created $success_count custom port forward(s)"
                # Build custom forward info for display
                for detail in "${forward_details[@]}"; do
                    local ext_p=${detail%%:*}
                    local remaining=${detail#*:}
                    local int_p=${remaining%%:*}
                    local desc=${remaining#*:}
                    custom_forward_info+="\n   • $desc: $PUBLIC_IP:$ext_p → $ip_addr:$int_p"
                done
                
                # Restart port forwards service to include new rules
                systemctl restart l2tp-forwards >/dev/null 2>&1
            fi
        fi
    fi
    
    # Display enhanced connection details
    echo -e "\n${GREEN}✓ User Created Successfully!${NC}"
    echo -e "${CYAN}===============================================${NC}"
    echo -e "${YELLOW}📋 Connection Details:${NC}"
    echo -e "${CYAN}Server IP:   ${NC}$PUBLIC_IP"
    echo -e "${CYAN}L2TP Port:   ${NC}$L2TP_PORT"
    echo -e "${CYAN}Username:    ${NC}$username"
    echo -e "${CYAN}Password:    ${NC}$password"
    echo -e "${CYAN}Static IP:   ${NC}$ip_addr"
    
    # Show port forwarding details if created
    if [[ -n "$winbox_port" && -n "$api_port" ]]; then
        echo -e "${CYAN}Port Forwards:${NC}"
        echo -e "   • Winbox: $PUBLIC_IP:$winbox_port → $ip_addr:8291"
        echo -e "   • API:    $PUBLIC_IP:$api_port → $ip_addr:8728"
    elif [[ -n "$custom_forward_info" ]]; then
        echo -e "${CYAN}Port Forwards:${NC}"
        echo -e "$custom_forward_info"
    fi
    
    echo -e "${CYAN}===============================================${NC}"
    echo -e "${PURPLE}💡 Save these credentials safely!${NC}"
}

add_user_random() {
    local username password ip_addr create_forwards
    local max_attempts=10
    local attempt=0
    
    # Generate unique random username
    while true; do
        username=$(generate_random_username)
        if ! username_exists "$username"; then
            break
        fi
        
        ((attempt++))
        if (( attempt >= max_attempts )); then
            error "Failed to generate unique username after $max_attempts attempts"
            return 1
        fi
    done
    
    # Generate random password
    password=$(generate_random_password 20) || return 1
    
    # Auto-assign next available static IP
    if ip_addr=$(get_next_available_ip); then
        info "Auto-assigned next available static IP: $ip_addr"
    else
        error "No available static IPs in range. Using auto-assign."
        ip_addr="*"
    fi
    
    # Ask about port forwarding (only if we have static IP)
    if [[ "$ip_addr" != "*" ]]; then
        echo -e "\n${YELLOW}🔄 Port Forwarding Setup:${NC}"
        echo -e "Would you like to create port forwards for MikroTik access?"
        echo -e "   • Winbox (8291) - Random external port (1000-9999)"
        echo -e "   • API (8728) - Random external port (1000-9999)"
        echo
        echo -e "${YELLOW}Create port forwards? (Y/n): ${NC}"
        echo -ne "${GREEN}▶ ${NC}"
        read create_forwards
        
        # Default to Yes if empty or Y/y
        if [[ -z "$create_forwards" ]] || [[ $create_forwards =~ ^[yY]$ ]]; then
            create_forwards="yes"
        else
            create_forwards="no"
        fi
    else
        create_forwards="no"
        warning "Port forwards require static IP. Skipping port forward creation."
    fi
    
    echo -e "\n${YELLOW}🎲 Generated Credentials:${NC}"
    echo -e "${CYAN}===============================================${NC}"
    echo -e "Username: ${GREEN}$username${NC}"
    echo -e "Password: ${GREEN}$password${NC}"
    if [[ "$ip_addr" == "*" ]]; then
        echo -e "IP Mode:  ${YELLOW}Auto-assign (dynamic)${NC}"
    else
        echo -e "Static IP: ${GREEN}$ip_addr${NC}"
    fi
    if [[ "$create_forwards" == "yes" ]]; then
        echo -e "Forwards:  ${GREEN}Yes (Winbox + API)${NC}"
    else
        echo -e "Forwards:  ${YELLOW}No${NC}"
    fi
    echo -e "${CYAN}===============================================${NC}\n"
    
    # Confirm creation
    echo -e "${YELLOW}Do you want to create this user? (y/N): ${NC}"
    read -r confirm
    if [[ ! $confirm =~ ^[yY]$ ]]; then
        info "User creation cancelled"
        return 0
    fi
    
    # Add user first
    if ! add_user_to_system "$username" "$password" "$ip_addr"; then
        error "Failed to create user. Aborting."
        return 1
    fi
    
    # Create port forwards if requested and we have static IP
    if [[ "$create_forwards" == "yes" ]] && [[ "$ip_addr" != "*" ]]; then
        echo -e "\n${YELLOW}Attempting to create port forwards...${NC}"
        
        local port_output
        if port_output=$(create_user_port_forwards "$username" "$ip_addr" 2>/dev/null); then
            local winbox_port api_port
            # Scan all output lines for the port pair pattern
            while IFS= read -r line; do
                if [[ "$line" =~ ^[0-9]+,[0-9]+$ ]]; then
                    IFS=',' read -r winbox_port api_port <<< "$line"
                fi
            done <<< "$port_output"
            
            # Verify we got valid port numbers
            if [[ "$winbox_port" =~ ^[0-9]+$ ]] && [[ "$api_port" =~ ^[0-9]+$ ]]; then
                echo -e "\n${GREEN}✓ Complete Setup Finished!${NC}"
                echo -e "${CYAN}===============================================${NC}"
                echo -e "${YELLOW}📋 Final Connection Details:${NC}"
                echo -e "Server IP:     ${GREEN}$PUBLIC_IP${NC}"
                echo -e "Username:      ${GREEN}$username${NC}"
                echo -e "Password:      ${GREEN}$password${NC}"
                echo -e "Static IP:     ${GREEN}$ip_addr${NC}"
                echo -e "Winbox Access: ${GREEN}$PUBLIC_IP:$winbox_port${NC}"
                echo -e "API Access:    ${GREEN}$PUBLIC_IP:$api_port${NC}"
                echo -e "${CYAN}===============================================${NC}"
                echo -e "${YELLOW}💡 Save these details safely!${NC}"
            else
                warning "Port forward created but port numbers could not be extracted from output"
            fi
        else
            error "Port forward setup failed."
            warning "User created successfully but port forwards could not be established."
        fi
    fi
    
    echo
}

add_user_to_system() {
    local username="$1" password="$2" ip_addr="$3"

    validate_username "$username" || { error "Invalid username"; return 1; }
    validate_password "$password" || { error "Invalid PPP password"; return 1; }
    if username_exists "$username"; then
        error "Username already exists."
        return 1
    fi
    [[ -f "$CHAP_SECRETS" && ! -L "$CHAP_SECRETS" ]] || {
        error "Unsafe or missing PPP credential file"
        return 1
    }
    umask 077
    if ! printf '%-20s *       %-20s %s\n' "$username" "$password" "$ip_addr" >> "$CHAP_SECRETS"; then
        error "Failed to append PPP user"
        return 1
    fi
    PSK_NEW_USERNAME="$username"
    log "PPP user created without restarting active xl2tpd sessions."
    info "New credentials apply to a new PPP authentication; test the client."
    return 0
}

add_user() {
    PSK_NEW_USERNAME=""
    echo -e "\n${CYAN}===============================================${NC}"
    echo -e "${CYAN}              Add L2TP User               ${NC}"
    echo -e "${BLUE}            Made by Mostech               ${NC}"
    echo -e "${PURPLE}        github.com/safrinnetwork        ${NC}"
    echo -e "${CYAN}===============================================${NC}\n"
    
    echo -e "${YELLOW}Choose creation method:${NC}"
    echo -e "   ${GREEN}[1]${NC} 🎲 Generate Random Username & Password"
    echo -e "   ${GREEN}[2]${NC} ✏️  Manual Username & Password Entry"
    echo -e "   ${GREEN}[0]${NC} ← Back to Main Menu"
    echo
    echo -e "${YELLOW}✨ Enter your choice (0-2): ${NC}"
    echo -ne "${GREEN}▶ ${NC}"
    read choice
    
    case $choice in
        1)
            echo -e "\n${CYAN}🎲 Generating Random User...${NC}\n"
            add_user_random
            ;;
        2)
            echo -e "\n${CYAN}✏️  Manual User Entry...${NC}\n"
            add_user_manual
            ;;
        0)
            return 0
            ;;
        *)
            error "Invalid option. Please try again."
            ;;
    esac
    if [[ -n "$PSK_NEW_USERNAME" ]]; then
        psk_choose_for_user "$PSK_NEW_USERNAME" ||
            warning "PPP user exists, but PSK sharing preference was not updated."
    fi
}
delete_user() {
    echo -e "\n${CYAN}=== Delete L2TP User ===${NC}"
    
    # List current users with numbers
    echo -e "\n${YELLOW}Current users:${NC}"
    local users_list=$(grep -v "^#" "$CHAP_SECRETS" | grep -v "^$")
    if [[ -z "$users_list" ]]; then
        warning "No users found!"
        return 1
    fi
    
    echo "$users_list" | nl -w2 -s'. '
    
    echo -e "\n${CYAN}Options:${NC}"
    echo "1. Enter username(s) directly: username1,username2"
    echo "2. Enter number(s): 1,7,3"
    echo "3. Enter 0 to cancel"
    
    read -p "Enter selection: " selection
    
    # Handle cancellation
    if [[ "$selection" == "0" ]]; then
        info "Deletion cancelled"
        return 0
    fi
    
    local users_to_delete=()
    
    # Check if input contains only numbers and commas
    if [[ "$selection" =~ ^[0-9,]+$ ]]; then
        # Number-based selection
        IFS=',' read -ra numbers <<< "$selection"
        local total_users=$(echo "$users_list" | wc -l)
        
        for num in "${numbers[@]}"; do
            num=$(echo "$num" | xargs) # trim whitespace
            if [[ "$num" -gt 0 && "$num" -le "$total_users" ]]; then
                local username=$(echo "$users_list" | sed -n "${num}p" | awk '{print $1}')
                users_to_delete+=("$username")
            else
                warning "Invalid number: $num (valid range: 1-$total_users)"
            fi
        done
    else
        # Username-based selection
        IFS=',' read -ra usernames <<< "$selection"
        for username in "${usernames[@]}"; do
            username=$(echo "$username" | xargs) # trim whitespace
            if grep -q "^$username\s" "$CHAP_SECRETS"; then
                users_to_delete+=("$username")
            else
                warning "User '$username' not found!"
            fi
        done
    fi
    
    # Check if any valid users to delete
    if [[ ${#users_to_delete[@]} -eq 0 ]]; then
        error "No valid users selected for deletion!"
        return 1
    fi
    
    # Show users to be deleted with their associated port forwards
    echo -e "\n${YELLOW}Users to be deleted:${NC}"
    local total_forwards_to_delete=0
    for user in "${users_to_delete[@]}"; do
        # Get user IP
        local user_ip=$(grep "^$user\s" "$CHAP_SECRETS" | awk '{print $4}')
        echo "• $user (IP: $user_ip)"
        
        # Find associated port forwards by username pattern and IP
        local related_forwards=()
        if [[ -f "$FORWARDS_CONFIG" ]]; then
            # Find forwards by username pattern (e.g., username-winbox, username-api)
            while IFS=':' read -r name ext_port int_ip int_port desc; do
                is_comment_or_empty "$name" && continue
                if [[ "$name" =~ ^$user- ]] || [[ "$int_ip" == "$user_ip" ]]; then
                    related_forwards+=("$name:$ext_port:$int_ip:$int_port:$desc")
                fi
            done < "$FORWARDS_CONFIG"
        fi
        
        if [[ ${#related_forwards[@]} -gt 0 ]]; then
            echo "  Related port forwards:"
            for forward in "${related_forwards[@]}"; do
                local fname=$(echo "$forward" | cut -d':' -f1)
                local fext=$(echo "$forward" | cut -d':' -f2)
                local fint_ip=$(echo "$forward" | cut -d':' -f3)
                local fint_port=$(echo "$forward" | cut -d':' -f4)
                local fdesc=$(echo "$forward" | cut -d':' -f5)
                echo "    - $fname: $fext → $fint_ip:$fint_port ($fdesc)"
                ((total_forwards_to_delete++))
            done
        fi
    done
    
    if [[ $total_forwards_to_delete -gt 0 ]]; then
        echo -e "\n${CYAN}Total port forwards to be deleted: $total_forwards_to_delete${NC}"
    fi
    
    # Confirm deletion
    read -p "Are you sure you want to delete these ${#users_to_delete[@]} user(s)? (y/N): " confirm
    if [[ $confirm != [yY] ]]; then
        info "Deletion cancelled"
        return 0
    fi
    
    # Delete users and their port forwards
    local deleted_count=0
    local total_forwards_deleted=0
    
    for username in "${users_to_delete[@]}"; do
        # Get user IP before deletion
        local user_ip=$(grep "^$username\s" "$CHAP_SECRETS" | awk '{print $4}')
        
        # Delete from chap-secrets
        if sed -i "/^$username\s/d" "$CHAP_SECRETS"; then
            log "User '$username' deleted from authentication"
            
            # Delete associated port forwards by username pattern and IP
            local forwards_deleted=0
            if [[ -f "$FORWARDS_CONFIG" ]]; then
                # Find and delete forwards by username pattern
                if grep -q "^$username-" "$FORWARDS_CONFIG" 2>/dev/null; then
                    # Count forwards before deletion
                    local forwards_count=$(grep -c "^$username-" "$FORWARDS_CONFIG" 2>/dev/null || echo 0)
                    
                    # Get port numbers for cleanup before deletion
                    local ports_to_cleanup=()
                    while IFS=':' read -r name ext_port int_ip int_port desc; do
                        [[ $name =~ ^$username- ]] && ports_to_cleanup+=("$ext_port")
                    done < <(grep "^$username-" "$FORWARDS_CONFIG" 2>/dev/null)
                    
                    # Delete from config
                    sed -i "/^$username-/d" "$FORWARDS_CONFIG"
                    forwards_deleted=$((forwards_deleted + forwards_count))
                fi
                
                # Find and delete forwards by IP (for cases where forwards don't follow username pattern)
                if [[ -n "$user_ip" && "$user_ip" != "*" ]]; then
                    # Get forwards with matching IP that weren't caught by username pattern
                    local ip_forwards=()
                    while IFS=':' read -r name ext_port int_ip int_port desc; do
                        is_comment_or_empty "$name" && continue
                        if [[ "$int_ip" == "$user_ip" ]] && [[ ! "$name" =~ ^$username- ]]; then
                            ip_forwards+=("$name:$ext_port")
                        fi
                    done < "$FORWARDS_CONFIG"
                    
                    # Delete IP-based forwards
                    for forward_info in "${ip_forwards[@]}"; do
                        local fname=$(echo "$forward_info" | cut -d':' -f1)
                        local fport=$(echo "$forward_info" | cut -d':' -f2)
                        
                        # Stop socat process
                        pkill -f "TCP4-LISTEN:$fport" 2>/dev/null
                        
                        # Remove firewall rule
                        firewall_del_rule -D INPUT -p tcp --dport "$fport" -j ACCEPT
                        
                        # Delete from config
                        sed -i "/^$fname:/d" "$FORWARDS_CONFIG"
                        ((forwards_deleted++))
                        log "Port forward '$fname' (IP: $user_ip) deleted"
                    done
                fi
                
                # Cleanup socat processes and firewall rules for username-based forwards
                for port in "${ports_to_cleanup[@]}"; do
                    [[ -n "$port" ]] || continue
                    pkill -f "TCP4-LISTEN:$port" 2>/dev/null
                    firewall_del_rule -D INPUT -p tcp --dport "$port" -j ACCEPT
                done
                
                if [[ $forwards_deleted -gt 0 ]]; then
                    log "Deleted $forwards_deleted port forward(s) for user '$username'"
                    total_forwards_deleted=$((total_forwards_deleted + forwards_deleted))
                fi
            fi
            
            ((deleted_count++))
        else
            error "Failed to delete user '$username'"
        fi
    done
    
    if [[ $deleted_count -gt 0 ]]; then
        info "Successfully deleted $deleted_count user(s)"
        
        if [[ $total_forwards_deleted -gt 0 ]]; then
            info "Successfully deleted $total_forwards_deleted related port forward(s)"
        fi
        
        # Restart services
        echo -e "\n${YELLOW}Restarting services...${NC}"
        systemctl restart xl2tpd
        
        # Restart port forwards if any remain or were deleted
        if [[ $total_forwards_deleted -gt 0 ]] || grep -q "^[^#]" "$FORWARDS_CONFIG" 2>/dev/null; then
            systemctl restart l2tp-forwards >/dev/null 2>&1
            info "Port forwarding service restarted"
        fi
        
        # Save firewall rules
        firewall_save_rules
        
        info "All services restarted successfully"
    else
        error "No users were deleted"
    fi
}

edit_user() {
    local username current_line current_pass current_ip new_password answer temp line first matches backup
    echo -e "\n=== Edit L2TP/PPP account and shared PSK preference ==="
    psk_client_tool list || return 1
    read -r -p "Username to edit: " username || return 1
    validate_username "$username" || { error "Invalid username."; return 1; }
    [[ -f "$CHAP_SECRETS" && ! -L "$CHAP_SECRETS" ]] || {
        error "Unsafe PPP credentials file"; return 1
    }
    current_line=$(awk -v u="$username" '$1==u {print; n++} END {if (n!=1) exit 1}' "$CHAP_SECRETS") || {
        error "PPP user not found or duplicate account."; return 1
    }
    current_pass=$(printf '%s\n' "$current_line" | awk '{print $3}')
    current_ip=$(printf '%s\n' "$current_line" | awk '{print $4}')
    echo "User: $username | PPP assigned IP: $current_ip | Password: [hidden]"
    echo "Changing the static IP is disabled in Phase 1: direct6/GRE/forwards may depend on it."
    read -r -s -p "New PPP password (empty keeps current): " new_password || return 1
    echo
    if [[ -n "$new_password" ]]; then
        validate_password "$new_password" || {
            error "Use 12-64 characters: letters, digits, @ . _ + = ! % : -"
            return 1
        }
        read -r -p "Type CHANGE PPP PASSWORD to confirm: " answer || return 1
        if [[ "$answer" != "CHANGE PPP PASSWORD" ]]; then
            info "Password change cancelled"
            return 1
        fi
        umask 077
        backup="$CHAP_SECRETS.backup.$(date +%s%N)"
        cp -p -- "$CHAP_SECRETS" "$backup" || return 1
        temp=$(mktemp "$CHAP_SECRETS.edit.XXXXXXXX") || return 1
        matches=0
        if ! while IFS= read -r line || [[ -n "$line" ]]; do
            read -r first _ <<< "$line"
            if [[ "$first" == "$username" ]]; then
                printf '%-20s *       %-20s %s\n' "$username" "$new_password" "$current_ip"
                matches=$((matches + 1))
            else
                printf '%s\n' "$line"
            fi
        done < "$CHAP_SECRETS" > "$temp"; then
            rm -f -- "$temp"
            error "Could not prepare replacement credentials"
            return 1
        fi
        # Count exact matches independently (the loop above is in a subshell).
        matches=$(awk -v u="$username" '$1==u {n++} END {print n+0}' "$CHAP_SECRETS")
        if [[ "$matches" != 1 ]]; then
            rm -f -- "$temp"
            error "Duplicate or missing account; unchanged"
            return 1
        fi
        chmod 600 -- "$temp"
        if ! mv -f -- "$temp" "$CHAP_SECRETS"; then
            rm -f -- "$temp"
            error "Could not commit credentials; backup retained"
            return 1
        fi
        info "PPP password stored. Existing sessions were NOT restarted."
        info "An already-connected PPP user must reconnect to authenticate with the new password."
    fi
    psk_choose_for_user "$username"
}

list_users() {
    echo -e "\n${CYAN}=== L2TP Users ===${NC}"
    
    # Get public IP
    local PUBLIC_IP=$(get_public_ip)
    
    # Check if there are any users
    local users_exist=false
    while read -r line; do
        is_comment_or_empty "$line" && continue
        users_exist=true
        break
    done < "$CHAP_SECRETS"
    
    if [[ "$users_exist" != "true" ]]; then
        warning "No L2TP users found!"
        return 1
    fi
    
    echo -e "\n${YELLOW}Server Public IP:${NC} $PUBLIC_IP"
    echo -e "${YELLOW}L2TP Port:${NC} 1701"
    echo
    
    local user_count=0
    while read -r line; do
        # Skip comments and empty lines
        is_comment_or_empty "$line" && continue
        
        ((user_count+=1))
        username=$(echo "$line" | awk '{print $1}')
        ip_addr=$(echo "$line" | awk '{print $4}')
        
        echo -e "${CYAN}[$user_count] User: ${GREEN}$username${NC}"
        echo -e "    Password: ${YELLOW}[hidden]${NC}"
        echo -e "    Internal IP: ${GREEN}$ip_addr${NC}"
        local status
        status=$(psk_client_tool status --username "$username" 2>/dev/null) ||
            status="PSK distribution status unavailable"
        echo "    $status"
        
        # Find related port forwards
        local forwards_found=false
        if [[ -f "$FORWARDS_CONFIG" ]]; then
            echo -e "    Port Forwards:"
            while IFS=':' read -r name ext_port int_ip int_port desc; do
                is_comment_or_empty "$name" && continue
                
                # Check if forward is related to this user (by username pattern or IP)
                if [[ "$name" =~ ^$username- ]] || [[ "$int_ip" == "$ip_addr" ]]; then
                    echo -e "      • ${YELLOW}$name${NC}: $PUBLIC_IP:${GREEN}$ext_port${NC} → $int_ip:$int_port ${PURPLE}($desc)${NC}"
                    forwards_found=true
                fi
            done < "$FORWARDS_CONFIG"
            
            if [[ "$forwards_found" != "true" ]]; then
                echo -e "      ${YELLOW}No port forwards configured${NC}"
            fi
        else
            echo -e "      ${YELLOW}No port forwards configured${NC}"
        fi
        
        echo
    done < "$CHAP_SECRETS"
    
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Total Users: ${GREEN}$user_count${NC}"
    
    # Count total port forwards
    local total_forwards=0
    if [[ -f "$FORWARDS_CONFIG" ]]; then
        while IFS=':' read -r name ext_port int_ip int_port desc; do
            is_comment_or_empty "$name" && continue
            ((total_forwards+=1))
        done < "$FORWARDS_CONFIG"
    fi
    
    echo -e "${YELLOW}Total Port Forwards: ${GREEN}$total_forwards${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    local chosen
    echo "For copy-ready details (including PPP password and global PSK),"
    echo "only reveal one offered user on a trusted local terminal."
    read -r -p "Username to reveal, or Enter to skip: " chosen || return 0
    if [[ -n "$chosen" ]]; then
        psk_client_tool show --username "$chosen" ||
            warning "Reveal failed, cancelled or PSK not offered."
    fi
}

show_ip_assignments() {
    echo -e "${YELLOW}📊 Current IP Assignments:${NC}"
    echo -e "${CYAN}---------------------------------------${NC}"
    
    local count=0
    while IFS= read -r line; do
        # Skip comments and empty lines
        is_comment_or_empty "$line" && continue
        
        local username=$(echo "$line" | awk '{print $1}')
        local ip=$(echo "$line" | awk '{print $4}')
        
        if [[ "$ip" == "*" ]]; then
            echo -e "   ${username}: ${YELLOW}Auto-assign${NC}"
        else
            echo -e "   ${username}: ${GREEN}$ip${NC}"
        fi
        ((count++))
    done < "$CHAP_SECRETS"
    
    if [[ $count -eq 0 ]]; then
        echo -e "   ${YELLOW}No users configured${NC}"
    fi
    
    echo -e "${CYAN}---------------------------------------${NC}"
    
    # Show next available IP
    local next_ip
    if next_ip=$(get_next_available_ip); then
        echo -e "${GREEN}Next available IP: $next_ip${NC}"
    else
        echo -e "${RED}No available IPs in range $VPN_IP_START-$VPN_IP_END${NC}"
    fi
    echo
}

