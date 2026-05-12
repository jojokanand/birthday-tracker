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

### Running the Firestore emulator locally

The integration tests require the [Firestore emulator](https://cloud.google.com/firestore/native/docs/emulator),
which itself needs **Java 21+** and the `cloud-firestore-emulator` gcloud
component. One-time setup:

```bash
brew install openjdk@21                                  # or any JDK 21+
gcloud components install cloud-firestore-emulator
```

Per-session:

```bash
# Start the emulator (keeps running in the foreground; Ctrl-C to stop).
gcloud emulators firestore start --host-port=localhost:8085

# In a second terminal:
export FIRESTORE_EMULATOR_HOST=localhost:8085
uv run pytest -m integration
```

When `FIRESTORE_EMULATOR_HOST` is unset, integration tests are skipped rather
than failing. CI starts the emulator automatically (see
`.github/workflows/ci-backend.yml`).

### Twilio integration tests (optional, local only)

Twilio's [test credentials](https://www.twilio.com/docs/iam/test-credentials)
let you exercise the API without sending real SMS. Magic number `+15005550006`
always succeeds.

```bash
export TWILIO_TEST_ACCOUNT_SID=ACxxxxxxxxxxxx     # from Twilio console
export TWILIO_TEST_AUTH_TOKEN=xxxxxxxxxxxx
uv run pytest tests/integration/adapters/test_twilio_integration.py
```

Without these env vars, the test is skipped.

### Gmail OAuth bootstrap (one-time)

The Gmail adapter sends mail as the owner's own Gmail user via OAuth 2.0 with
the `gmail.send` scope. First-time setup mints a refresh token; afterwards
the adapter runs unattended.

1. **Enable the Gmail API** for your GCP project:
   <https://console.cloud.google.com/apis/library/gmail.googleapis.com>
2. **Create OAuth client credentials** (type: *Desktop app*) at
   <https://console.cloud.google.com/apis/credentials> and download the
   resulting `client_secret.json`. Store it outside the repo, e.g.
   `~/.config/birthday-tracker/gmail_client_secret.json`.
3. **Run the bootstrap** — the first call opens a browser for consent and
   writes the refresh token to disk:

   ```bash
   uv run python -c "
   from birthday_tracker.adapters import load_gmail_credentials
   load_gmail_credentials(
       client_secrets_path='/absolute/path/to/client_secret.json',
       token_path='/absolute/path/to/gmail_token.json',
   )
   "
   ```

4. **Point the adapter at the cached token** via env vars (or `.env`):

   ```bash
   export GMAIL_OAUTH_CLIENT_SECRETS_PATH=/absolute/path/to/client_secret.json
   export GMAIL_OAUTH_TOKEN_PATH=/absolute/path/to/gmail_token.json
   export GMAIL_FROM_ADDRESS=you@example.com
   ```

5. **Run the integration test** (sends a real email — recipient is set via
   `GMAIL_INTEGRATION_TO`):

   ```bash
   export GMAIL_INTEGRATION_TO=you@example.com
   uv run pytest tests/integration/adapters/test_gmail_integration.py
   ```

In production, both the client secrets and the cached token live in Google
Secret Manager — see issue #7. **Never commit either file.**

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
