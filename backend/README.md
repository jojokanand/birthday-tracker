# Backend — Birthday Tracker API

FastAPI service that owns contact storage, outbound notifications, and the
self-serve form endpoint.

## Quick start

```bash
# pyenv selects 3.12.11 via the repo-root .python-version
cd backend
uv sync --extra dev               # creates .venv using pyenv's Python
uv run uvicorn birthday_tracker.main:app --reload
# → http://localhost:8000/docs (Swagger UI)
# → http://localhost:8000/redoc (ReDoc)
```

## Tests

```bash
uv run pytest                                   # unit + integration
uv run pytest -m unit                           # fast unit only
uv run pytest -m integration                    # needs Firestore emulator
uv run pytest --cov-report=html                 # HTML coverage report at htmlcov/
```

To run the Firestore emulator locally:

```bash
gcloud emulators firestore start --host-port=localhost:8080
export FIRESTORE_EMULATOR_HOST=localhost:8080
uv run pytest -m integration
```

## Lint, types, docs

```bash
uv run ruff check .
uv run ruff format .
uv run mypy
uv run sphinx-build -b html docs docs/_build/html
```

## Layout

```
src/birthday_tracker/
├── main.py           # FastAPI app entry
├── api/              # HTTP routers
├── core/             # config, logging, security primitives
├── models/           # Pydantic models (Contact, CollectionRequest, ...)
├── services/         # business logic (issue collection request, parse response)
└── adapters/         # external systems (firestore, twilio, gmail)
```
