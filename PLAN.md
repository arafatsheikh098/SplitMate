# PLAN.md — milestones

Each milestone names the files it will create and the tests it needs. Order matches `PROJECT_SPEC.md` MILESTONES.

## M1 — Foundation, money and i18n scaffold

**Files**

- `pyproject.toml` (deps pinned)
- `splitmate/__init__.py`
- `splitmate/main.py` (app factory, `/health`)
- `splitmate/config.py` (pydantic-settings, `.env.example`)
- `splitmate/db.py` (engine, session)
- `splitmate/models/__init__.py`
- `splitmate/models/group.py`, `member.py`, `expense.py`, `payer.py`, `split_part.py`, `settlement.py`, `activity.py`, `idempotency.py`
- `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_init.py`
- `splitmate/i18n/__init__.py` (t(key) helper, language toggle)
- `splitmate/i18n/en.json`, `splitmate/i18n/bn.json`
- `splitmate/money.py` (parse / format, integer-only)
- `splitmate/templates/base.html.j2` (Jinja base, vendored HTMX)
- `splitmate/static/vendor/htmx.min.js` (vendored)
- `Dockerfile` (non-root, HEALTHCHECK)
- `docker-compose.yml` (app + postgres)
- `Makefile`
- `.env.example`
- `.github/workflows/ci.yml` (Postgres service)
- `tests/test_money.py`
- `tests/test_i18n.py`
- `tests/test_health.py`
- `tests/conftest.py` (SQLite in-memory test engine)

**Acceptance tests**

- A1 `docker compose up --build` serves `/health` (CI runs the equivalent).
- A2 Alembic upgrade and downgrade on Postgres and SQLite.
- A3 Money-helper tests for "0.1", "1,250.50", "1250", ".5", "1e3" (rejected), negative, empty.
- A4 Test fails if en.json and bn.json differ in keys.
- A5 CI green.

## M2 — Groups, invites and member sessions

**Files**

- `splitmate/security.py` (token hashing, signed session helpers, rate-limit memory store)
- `splitmate/services/groups.py`, `members.py`, `invites.py`, `relink.py`
- `splitmate/web/deps.py` (`require_member`, `require_admin`)
- `splitmate/web/groups.py`, `join.py`, `members.py`, `admin.py`
- `splitmate/templates/groups/*.j2`
- `alembic/versions/0002_groups_members.py`
- `tests/test_groups.py`, `test_invites.py`, `test_relink.py`, `test_admin.py`, `test_isolation.py`, `test_limits.py`

**Acceptance tests**

- A1 Route-discovery test (every group-scoped route, two groups).
- A2 Rotating invite link makes old link return 404.
- A3 Duplicate display names rejected case-insensitive, trimmed.
- A4 Re-link code: single use, 24 h expiry (freezegun), 5-attempt rate limit.
- A5 Tokens and codes stored only as hashes; never appear in logs.
- A6 Last admin cannot be demoted.
- A7 Member and expense limits enforced.

## M3 — Split engine (pure logic, no UI)

**Files**

- `splitmate/split_engine/__init__.py` (public API)
- `splitmate/split_engine/equal.py`, `exact.py`, `percentage.py`, `shares.py`
- `splitmate/split_engine/largest_remainder.py` (reusable helper)
- `splitmate/split_engine/errors.py`
- `tests/test_split_equal.py`, `test_split_exact.py`, `test_split_percentage.py`, `test_split_shares.py`, `test_split_properties.py`

**Acceptance tests**

- A1 Property test: parts sum exactly, no negatives, parts within 1 unit of ideal real share.
- A2 Worked example: 1000 / 3 → 334/333/333 with extra unit moving with expense id.
- A3 Validation: exact amounts not summing, percentages not 10 000, empty participants, zero/negative shares, payers not summing.
- A4 1 participant and 30 participants.
- A5 Module imports nothing from web or db (import test).

## M4 — Expenses (API and UI)

**Files**

- `splitmate/services/expenses.py`
- `splitmate/web/expenses.py`
- `splitmate/templates/expenses/*.j2`
- `splitmate/static/js/split_form.js` (vanilla ES module)
- `tests/test_expenses_api.py`, `test_expenses_ui.py`, `test_split_form_js.py` (size guard), `test_xss.py`

**Acceptance tests**

- A1 Server recomputes every split (tampered-input test).
- A2 Member can add; non-member cannot.
- A3 Amounts stored as integers; UI never sends floats.
- A4 Archived members cannot be added.
- A5 Form works on 375 px; page JS < 100 KB excluding HTMX.
- A6 Title/note HTML escaped.

## M5 — Balances, settle-up and settlements

**Files**

- `splitmate/services/balances.py`
- `splitmate/services/settle.py`
- `splitmate/services/settlements.py`
- `splitmate/web/balances.py`, `settlements.py`
- `splitmate/templates/balances.j2`, `settlements/*.j2`
- `tests/test_balances.py`, `test_settle.py`, `test_settlements.py`, `test_settle_properties.py`

**Acceptance tests**

- A1 Property G3.
- A2 Plan deterministic.
- A3 Settlement immediately changes balances; applying plan zeroes balances.
- A4 Member with zero balance is never in the plan.
- A5 4-member 6-expense worked example.
- A6 Self / zero / negative / unknown members rejected.

## M6 — History, activity feed and idempotency

**Files**

- `splitmate/services/activity.py`
- `splitmate/services/idempotency.py`
- `splitmate/web/activity.py`
- `splitmate/templates/activity.j2`
- `alembic/versions/0006_idempotency.py`
- `tests/test_history.py`, `test_activity.py`, `test_idempotency.py` (incl. concurrency on Postgres)

**Acceptance tests**

- A1 Only creator or admin can edit/delete.
- A2 One activity row per create/edit/delete/restore.
- A3 Soft-deleted expense excluded from balances; restore returns them exactly.
- A4 Same idempotency key twice → one expense (including parallel on Postgres).
- A5 Pagination boundaries.
- A6 Editing recomputes split; balances stay balanced.

## M7 — Sharing, export, Bangla UI, seed, end-to-end tests

**Files**

- `splitmate/services/share.py`, `csv_export.py`
- `splitmate/web/share.py`, `export.py`
- `splitmate/templates/errors/404.j2`, `errors/500.j2`
- `splitmate/security_headers.py`
- `splitmate/seed.py` (idempotent demo seed)
- `tests/test_share.py`, `test_csv.py`, `test_security_headers.py`, `test_seed.py`, `test_rate_limits.py`
- `tests/e2e/test_e2e.py` (Playwright)
- `docs/screenshots/` (captured during CI / local)

**Acceptance tests**

- A1 Summary golden file in both languages.
- A2 CSV formula-injection neutralization.
- A3 CSP present, zero CSP errors in Playwright console.
- A4 No horizontal scroll at 375 px.
- A5 E2E: create group, join via invite, add unequal expense, balances match, settlement zeroes balances.
- A6 Seed runs twice without duplicates.
- A7 Join and re-link rate limits exercised in test.

## Step 4 — Hardening, fresh-clone, deploy prep, README, final audit

See project plan in the user-provided brief; tracked as Step 4.
