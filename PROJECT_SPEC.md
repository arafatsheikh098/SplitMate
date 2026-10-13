PROJECT: SplitMate
PURPOSE: A group of friends records shared expenses and payments. The app shows each person's balance, who owes whom, and a short list of payments that settles everything. It must be exactly correct to the last paisa, fast on a slow phone connection, and easy to join.

IN SCOPE
F1 Groups and access: create a group (name, currency symbol, default BDT); the creator becomes admin. A group has a secret invite link (random token of at least 128 bits, stored hashed, rotatable and revocable by an admin). Joining means choosing a display name that is unique inside the group; the server then sets a signed session cookie (HttpOnly, SameSite=Lax, Secure in production). Recovery on a new device: an admin generates a one-time re-link code for a member (valid 24 hours, stored hashed, single use, rate-limited to 5 attempts per 15 minutes per IP and group). Admins can promote or demote other admins; a group always keeps at least one admin. Limits: at most 30 members and 5,000 expenses per group.
F2 Members: admins can add a "virtual" member (a friend who has not joined yet); a person can later claim that member through a re-link code. A member with a non-zero balance cannot be archived; archived members stay in history and cannot be added to new expenses.
F3 Expenses: title (max 100), amount (integer minor units), date, category (Food, Transport, Rent, Utilities, Trip, Other), optional note (max 300), one or more payers with amounts that sum to the total, and a split among participants by one of: equal, exact amounts, percentages (basis points, must total 100.00%), or shares (integers). Remainders from equal, percentage and share splits are distributed deterministically with the largest-remainder method so every split sums exactly to the total; ties are broken starting at index (expense id modulo participants) in member-id order so that no one is always charged the extra paisa. A client-generated idempotency key makes double-taps and retries create one expense.
F4 Balances: per member net balance = total paid minus total owed (expenses) adjusted by settlements. Balances are computed from the ledger on every read (no cached balances, so they cannot drift). The sum of all balances is always exactly zero.
F5 Settle-up plan: a greedy algorithm (match the largest creditor with the largest debtor, repeat) produces at most N-1 transfers that bring every balance to zero, in deterministic order. The README states that the true minimum number of transfers is a hard problem and this is a good practical approximation.
F6 Settlements: any member can record a payment (from, to, amount, method label: cash / bKash / Nagad / bank / other, date, optional note). It counts immediately and appears in the activity feed. No payment integration.
F7 Edit, delete and history: the creator or an admin can edit or soft-delete an expense or settlement; every change is recorded in the activity feed (who, what, before and after summary, time); an admin can restore a soft-deleted item. Activity is paginated.
F8 Sharing and export: a "copy summary" button that produces plain text suitable for pasting into a chat (group name, balances, settle-up plan); CSV export of expenses (cells beginning with = + - @ tab or CR are neutralized in text fields).
F9 Languages: English and Bangla UI with a toggle; all strings come from dictionaries; a test fails if the dictionaries differ in keys. Bangla text must be reviewed by a native reader.
F10 Operations: GET /health; security headers (CSP without inline scripts, X-Content-Type-Options, Referrer-Policy, frame-ancestors none); rate limits on join and re-link; custom 404/500 pages; no tokens in logs; idempotent demo seed (a 4-person trip with 12 expenses and 2 settlements); mobile-first UI with a total JavaScript size under 100 KB (excluding vendored HTMX).

OUT OF SCOPE
Email, SMS or push notifications, payment gateway or wallet integration, receipts or file uploads, recurring expenses, multiple currencies, debt simplification across groups, accounts that span groups, comments or chat, offline mode, a native mobile app, anything not listed above.

ALLOWED STACK
Python 3.12; FastAPI; uvicorn; SQLModel; Alembic; psycopg[binary]; pydantic-settings; Jinja2; python-multipart; Starlette SessionMiddleware; vendored HTMX (eval disabled); vanilla JavaScript ES modules; pytest, pytest-playwright, httpx, freezegun, hypothesis; ruff; Docker, docker compose; GitHub Actions.

GLOBAL ACCEPTANCE CRITERIA
G1 docker compose up --build serves the app; the demo seed loads; a fresh clone works from the README.
G2 For every split method, the parts always sum exactly to the total (property-based test over thousands of generated cases including 1-paisa amounts, 1 participant and 30 participants).
G3 For any generated ledger, the sum of balances is exactly zero, and applying the settle-up plan brings every balance to exactly zero using at most N-1 transfers (property-based test).
G4 A member of group A can never read or change anything in group B (route-discovery test with two groups).
G5 Posting the same idempotency key twice creates one expense.
G6 Recovery codes and invite tokens are single-purpose, stored hashed, rate-limited, and never appear in logs (tests).
G7 The English and Bangla dictionaries have identical keys.
G8 CI is green on PostgreSQL.

MILESTONES
M1 Foundation, money and i18n scaffold; M2 Groups, invites and member sessions; M3 Split engine (pure logic, no UI); M4 Expenses (API and UI); M5 Balances, settle-up and settlements; M6 History, activity feed and idempotency; M7 Sharing, export, Bangla UI, seed, end-to-end tests.
