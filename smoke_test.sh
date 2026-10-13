#!/usr/bin/env bash
# Smoke test for a live SplitMate deployment.
#
# Usage::
#
#     ./smoke_test.sh https://splitmate.example.com
#
# Exits 0 if every check passes, non-zero on the first failure.

set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
echo ">> smoke test against $BASE"

check() {
  local desc="$1"
  shift
  if "$@"; then
    echo "  ok  $desc"
  else
    echo "  FAIL $desc"
    exit 1
  fi
}

# /health returns 200 and "ok".
check "GET /health returns 200" \
  bash -c "curl -fsS '$BASE/health' | grep -q '\"status\":\"ok\"'"

# Home page renders.
check "GET / renders the home page" \
  bash -c "curl -fsS '$BASE/' | grep -q 'SplitMate'"

# Security headers are present.
check "CSP header is set" \
  bash -c "curl -fsS -D - -o /dev/null '$BASE/' | grep -i '^content-security-policy:'"

check "X-Frame-Options is DENY" \
  bash -c "curl -fsS -D - -o /dev/null '$BASE/' | grep -i '^x-frame-options:.*DENY'"

# Language toggle (POST /lang/bn sets the cookie).
check "POST /lang/bn returns 303" \
  bash -c "curl -fsS -X POST -o /dev/null -w '%{http_code}' '$BASE/lang/bn' | grep -q '^303$'"

# 404 page renders a custom error.
check "GET /nope returns 404" \
  bash -c "curl -fsS -o /dev/null -w '%{http_code}' '$BASE/nope' | grep -q '^404$'"

# JSON /groups is reachable only as HTML (no API surface to leak).
check "GET /groups/new renders" \
  bash -c "curl -fsS '$BASE/groups/new' | grep -qi 'create'"

echo ">> all smoke checks passed"
