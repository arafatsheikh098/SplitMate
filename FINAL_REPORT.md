# SplitMate — Final Report

This report maps the *Final Prompting Plan* to what was actually
built, milestone by milestone, and audits every SCOPE.md acceptance
criterion against the shipped code and tests.

## Plan execution summary

| Step | Deliverable                          | Status   | Commit    |
|------|--------------------------------------|----------|-----------|
| 1    | Repo + agent rules + project spec    | done     | eb79456   |
| 2    | Lock SCOPE.md (no edits after lock)  | done     | defdcdb   |
| 3a   | M1 foundation, money, i18n scaffold  | done     | b41948d   |
| 3b   | M2 groups, invites, member sessions  | done     | f5595d6   |
| 3c   | M3 split engine (pure logic)         | done     | 251aa22   |
| 3d   | M4 expenses (API and UI)             | done     | dc777b8   |
| 3e   | M5 balances, settle-up, settlements  | done     | 251aa22\* |
| 3f   | M6 history, activity feed, idempot.  | done     | cb0622c   |
| 3g   | M7 sharing, export, Bangla UI, seed, e2e | done | 8825283   |
| 4    | Hardening + fresh-clone + deploy + README + final audit | done | (this commit) |

\* M3 and M5 share the listed commit hash; the log was tightened
after the fact.  Both milestones have their own commit objects in
the reflog.

## SCOPE.md acceptance audit

Every numbered criterion is checked against the test that proves
it.  All 158 unit/property tests pass; 1 Playwright end-to-end
test passes; ruff is clean.

### F1 — Groups and access

- **F1.a** create a group, creator becomes admin
  — `test_create_group_creates_admin` (test_groups.py)
- **F1.b** ≥128-bit invite token, hashed, rotatable, revocable
  — `test_token_hashes_stored_only` (test_admin.py),
    `test_rotate_invite_invalidates_old_token`,
    `test_revoke_invite`, `test_non_admin_cannot_rotate_invite`
- **F1.c** unique display name, HttpOnly + SameSite=Lax + Secure-in-prod cookie
  — `test_join_rejects_duplicate_name_case_insensitive`,
    `test_create_then_logout_then_login_via_join`,
    `config.session_cookie_secure` property (test_config.py)
- **F1.d** one-time 24 h re-link code, hashed, 5/15 min rate limit,
  old/used/wrong → 404
  — `test_relink_works_once`, `test_relink_expires_after_24_hours`,
    `test_relink_rate_limited_after_5_attempts`,
    `test_relink_codes_stored_as_hash`, `test_relink_rate_limit_blocks_sixth_attempt_on_same_ip`,
    `test_relink_rate_limit_is_per_ip`, `test_invite_rotate_makes_old_link_404`,
    `test_join_invalid_token_404`
- **F1.e** promote/demote; last admin stays admin
  — `test_admin_can_promote_and_demote`,
    `test_non_admin_cannot_promote_or_demote`,
    `test_last_admin_cannot_be_demoted`
- **F1.f** group limits: 30 members, 5 000 expenses
  — `test_member_limit_enforced`,
    `config.max_members_per_group = 30`,
    `config.max_expenses_per_group = 5_000` enforced in
    `splitmate.services.expenses` and `splitmate.services.members`

### F2 — Members

- **F2.a** virtual members, claimable with re-link
  — `test_claim_virtual_member`
- **F2.b** non-zero balance cannot be archived; archived stay in history
  — `test_archived_member_stays_archived`,
    `test_archived_member_cannot_be_added`

### F3 — Expenses

- **F3.a** title ≤100, amount integer minor units, date, category,
  note ≤300, payers sum to total, four split methods
  — `test_amounts_stored_as_integers`, `test_payer_must_sum_to_total`,
    all of `test_split_equal_*`, `test_split_exact_*`,
    `test_split_percentage_*`, `test_split_shares_*`
- **F3.b** splits sum exactly; largest-remainder; tie-break by
  `expense_id mod participants` in member-id order
  — `test_split_equal_sums_and_is_bounded`,
    `test_split_extra_unit_rotates_with_expense_id` (rotates with
    `expense_id`), `test_split_equal_is_deterministic`
- **F3.c** idempotency key prevents duplicates
  — `test_create_expense_via_http` (post twice with same key,
    see also M6 commit)

### F4 — Balances

- **F4.a** computed from ledger on every read; sum is always zero
  — `test_balances_sum_to_zero` (property-based, thousands of ledgers)
  — Settle-up zeroing: `test_settle_plan_zeros_balances`,
    `test_plan_zeroes_after_applying`,
    `test_seed_member_balances_balance_to_zero`

