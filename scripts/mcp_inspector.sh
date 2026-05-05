#!/usr/bin/env bash
# Launch the MCP Inspector against one of this project's MCP servers.
#
# The inspector is a debugging UI for MCP servers. It connects to a server
# over stdio, lists its tools/resources/prompts, and lets you invoke them
# interactively. See https://github.com/modelcontextprotocol/inspector.
#
# Usage:
#   scripts/mcp_inspector.sh <server>          # truckstop | dat | fuel
#   scripts/mcp_inspector.sh -- <command...>   # inspect an arbitrary command
#
# Examples:
#   scripts/mcp_inspector.sh truckstop
#   scripts/mcp_inspector.sh dat
#   scripts/mcp_inspector.sh -- uv run python -m mcp_servers.fuel

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/mcp_inspector.sh <server>
       scripts/mcp_inspector.sh -- <command...>

Servers:
  truckstop    Truckstop.com load board MCP server
  dat          DAT load board / RateView MCP server
  fuel         Fuel price tracking MCP server

Pass `-- <command...>` to inspect any other stdio MCP server, e.g.:
  scripts/mcp_inspector.sh -- uv run python -m mcp_servers.custom

Requires Node.js (for npx) and the project's Python env (uv).
EOF
}

if [[ $# -eq 0 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if ! command -v npx >/dev/null 2>&1; then
    echo "error: npx not found. Install Node.js (https://nodejs.org)." >&2
    exit 1
fi

if [[ "$1" == "--" ]]; then
    shift
    if [[ $# -eq 0 ]]; then
        echo "error: no command provided after --" >&2
        usage
        exit 2
    fi
    exec npx --yes @modelcontextprotocol/inspector "$@"
fi

server="$1"
shift

case "$server" in
    truckstop|dat|fuel)
        module="mcp_servers.${server}"
        ;;
    *)
        echo "error: unknown server '$server'" >&2
        usage
        exit 2
        ;;
esac

exec npx --yes @modelcontextprotocol/inspector uv run python -m "$module" "$@"
