# Deploy

SplitMate is a small FastAPI app with one database. There are two
official deployment paths; both are designed to be reproduced from a
fresh clone.

## Render (managed)

1. Push the repository to GitHub.
2. Create a new **Blueprint Instance** in Render and point it at
   this repo.  Render reads `render.yaml` and provisions the
   `splitmate` web service **and** the `splitmate-db` Postgres
   instance in one go.
3. Render generates a `SECRET_KEY` for you and wires `DATABASE_URL`
   to the new database.  The build runs `pip install -e '.[dev]'`
   and the start command runs migrations + seed + uvicorn.
4. Visit `https://<your-app>.onrender.com/health` to confirm the app
   is up.  Visit `https://<your-app>.onrender.com/` to see the home
   page.

Smoke test (after the app is up):

```sh
./smoke_test.sh https://<your-app>.onrender.com
```

## Self-hosted with docker compose

1. Copy `.env.example` to `.env` and set `SECRET_KEY` to a fresh
   `secrets.token_urlsafe(32)` value.
2. `docker compose up --build`
3. The first run applies Alembic migrations and seeds the demo
   group (4 members, 12 expenses, 2 settlements).
4. Open <http://localhost:8000>.

The `db` service is a Postgres 16 container; data persists in the
`db_data` named volume.  To reset:

```sh
docker compose down -v
docker compose up --build
```

## Bare-metal (uvicorn + Postgres)

```sh
# 1. Create a database and user
createdb splitmate
createuser splitmate

# 2. Install
pip install -e '.[dev]'

# 3. Configure
export ENV=production
export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
export DATABASE_URL=postgresql+psycopg://splitmate:...@localhost:5432/splitmate

# 4. Migrate + seed + start
alembic upgrade head
python -m splitmate.seed
gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 splitmate.main:app
```

## Production checklist

- `SECRET_KEY` is at least 32 random bytes (the app refuses to start
  with the placeholder in `ENV=production`).
- `DATABASE_URL` points to a managed Postgres with backups enabled.
- HTTPS is terminated upstream (Render, nginx, Caddy, …).  Cookies
  are `Secure` automatically when `ENV=production`.
- The seed (`python -m splitmate.seed`) is idempotent and is safe to
  run on every deploy; it is no-op when the demo group already
  exists.
