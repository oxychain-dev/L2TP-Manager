#!/usr/bin/env bash
# Optional pppd mapping hooks. Do NOT restart PPP/xl2tpd.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source_file="$SCRIPT_DIR/ppp-session-hook.py"

usage() {
    echo "Usage: $0 --check | --install"
    echo "Installation touches only optional pppd ip-up.d/ip-down.d scripts."
}

if [[ $# -ne 1 ]]; then
    usage
    exit 2
fi
case "$1" in
    --check|--install) ;;
    *) usage; exit 2 ;;
esac

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR: Python3 not available" >&2
    exit 1
}
[[ -f "$source_file" && ! -L "$source_file" ]] || {
    echo "ERROR: Hook source not a regular file" >&2
    exit 1
}
python3 -c 'import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))' "$source_file"

for part in ip-up.d ip-down.d; do
    directory="/etc/ppp/$part"
    dest="$directory/91-l2tp-manager-multiwan"
    [[ -d "$directory" && ! -L "$directory" ]] || {
        echo "ERROR: pppd hook directory unavailable: $directory" >&2
        exit 1
    }
    if [[ -e "$dest" || -L "$dest" ]]; then
        if [[ -L "$dest" || ! -f "$dest" ]] || ! cmp -s -- "$dest" "$source_file"; then
            echo "ERROR: Existing hook is different; refusing overwrite: $dest" >&2
            exit 1
        fi
    fi
done

if [[ "$1" == --check ]]; then
    echo "Hook prerequisites OK. No files changed."
    exit 0
fi
[[ "$(id -u)" == 0 ]] || {
    echo "ERROR: Root required to install pppd hooks" >&2
    exit 1
}

for part in ip-up.d ip-down.d; do
    dest="/etc/ppp/$part/91-l2tp-manager-multiwan"
    if [[ ! -e "$dest" ]]; then
        install -o root -g root -m 0755 -- "$source_file" "$dest"
        echo "Installed: $dest"
    else
        echo "Already installed: $dest"
    fi
done
echo "No xl2tpd/pppd restart, firewall modification or PSK operation performed."
echo "New PPP sessions now register verified PEERNAME and interface metadata."
