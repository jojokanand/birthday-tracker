# Infrastructure

> **Status:** placeholder. Dockerfiles and Cloud Run wiring are tracked in
> [issue #7](../../issues).

## Planned contents

- `Dockerfile.backend` — multi-stage build for the FastAPI service.
- `Dockerfile.frontend` — Next.js standalone output served by Node on Cloud Run.
- `terraform/` (optional) — declarative GCP resources: Firestore, Cloud Run
  services, Cloud Scheduler job, Secret Manager secrets, IAM bindings.
