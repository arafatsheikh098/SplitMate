# SplitMate 💸

Shared expenses and balances for friend groups, settled to the last paisa.

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![CSP](https://img.shields.io/badge/CSP-Strict%20%7C%20Zero--CDN-green.svg)](https://developer.mozilla.org)
[![Tests](https://img.shields.io/badge/Tests-164%20Passed-brightgreen.svg)](tests/)
[![Languages](https://img.shields.io/badge/i18n-English%20%7C%20বাংলা-orange.svg)](splitmate/i18n/)
[![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-000000.svg)](https://github.com/astral-sh/ruff)

SplitMate is an opinionated, privacy-first web application for tracking group expenses: create a group, share an invite link, record expenses with granular split methods, search and filter transactions in real time, see who owes whom with visual debt transfer flows, and record settlements. Everything is computed directly from the immutable transaction ledger on every read, so balances can never drift.

---

## Highlights & Features

* **🎨 Modern Fintech Design System**
  * Modern interface styled in an **Emerald, Teal, and Slate** color palette with subtle border highlights and soft elevation shadows.
  * Instant **Dark & Light Mode** toggle with `localStorage` memory and automatic OS system preference detection.
  * Sticky group navigation bar displaying active group avatar, currency badge, logged-in member identity, admin pill, and fast action buttons (`+ Add expense`, `Settle up`).
  * Dynamic initial avatar circles with rotating palettes (`.avatar-color-0` to `5`), color-coded balance status cards (mint for owed, rose for owing, neutral for settled).
  * **100% Mobile-First Responsive:** Clean layout with zero horizontal overflow on screens down to 375px viewports (automated in Playwright E2E).

* **⚡ Dynamic Client-Side Interactions**
  * **Real-Time Expense Search & Category Filter Pills:** Instant live search across title, amount, or payer, paired with one-tap category filters (`🍽️ Food`, `🚗 Transport`, `🏠 Rent`, `💡 Utilities`, `✈️ Trip`, `🏷️ Other`) and dynamic subtotal recalculation.
  * **Visual Debt Settlement Flows:** Interactive transfer cards (`[Payer] ── ৳ Amount ──▶ [Recipient]`) with a 1-click **"Pay ৳X →"** button that pre-populates the settlement form via URL parameters.
  * **Digital Receipt View:** Itemized receipt view on expense details breaking down payers and individual split amounts.
  * **Smart Amount Auto-Sync:** Entering the expense total automatically synchronizes the payer share on single-payer entries.
  * **One-Click Share & Toast System:** Native clipboard utility for invite links and group summaries with animated toast alerts and fallback support.

* **💰 Paisa-Perfect Precision & Storage**
  * Every amount is stored strictly as **integer minor units** (e.g. BDT paisa, USD cents). Zero floating-point rounding errors anywhere on the wire.
  * Four split methods: **Equal**, **Exact**, **Percentage** (basis points), and **Shares** (integers).
  * The largest-remainder method ensures splits sum exactly to the cent; ties are deterministically broken starting at index `(expense_id mod participants)` in member-id order so no one is unfairly charged the extra paisa.

* **🤝 Greedy Settlement Algorithm**
  * Automatic settle-up plan matches the largest creditor with the largest debtor repeatedly. Resolves all group debts in at most $N - 1$ transfers.
  * Records real-world payments across multiple channels (💵 Cash, 📱 bKash, 📲 Nagad, 🏦 Bank transfer, 🏷️ Other).

* **🔒 Zero External CDNs & Enterprise Security**
  * **100% Self-Contained:** Zero external fonts, scripts, or CDN calls. Works completely offline or in air-gapped environments.
  * Strict Content Security Policy (`script-src 'self'`), `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `X-Content-Type-Options: nosniff`.
  * Secure `HttpOnly` + `SameSite=Lax` session cookies. Invite tokens are $\ge 128$-bit random strings stored as SHA-256 hashes (rotatable and revocable by admins).
  * Idempotency keys make expense retries safe; duplicate requests never double-charge.

* **🌐 Bilingual Support (English & বাংলা)**
  * Full native localization in English and Bengali with instant language switching via topbar toggle.

---

## Screenshots

| Home & Welcome | Create Group Form | Group Dashboard |
| :---: | :---: | :---: |
| ![Home](docs/screenshots/01_home.png) | ![Create Group](docs/screenshots/02_create_form.png) | ![Dashboard](docs/screenshots/03_group_dashboard.png) |
| *Modern hero with animated badge & quick-join* | *Quick-pick currency buttons (৳, $, €, £, ₹)* | *Personal balance status card and member ledger* |

| Member Join Link | Add Expense Form | Filterable Expenses List |
| :---: | :---: | :---: |
| ![Member Joined](docs/screenshots/04_bea_joined.png) | ![Expense Form](docs/screenshots/05_expense_form.png) | ![Expenses List](docs/screenshots/06_expense_saved.png) |
| *Clean invite acceptance and display name setup* | *Split method selector and participant checklist* | *Live instant search and category filter pills* |

| Net Balances | Share & Export | Activity Stream |
| :---: | :---: | :---: |
| ![Balances](docs/screenshots/07_balances.png) | ![Summary](docs/screenshots/08_summary.png) | ![Activity](docs/screenshots/09_activity.png) |
| *Color-coded member balances and visual debt flow* | *One-click summary copy and CSV export* | *Vertical audit stream with event icons* |

---

## Quick start (local, SQLite)

```sh
# 1. Clone and install
git clone <your-fork> splitmate
cd splitmate
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'

# 2. Configure
cp .env.example .env
# (the default SECRET_KEY is fine for local development)

# 3. Migrate + seed + run
.venv/bin/alembic upgrade head
.venv/bin/python -m splitmate.seed
.venv/bin/uvicorn splitmate.main:app --reload
```

Open <http://127.0.0.1:8000>. The seeded demo group has 4 members, 12 expenses, and 2 settlements ready to explore.

---

## Quick start (docker compose, Postgres)

```sh
cp .env.example .env
# Edit .env and set a real SECRET_KEY:
#   python3.12 -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up --build
```

The first run applies Alembic migrations and seeds the demo group. Data persists in the `db_data` named volume.

---

## Tests

```sh
.venv/bin/python -m pytest                # 164 unit / property tests
.venv/bin/python -m pytest tests/e2e      # Playwright end-to-end
.venv/bin/python -m ruff check .          # lint
```

The test suite is fully isolated: every test gets its own tmp-path SQLite database. The CI workflow (`.github/workflows/ci.yml`) runs the same suite against PostgreSQL to catch dialect-specific bugs.

---

## Project layout

```
splitmate/
  config.py            pydantic-settings, env-driven
  db.py                engine + session
  models.py            SQLModel ORM
  money.py             integer-only money helpers
  security.py          token hashing, rate limiter, session helpers
  security_headers.py  CSP + defensive headers middleware
  seed.py              demo seed (idempotent)
  split_engine/        pure logic for equal/exact/percentage/shares
  services/            business rules (groups, members, expenses, …)
  web/                 FastAPI routes (thin)
  templates/           Jinja2 .j2 templates & components
  static/              Vanilla CSS design system, dynamic JS, vendored HTMX
  i18n/                en.json, bn.json
  i18n.py              translation helper
  main.py              app factory

tests/                 pytest unit + property + e2e
alembic/               hand-written migrations
docs/screenshots/      Playwright walkthrough captures
```

---

## Production checklist

* `SECRET_KEY` is a fresh 32-byte random string (the app refuses to start in `ENV=production` with the placeholder key).
* `DATABASE_URL` points to a managed Postgres with backups.
* HTTPS is terminated upstream; cookies are `Secure` automatically in production.
* The seed (`python -m splitmate.seed`) is idempotent and safe to run on every deploy.

See [DEPLOY.md](DEPLOY.md) for Render / docker / bare-metal recipes and [smoke_test.sh](smoke_test.sh) for a post-deploy health check.

---

## License

MIT — see the file header on each module.