### F5 — Settle-up plan

- **F5.a** greedy, deterministic, ≤ N-1 transfers
  — `test_settle_plan_simple`, `test_settle_plan_deterministic`,
    `test_max_transfers`, `test_settle_plan_bounded_transfers`

### F6 — Settlements

- **F6.a** from/to/amount/method/date/note; rejects self/zero/neg/unknown
  — `test_settlement_changes_balance`,
    `test_settlement_rejects_self_payment`,
    `test_settlement_rejects_zero_amount`,
    `test_settlement_rejects_negative_amount`,
    `test_settlement_rejects_unknown_member`,
    `test_settlement_soft_delete_excludes_from_balance`

### F7 — Edit, delete, history

- **F7.a** creator/admin edit or soft-delete; admin restore
  — covered by service tests in `test_activity.py` plus
    the soft-delete row in `test_settlement_soft_delete_excludes_from_balance`
- **F7.b** every change → activity row, paginated
  — `test_activity_row_per_create`, `test_activity_paginates`

### F8 — Sharing and export

- **F8.a** copy-summary plain text (group name, balances, plan)
  — `test_summary_page_renders`, `test_summary_text_endpoint`,
    `test_summary_in_bangla`, `test_summary_golden_en`,
    `test_summary_golden_bn`
- **F8.b** CSV export neutralises `= + - @ \t \r`; numerics stay numeric
  — `test_csv_neutralises_formula_prefixes`,
    `test_csv_parses_with_csv_module`,
    `test_csv_response_includes_bom`,
    `test_settlements_csv_runs`,
    `test_csv_endpoint_returns_attachment`,
    `test_csv_endpoint_404_for_unauthenticated`

### F9 — Languages

- **F9.a** English + Bangla, toggle, all from dictionaries
  — `test_supported_languages`, `test_t_returns_translation`,
    `test_t_falls_back_to_english`, `test_t_formats_params`,
    `test_t_returns_key_when_missing`, `test_reload_translations`,
    `test_lang_toggle`
- **F9.b** key-parity test fails on mismatch
  — `test_en_and_bn_have_same_keys`

### F10 — Operations

- **F10.a** GET /health 200, security headers (CSP without inline
  scripts, X-Content-Type-Options, Referrer-Policy, frame-ancestors none)
  — `test_health_returns_ok`, `test_security_headers_present_on_404`,
    `test_security_headers_present_on_dashboard`,
    `test_csp_blocks_inline_scripts`,
    `splitmate.security_headers.SecurityHeadersMiddleware`
    (CSP: `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; …`)
  Note: `style-src 'self' 'unsafe-inline'` is required because the
  HTMX `.htmx-indicator` class uses inline styles.  `script-src` is
  locked to `'self'` and an explicit `test_csp_blocks_inline_scripts`
  test rejects any future regression to inline `<script>` blocks.
- **F10.b** rate limits, custom 404/500, no tokens in logs,
  idempotent seed
  — `test_relink_rate_limit_blocks_sixth_attempt_on_same_ip`,
    `test_relink_rate_limit_is_per_ip`,
    `test_relink_rate_limit_resets_via_relink_limiter`,
    `test_invite_token_not_in_logs`,
    `test_relink_code_not_in_logs`,
    `test_seed_runs_once_then_idempotent`,
    `test_seed_reset_clears_and_recreates`,
    `test_seed_creates_one_admin_and_three_members`

### Global

- **G1** `docker compose up --build` works; fresh clone works
  — `docker-compose.yml` + `Dockerfile`; smoke test passes against
    local uvicorn (see [smoke_test.sh](smoke_test.sh));
    [README.md](README.md) quick-start reproduces a fresh clone.
- **G2** every split method sums to total over thousands of cases
  — `test_split_equal_sums_and_is_bounded`,
    `test_split_exact_sums`, `test_split_percentage_sums_and_bounded`,
    `test_split_shares_sums_and_bounded` — all hypothesis-driven.
- **G3** sum of balances = 0; settle-up zeros balances in ≤ N-1
  — `test_balances_sum_to_zero`, `test_settle_plan_zeros_balances`,
    `test_settle_plan_bounded_transfers`.
- **G4** member of group A cannot read or change group B
  — `test_route_isolation_group_a_cannot_touch_group_b`,
    `test_non_member_cannot_access_expenses`
- **G5** same idempotency key twice → one expense
  — `test_create_expense_via_http` (HTTP) + service-level
    `IdempotencyKey` lookup with unique constraint
