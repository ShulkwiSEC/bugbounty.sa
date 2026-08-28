#!/usr/bin/env bash

# Accept the common `curl ... | sh` form, while keeping the interactive UI in Bash.
if [ -z "${BASH_VERSION:-}" ]; then
    command -v bash >/dev/null 2>&1 || {
        printf 'bbsa installer: bash is required\n' >&2
        exit 1
    }
    if [ -f "$0" ]; then
        exec bash "$0" "$@"
    elif command -v curl >/dev/null 2>&1; then
        exec bash -c 'curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/install.sh | bash -s -- "$@"' sh "$@"
    elif command -v wget >/dev/null 2>&1; then
        exec bash -c 'wget -qO- https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/install.sh | bash -s -- "$@"' sh "$@"
    else
        printf 'bbsa installer: curl or wget is required\n' >&2
        exit 1
    fi
fi

set -euo pipefail

YES=0
CURSOR_HIDDEN=0
AGENTS=("Claude Code" "Codex" "AGY" "OpenCode")
SELECTED=(0 0 0 0)

usage() {
    cat <<'EOF'
Install or update the bbsa CLI, MCP server, and agent skill.

Usage: install.sh [--yes]

  -y, --yes   Skip prompts and print setup for every agent
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

restore_cursor() {
    if [ "$CURSOR_HIDDEN" -eq 1 ]; then
        printf '\033[?25h' >/dev/tty 2>/dev/null || true
    fi
}
trap restore_cursor EXIT

render_agents() {
    local i marker box
    for i in "${!AGENTS[@]}"; do
        marker=" "
        box=" "
        [ "$i" -eq "$1" ] && marker="›"
        [ "${SELECTED[$i]}" -eq 1 ] && box="x"
        printf '  %s [%s] %s\n' "$marker" "$box" "${AGENTS[$i]}" >/dev/tty
    done
    printf '  ↑/↓ move  Space select  A all  Enter continue\n' >/dev/tty
}

select_agents() {
    local cursor=0 key rest i all next lines
    lines=$((${#AGENTS[@]} + 1))
    printf '\nSelect agents to configure:\n' >/dev/tty
    CURSOR_HIDDEN=1
    printf '\033[?25l' >/dev/tty
    render_agents "$cursor"

    while true; do
        IFS= read -rsn1 key </dev/tty || fail "could not read agent selection"
        if [ "$key" = $'\033' ]; then
            rest=""
            IFS= read -rsn2 -t 0.1 rest </dev/tty || true
            key+="$rest"
        fi
        case "$key" in
            $'\033[A') cursor=$(((cursor + ${#AGENTS[@]} - 1) % ${#AGENTS[@]})) ;;
            $'\033[B') cursor=$(((cursor + 1) % ${#AGENTS[@]})) ;;
            ' ') SELECTED[$cursor]=$((1 - SELECTED[$cursor])) ;;
            a|A)
                all=1
                for i in "${SELECTED[@]}"; do [ "$i" -eq 0 ] && all=0; done
                next=$((1 - all))
                for i in "${!SELECTED[@]}"; do SELECTED[$i]=$next; done
                ;;
            '') break ;;
            *) continue ;;
        esac
        printf '\033[%dA\r' "$lines" >/dev/tty
        render_agents "$cursor"
    done

    restore_cursor
    CURSOR_HIDDEN=0
}

skill_setup() {
    local path=$1
    if [ -f "$HOME/$path/SKILL.md" ]; then
        printf 'Skill: already installed at ~/%s/SKILL.md\n' "$path"
    else
        printf 'Skill:\nmkdir -p "$HOME/%s" && curl -fsSL https://raw.githubusercontent.com/ShulkwiSEC/bugbounty.sa/main/src/bbsa/SKILL.md -o "$HOME/%s/SKILL.md"\n' "$path" "$path"
    fi
}

print_agent_setup() {
    printf '\n%sAgent setup — copy and paste%s\n' "$BOLD" "$RESET"
    printf '\nFirst set your token:\nexport BUGBOUNTY_SA_TOKEN="your-token"\n'

    if [ "${SELECTED[0]}" -eq 1 ]; then
        printf '\n%sClaude Code%s\nMCP:\n' "$BOLD" "$RESET"
        printf '%s\n' 'claude mcp add --scope user --transport stdio bugbounty-sa --env BUGBOUNTY_SA_TOKEN="$BUGBOUNTY_SA_TOKEN" -- bbsa-mcp'
        skill_setup '.claude/skills/bbsa'
    fi

    if [ "${SELECTED[1]}" -eq 1 ]; then
        printf '\n%sCodex%s\nMCP:\n' "$BOLD" "$RESET"
        printf '%s\n' 'codex mcp add bugbounty-sa --env BUGBOUNTY_SA_TOKEN="$BUGBOUNTY_SA_TOKEN" -- bbsa-mcp'
        skill_setup '.codex/skills/bbsa'
    fi

    if [ "${SELECTED[2]}" -eq 1 ]; then
        printf '\n%sAGY (Antigravity CLI)%s\nMCP:\n' "$BOLD" "$RESET"
        printf '%s\n' 'agy mcp add --env BUGBOUNTY_SA_TOKEN="$BUGBOUNTY_SA_TOKEN" bugbounty-sa bbsa-mcp'
        skill_setup '.gemini/antigravity-cli/skills/bbsa'
    fi

    if [ "${SELECTED[3]}" -eq 1 ]; then
        printf '\n%sOpenCode%s\nAdd this server to ~/.config/opencode/opencode.json:\n' "$BOLD" "$RESET"
        cat <<'EOF'
{
  "mcp": {
    "bugbounty-sa": {
      "type": "local",
      "command": ["bbsa-mcp"],
      "environment": {"BUGBOUNTY_SA_TOKEN": "{env:BUGBOUNTY_SA_TOKEN}"}
    }
  }
}
EOF
        skill_setup '.config/opencode/skills/bbsa'
    fi
}

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
uv tool install --quiet --force --refresh-package bugbounty.sa bugbounty.sa

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

if [ "$YES" -eq 1 ]; then
    SELECTED=(1 1 1 1)
else
    select_agents
fi
print_agent_setup

printf '\nRestart your agent after adding MCP or skill configuration.\n'
