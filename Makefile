.PHONY: install test lint migrate upgrade downgrade run fmt clean

PY := python3.12
PIP := $(PY) -m pip

install:
	$(PIP) install -e '.[dev]'

test:
	$(PY) -m pytest

test-cov:
	$(PY) -m pytest --cov=splitmate --cov-report=term-missing

lint:
	$(PY) -m ruff check .

fmt:
	$(PY) -m ruff format .

migrate:
	$(PY) -m alembic upgrade head

upgrade:
	$(PY) -m alembic upgrade head

downgrade:
	$(PY) -m alembic downgrade -1

run:
	$(PY) -m uvicorn splitmate.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov __pycache__ */__pycache__ *.db