# Birthday Tracker — Project Plan

> **Status:** Living document. Updated as decisions change. Each phase below
> corresponds to a GitHub issue; closing the issue updates this plan.

## 1. Goal

Build a personal birthday tracker that:
1. Sends a contact a secure self-serve link via SMS (Twilio) or email (Gmail API)
   asking for: full name, preferred first name, address, and birthday.
2. Stores submitted responses in Google Firestore.
3. Presents the data in a Next.js dashboard the owner can use to view upcoming
   birthdays and trigger new collection requests.
4. Sends the owner a daily digest of upcoming birthdays via Cloud Scheduler.

## 2. Architecture

```
┌──────────────┐      ┌─────────────────┐      ┌──────────────┐
│ Next.js      │ ───▶ │ FastAPI         │ ───▶ │ Firestore    │
│ Dashboard    │ HTTP │ on Cloud Run    │      │ (NoSQL)      │
│ (Cloud Run)  │      │                 │      └──────────────┘
└──────────────┘      │   ┌──────────┐  │
                      │   │ Twilio   │  │ ──▶ SMS to contacts
                      │   │ Gmail API│  │ ──▶ Email to contacts
                      │   └──────────┘  │
                      │                 │      ┌──────────────┐
                      │  Cloud          │ ───▶ │ Secret Mgr   │
                      │  Scheduler      │      └──────────────┘
                      │  (daily digest) │
                      └─────────────────┘
```

## 3. Technology choices and rationale

| Concern | Choice | Why |
|---|---|---|
| Python version | 3.12.11 via `pyenv` | LTS, broad lib support; pyenv keeps it isolated from system Python |
| Dependency mgr | `uv` (also `uvx` for one-offs) | Fast, lockfile-based, reproducible; respects pyenv-selected interpreter |
| Backend framework | FastAPI | Async, auto-generates OpenAPI from type hints, Pydantic-native |
| Validation | Pydantic v2 | Type-safe DTOs shared between API and tests |
| Database | Firestore | Serverless NoSQL on GCP, free tier covers personal use, no migrations |
| Compute | Cloud Run | Scales to zero, container-based, HTTPS by default |
| Secrets | Google Secret Manager | Native IAM, never store creds in git |
| SMS | Twilio | De facto standard, free trial, simple Python SDK |
| Email | Gmail API (OAuth) | Sends from the owner's own Gmail; no separate ESP needed |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui | Industry-standard React stack, polished UI quickly |
| Scheduling | Cloud Scheduler → Cloud Run | Cron-as-a-service for daily digest |
| Testing | pytest + pytest-asyncio + pytest-cov + httpx + Firestore emulator + Playwright | Unit, integration, and E2E coverage |
| Lint/format/types | ruff + mypy + pre-commit | Fast, opinionated, fail in CI |
| Auto-docs | Sphinx (Google-style docstrings) + OpenAPI + TypeDoc | Every function gets a docstring; docs build in CI |
| CI/CD | GitHub Actions → Cloud Run | Tests on PR; deploy on merge to `main` |
| Issue tracking | GitHub Issues | All future work lands as an issue first |

## 4. Project structure

```
birthday-tracker/
├── README.md
├── PROJECT_PLAN.md              # this file
├── .python-version              # pyenv pin: 3.12.11
├── .gitignore
├── .pre-commit-config.yaml
├── .github/
│   ├── workflows/
│   │   ├── ci-backend.yml
│   │   └── ci-frontend.yml
│   └── ISSUE_TEMPLATE/
│       ├── task.md
│       └── bug.md
├── backend/
│   ├── pyproject.toml           # uv-managed
│   ├── README.md
│   ├── src/birthday_tracker/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry
│   │   ├── api/                 # routers (contacts, requests, health)
│   │   ├── core/                # settings, logging, security
│   │   ├── models/              # Pydantic models (Contact, CollectionRequest)
│   │   ├── services/            # business logic
│   │   └── adapters/            # twilio, gmail, firestore wrappers
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/         # uses Firestore emulator
│   │   └── conftest.py
│   └── docs/                    # Sphinx
├── frontend/                    # populated in issue #6
│   └── README.md
├── infra/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── README.md
└── scripts/
    ├── dev.sh
    └── deploy.sh
```

## 5. Phased delivery

Each phase is its own GitHub issue. PRs reference and close their issue.

| # | Issue | Description |
|---|---|---|
| 1 | Repo scaffolding | git init, pyenv, uv, pre-commit, CI skeleton, this plan |
| 2 | Backend skeleton | FastAPI app, health endpoint, Pydantic models, Sphinx |
| 3 | Firestore adapter + integration tests | Adapter behind interface, emulator-based tests |
| 4 | Notification adapters | Twilio + Gmail API wrappers behind a notifier interface |
| 5 | Self-serve form endpoint | Public token-protected route the contact fills out |
| 6 | Frontend dashboard | Next.js scaffolded, list/upcoming/create-request views |
| 7 | GCP deploy | Dockerfiles, Cloud Run, Secret Manager, GH Actions deploy |
| 8 | Scheduled digest | Cloud Scheduler hits backend → emails owner upcoming birthdays |
| 9 | E2E tests | Playwright happy path against staging |

## 6. Testing strategy

- **Unit tests** (`backend/tests/unit/`): Pure logic, mock all I/O. Aim ≥ 90% coverage on `services/`.
- **Integration tests** (`backend/tests/integration/`): FastAPI `TestClient` + Firestore emulator + mocked Twilio/Gmail.
- **Contract tests**: Pydantic models double as the contract; OpenAPI snapshot test guards against accidental breaks.
- **E2E tests** (`frontend/tests/e2e/`): Playwright drives the dashboard against a live (or emulated) backend.
- **CI gate**: ruff + mypy + pytest must pass on every PR.

## 7. Documentation strategy

- Every Python function has a Google-style docstring (Args/Returns/Raises). Sphinx + napoleon renders `backend/docs/` site.
- FastAPI auto-publishes OpenAPI at `/docs` and `/redoc`.
- TypeScript components get TSDoc comments; TypeDoc builds the frontend reference.
- `README.md` and `PROJECT_PLAN.md` are the human entry points; both updated on every phase merge.

## 8. Operational notes

- Pyenv selects Python via `.python-version`. Do not use system Python.
- All secrets live in GCP Secret Manager — never committed.
- Branch protection: `main` requires green CI + 1 review (set up in issue #1 or #7).
