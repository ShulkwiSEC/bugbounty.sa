#!/bin/sh
set -eu

YES=0

usage() {
    cat <<'EOF'
Install or update the bbsa CLI, MCP server, and agent skill.

Usage: install.sh [--yes]

  -y, --yes   Skip the confirmation prompt (for agents and CI)
  -h, --help  Show this help
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        -y|--yes) YES=1 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'bbsa installer: unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ -t 1 ] && command -v tput >/dev/null 2>&1; then
    BOLD=$(tput bold 2>/dev/null || true)
    GREEN=$(tput setaf 2 2>/dev/null || true)
    RESET=$(tput sgr0 2>/dev/null || true)
else
    BOLD= GREEN= RESET=
fi

info() { printf '%s> %s%s\n' "$BOLD" "$*" "$RESET"; }
done_message() { printf '%s✓ %s%s\n' "$GREEN" "$*" "$RESET"; }
fail() { printf 'bbsa installer: %s\n' "$*" >&2; exit 1; }

printf '\n%sbbsa native installer%s\n\n' "$BOLD" "$RESET"
printf '  • installs uv when missing\n'
printf '  • installs or updates bbsa and bbsa-mcp\n'
printf '  • refreshes the bbsa skill for detected coding agents\n\n'

if [ "$YES" -eq 0 ]; then
    printf 'Continue? [y/N] ' >/dev/tty 2>/dev/null || fail "no terminal; rerun with --yes"
    read -r answer </dev/tty || fail "no terminal; rerun with --yes"
    case "$answer" in y|Y|yes|YES) ;; *) fail "installation cancelled" ;; esac
fi

if ! command -v uv >/dev/null 2>&1; then
    info "uv not found; installing it"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        fail "curl or wget is required to install uv"
    fi

    for bin_dir in "${UV_INSTALL_DIR:-}" "${XDG_BIN_HOME:-}" "$HOME/.local/bin" "$HOME/.cargo/bin"; do
        if [ -n "$bin_dir" ] && [ -x "$bin_dir/uv" ]; then
            PATH="$bin_dir:$PATH"
            export PATH
            break
        fi
    done
fi

command -v uv >/dev/null 2>&1 || fail "uv was installed but is not available on PATH"

info "installing the latest bugbounty.sa release"
uv tool install --force --refresh-package bugbounty.sa bugbounty.sa

bin_dir=$(uv tool dir --bin)
case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *)
        uv tool update-shell
        PATH="$bin_dir:$PATH"
        export PATH
        ;;
esac

[ -x "$bin_dir/bbsa" ] || fail "bbsa executable was not installed"
[ -x "$bin_dir/bbsa-mcp" ] || fail "bbsa-mcp executable was not installed"
installed_version=$("$bin_dir/bbsa" --version)

printf '\n'
done_message "$installed_version installed"
done_message "CLI: $bin_dir/bbsa"
done_message "MCP server: $bin_dir/bbsa-mcp"
printf '\nSet BUGBOUNTY_SA_TOKEN, then restart your shell and run: bbsa me\n'
