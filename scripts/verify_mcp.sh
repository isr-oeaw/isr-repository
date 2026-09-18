#!/usr/bin/env bash
# Verify MCP endpoint reachability and API key authentication.
#
# Usage:
#   MCP_URL=https://isrrepository.dataplexity.eu/mcp API_KEY=your_full_key ./scripts/verify_mcp.sh
#   MCP_URL=http://localhost/mcp API_KEY=your_full_key ./scripts/verify_mcp.sh
#
# Create an API key in the app: Settings -> API keys (full key shown once).
#
# Optional: list keys on the server (prefix only, not the secret):
#   docker compose exec app python manage.py shell -c "
#   from user.models import APIKey
#   for k in APIKey.objects.select_related('user').all():
#       print(k.prefix, k.name, k.user.username, k.is_active, k.expires_at, k.last_used_at)
#   "

set -euo pipefail

MCP_URL="${MCP_URL:-http://localhost/mcp}"
API_KEY="${API_KEY:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

failures=0

check_status() {
    local label="$1"
    local expected="$2"
    local actual="$3"
    if [[ "$actual" == "$expected" ]]; then
        echo -e "${GREEN}OK${NC}  $label (HTTP $actual)"
    else
        echo -e "${RED}FAIL${NC}  $label (expected HTTP $expected, got HTTP $actual)"
        failures=$((failures + 1))
    fi
}

body_snippet() {
    local body="$1"
    if [[ ${#body} -gt 400 ]]; then
        echo "${body:0:400}..."
    else
        echo "$body"
    fi
}

mcp_post() {
    local payload="$1"
    local auth_header="${2:-}"
    if [[ -n "$auth_header" ]]; then
        curl -sS -w '\n%{http_code}' -X POST "$MCP_URL" \
            -H "Content-Type: application/json" \
            -H "Authorization: $auth_header" \
            -d "$payload"
    else
        curl -sS -w '\n%{http_code}' -X POST "$MCP_URL" \
            -H "Content-Type: application/json" \
            -d "$payload"
    fi
}

echo "MCP verification"
echo "  URL: $MCP_URL"
echo ""

# 1. Reachability (GET -> 405, no auth required)
echo "--- 1. Reachability (GET) ---"
get_response=$(curl -sS -w '\n%{http_code}' -X GET "$MCP_URL" || true)
get_body=$(echo "$get_response" | sed '$d')
get_status=$(echo "$get_response" | tail -n 1)
check_status "GET /mcp" "405" "$get_status"
echo "    Body: $(body_snippet "$get_body")"
echo ""

# 2. Unauthenticated POST (initialize -> 401)
echo "--- 2. Unauthenticated POST (initialize) ---"
init_payload='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
unauth_response=$(mcp_post "$init_payload" || true)
unauth_body=$(echo "$unauth_response" | sed '$d')
unauth_status=$(echo "$unauth_response" | tail -n 1)
check_status "POST initialize without API key" "401" "$unauth_status"
echo "    Body: $(body_snippet "$unauth_body")"
echo ""

if [[ -z "$API_KEY" ]]; then
    echo -e "${YELLOW}SKIP${NC}  Steps 3-5 (set API_KEY to test authenticated requests)"
    echo ""
    echo "Example authenticated initialize:"
    echo "  curl -sS -X POST '$MCP_URL' \\"
    echo "    -H 'Authorization: Bearer YOUR_API_KEY' \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '$init_payload'"
    echo ""
    if [[ "$failures" -gt 0 ]]; then
        exit 1
    fi
    exit 0
fi

AUTH_HEADER="Bearer ${API_KEY}"

# 3. Authenticated initialize
echo "--- 3. Authenticated initialize ---"
auth_init_response=$(mcp_post "$init_payload" "$AUTH_HEADER" || true)
auth_init_body=$(echo "$auth_init_response" | sed '$d')
auth_init_status=$(echo "$auth_init_response" | tail -n 1)
check_status "POST initialize with Bearer API key" "200" "$auth_init_status"
echo "    Body: $(body_snippet "$auth_init_body")"
if [[ "$auth_init_status" == "200" ]] && ! echo "$auth_init_body" | grep -q '2024-11-05'; then
    echo -e "${RED}FAIL${NC}  Expected protocolVersion 2024-11-05 in response"
    failures=$((failures + 1))
fi
echo ""

# 4. tools/list
echo "--- 4. tools/list ---"
tools_payload='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
tools_response=$(mcp_post "$tools_payload" "$AUTH_HEADER" || true)
tools_body=$(echo "$tools_response" | sed '$d')
tools_status=$(echo "$tools_response" | tail -n 1)
check_status "POST tools/list" "200" "$tools_status"
echo "    Body: $(body_snippet "$tools_body")"
if [[ "$tools_status" == "200" ]] && ! echo "$tools_body" | grep -q 'list_datasets'; then
    echo -e "${RED}FAIL${NC}  Expected list_datasets tool in response"
    failures=$((failures + 1))
fi
echo ""

# 5. ping
echo "--- 5. ping ---"
ping_payload='{"jsonrpc":"2.0","id":3,"method":"ping","params":{}}'
ping_response=$(mcp_post "$ping_payload" "$AUTH_HEADER" || true)
ping_body=$(echo "$ping_response" | sed '$d')
ping_status=$(echo "$ping_response" | tail -n 1)
check_status "POST ping" "200" "$ping_status"
echo "    Body: $(body_snippet "$ping_body")"
echo ""

echo "Copy-paste curl for initialize:"
echo "  curl -sS -X POST '$MCP_URL' \\"
echo "    -H 'Authorization: Bearer \$API_KEY' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '$init_payload'"
echo ""

if [[ "$failures" -gt 0 ]]; then
    echo -e "${RED}$failures check(s) failed.${NC}"
    exit 1
fi

echo -e "${GREEN}All checks passed.${NC}"