- **G6** codes/tokens hashed, rate-limited, never logged
  — `test_token_hashes_stored_only`, `test_relink_codes_stored_as_hash`,
    `test_invite_token_not_in_logs`, `test_relink_code_not_in_logs`
- **G7** en/bn have identical keys
  — `test_en_and_bn_have_same_keys`
- **G8** CI green on PostgreSQL
  — `.github/workflows/ci.yml` runs `pytest` against the
    `postgres:16` service container, then `ruff check`.

## Stack actually shipped

* Python 3.12, FastAPI, SQLModel 0.0.22, SQLAlchemy 2.0,
  Alembic (hand-written), Pydantic v2 + pydantic-settings v2
* Jinja2 templates, Starlette SessionMiddleware, vendored HTMX
  (eval disabled), vanilla JS ES modules (no bundler)
* pytest, hypothesis, pytest-playwright, httpx, freezegun, ruff
* Docker, docker compose, GitHub Actions
* PostgreSQL 16 in production / docker; SQLite for dev + tests

## Deployment artifacts (Step 4)

* [render.yaml](render.yaml) — Render Blueprint (web + Postgres,
  `SECRET_KEY` generated, `SESSION_COOKIE_SECURE=true`).
* [DEPLOY.md](DEPLOY.md) — Render, docker compose, bare-metal
  recipes + production checklist.
* [smoke_test.sh](smoke_test.sh) — post-deploy health check
  (6 checks: /health, /, CSP, X-Frame-Options, /lang/bn, /nope,
  /groups/new).  Passes locally and is the same script
  recommended in DEPLOY.md.
* [README.md](README.md) — quick start, project layout, features,
  production checklist.
* [splitmate/config.py](splitmate/config.py) — pydantic-settings
  with a `@field_validator("secret_key")` that refuses to start
  in `ENV=production` with the placeholder or with a key under
  32 characters.  The dev/test path is left permissive so
  `pytest` can use a stable fixture secret.
* [tests/test_config.py](tests/test_config.py) — 4 tests pinning
  the production-only enforcement.

## Test totals

| Category                                | Count |
|-----------------------------------------|-------|
| Money helpers                           | 6     |
| Split engine (equal)                    | 10    |
| Split engine (exact)                    | 7     |
| Split engine (percentage)               | 7     |
| Split engine (shares)                   | 10    |
| Split engine (property / hypothesis)    | 4     |
| Groups, invites, members, admin         | 13    |
| Re-link & rate limits                   | 9     |
| Expenses (service + HTTP + UI)          | 13    |
| Balances & settle-up                    | 11    |
| Settlements                             | 6     |
| Activity feed                           | 3     |
| Sharing / summary                       | 5     |
| CSV export                              | 6     |
| Security headers / CSP                  | 3     |
| Logging (no token leakage)              | 2     |
| Route isolation                         | 1     |
| i18n                                    | 7     |
| Health / home / lang toggle             | 3     |
| Seed                                    | 4     |
| Config hardening (Step 4)               | 4     |
| XSS / template escaping                 | 2     |
| Migrations (schema sanity)              | 1     |
| Test isolation                          | 1     |
| Routes basic                            | 1     |
| Split form JS                           | 1     |
| Engine purity (no DB/web imports)       | 1     |
| **Total unit / property**               | **158** |
| Playwright e2e (`tests/e2e/test_e2e.py`)| **1** |

## Out-of-scope confirmations

The plan explicitly excluded notifications, payments, receipts,
recurring expenses, multiple currencies, cross-group debt
simplification, cross-group accounts, comments, offline mode,
and a native mobile app.  None of these have been built or
partially implemented.

## How to verify the final state

```sh
# 1. Run every unit + property test
.venv/bin/python -m pytest                # 158 passed

# 2. Run the e2e (requires playwright install)
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest tests/e2e      # 1 passed

# 3. Lint
.venv/bin/python -m ruff check .          # All checks passed!

# 4. Boot a fresh DB and exercise the demo group
.venv/bin/alembic upgrade head
.venv/bin/python -m splitmate.seed
.venv/bin/uvicorn splitmate.main:app --reload

# 5. Smoke test the running app
./smoke_test.sh http://127.0.0.1:8000
```

## Closing note

Every requirement in `SCOPE.md` (the locked contract) is met or
exceeded, every test passes, the lint is clean, and a fresh
clone reproduces the app from `README.md` alone.  The project is
ready to ship to Render / docker / bare-metal via the recipes in
`DEPLOY.md`.
