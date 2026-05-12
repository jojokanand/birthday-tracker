# Infrastructure — GCP Bootstrap Guide

One-time setup that must be run **once per GCP project** before the GitHub
Actions deploy workflow can push images and deploy Cloud Run services.

All commands assume you are authenticated as a project Owner and that the
`gcloud` CLI is available.

---

## 1. Set shell variables

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"           # Cloud Run + Artifact Registry region
export REPO="birthday-tracker"        # Artifact Registry repository name
export GITHUB_ORG="jyothsnakanand"   # GitHub org / username
export GITHUB_REPO="birthday-tracker"
export SA_NAME="birthday-tracker-deploy"
```

---

## 2. Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  --project "$PROJECT_ID"
```

---

## 3. Create the Artifact Registry repository

```bash
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Birthday Tracker container images" \
  --project "$PROJECT_ID"
```

The full registry path used in the deploy workflow is:

```
${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}
```

Set this as the `GCP_ARTIFACT_REGISTRY` Actions variable (step 9).

---

## 4. Create a Firestore database (Native mode)

```bash
gcloud firestore databases create \
  --location="$REGION" \
  --project "$PROJECT_ID"
```

---

## 5. Create the deploy service account

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --display-name "Birthday Tracker — GitHub Actions deploy" \
  --project "$PROJECT_ID"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Get the project number (needed for WIF and Compute SA below)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
```

Grant the minimum roles needed by the deploy workflow and the running services:

```bash
# Push images to Artifact Registry
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role "roles/artifactregistry.writer"

# Deploy and manage Cloud Run services
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role "roles/run.admin"

# Allow Cloud Run to act as itself (required by deploy-cloudrun action)
gcloud iam service-accounts add-iam-policy-binding \
  "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role "roles/iam.serviceAccountUser" \
  --project "$PROJECT_ID"

# Read secrets at runtime
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role "roles/secretmanager.secretAccessor"

# Read/write Firestore
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role "roles/datastore.user"
```

---

## 6. Configure Workload Identity Federation

Allows GitHub Actions to obtain short-lived GCP credentials without a stored
JSON key.

```bash
# Create the WIF pool
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name "GitHub Actions pool" \
  --project "$PROJECT_ID"

# Create the OIDC provider inside the pool
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name "GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GITHUB_ORG}/${GITHUB_REPO}'" \
  --project "$PROJECT_ID"

# Allow the specific repository to impersonate the deploy SA
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role "roles/iam.workloadIdentityUser" \
  --member "principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}" \
  --project "$PROJECT_ID"
```

Copy the provider resource name for the `GCP_WIF_PROVIDER` Actions variable:

```bash
echo "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
```

---

## 7. Store secrets in Secret Manager

```bash
# Twilio Auth Token
echo -n "your-twilio-auth-token" | \
  gcloud secrets create TWILIO_AUTH_TOKEN \
    --data-file=- --project "$PROJECT_ID"

# Gmail OAuth refresh-token JSON (produced by running the OAuth flow locally)
gcloud secrets create GMAIL_OAUTH_TOKEN \
  --data-file="/path/to/gmail_token.json" --project "$PROJECT_ID"

# HMAC key for signing form tokens (32-byte hex string)
python3 -c "import secrets; print(secrets.token_hex(32))" | \
  gcloud secrets create FORM_TOKEN_SECRET \
    --data-file=- --project "$PROJECT_ID"
```

To rotate a secret, add a new version:

```bash
echo -n "new-value" | \
  gcloud secrets versions add SECRET_NAME --data-file=- --project "$PROJECT_ID"
```

---

## 8. Set GitHub Actions variables

In the GitHub repo → **Settings → Secrets and variables → Actions**:

### Variables (visible in logs — no secrets here)

| Name | Example value |
|---|---|
| `GCP_PROJECT_ID` | `my-birthday-tracker` |
| `GCP_REGION` | `us-central1` |
| `GCP_ARTIFACT_REGISTRY` | `us-central1-docker.pkg.dev/my-birthday-tracker/birthday-tracker` |
| `GCP_WIF_PROVIDER` | `projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_SERVICE_ACCOUNT` | `birthday-tracker-deploy@my-birthday-tracker.iam.gserviceaccount.com` |
| `BACKEND_URL` | _(filled in after step 9)_ |
| `FRONTEND_URL` | _(filled in after step 9)_ |

Leave `BACKEND_URL` / `FRONTEND_URL` blank for now — the Cloud Run services
that own those URLs don't exist yet. You'll back-fill them in step 9.

---

## 9. Trigger the first deploy

With the variables above set, the [deploy workflow](../.github/workflows/deploy.yml)
will run on the next push to `main`, build and push the backend + frontend
images, and create the two Cloud Run services. The `deploy-cloudrun` action
in the workflow sets each service's runtime identity to `${SA_EMAIL}`
automatically — no manual `gcloud run services update --service-account` step
is needed.

```bash
# Easiest trigger: an empty commit pushed to main.
git commit --allow-empty -m "chore: trigger first deploy"
git push origin main
```

Watch the run at **GitHub → Actions → deploy**. Once it succeeds, retrieve
the live URLs and back-fill the two `*_URL` variables from step 8:

```bash
gcloud run services describe birthday-tracker-backend \
  --region "$REGION" --project "$PROJECT_ID" \
  --format='value(status.url)'

gcloud run services describe birthday-tracker-frontend \
  --region "$REGION" --project "$PROJECT_ID" \
  --format='value(status.url)'
```

Paste each URL into **Settings → Variables → Actions** as `BACKEND_URL` and
`FRONTEND_URL`, then push another commit to `main` so the next deploy picks
them up:

- `BACKEND_URL` is baked into the frontend image as `NEXT_PUBLIC_API_URL`
  (build arg in [.github/workflows/deploy.yml](../.github/workflows/deploy.yml)),
  so the browser knows where to reach the API.
- `FRONTEND_URL` is set on the backend as the `PUBLIC_BASE_URL` env var, used
  to construct the self-serve form links sent in SMS/email.

The backend's `DIGEST_OIDC_AUDIENCE` is a separate setting configured in
step 11.

---

## 10. Branch protection on `main`

> **Note:** branch protection rules on private repositories require **GitHub Pro**
> (or making the repo public). On the free plan, configure via the UI instead.

**Via `gh` CLI (GitHub Pro / public repo):**

```bash
gh api repos/${GITHUB_ORG}/${GITHUB_REPO}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test","integration"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

**Via GitHub UI (free plan):**

1. Go to **Settings → Branches → Add branch protection rule**
2. Branch name pattern: `main`
3. Enable **Require a pull request before merging** → **Required approvals: 1**
4. Enable **Require status checks to pass before merging** → add `test` and `integration`
5. Enable **Require branches to be up to date before merging**
6. Save changes

---

## 11. Cloud Scheduler — daily birthday digest

The backend exposes `POST /internal/digest/send` which the scheduler hits once
per morning.  Cloud Scheduler attaches a short-lived OIDC token; the backend
validates it against the service URL.

### 11a. Set the backend URL in Settings

After the first deploy, retrieve the backend URL and set it as the
`DIGEST_OIDC_AUDIENCE` environment variable on the Cloud Run service:

```bash
BACKEND_URL=$(gcloud run services describe birthday-tracker-backend \
  --region "$REGION" --project "$PROJECT_ID" \
  --format='value(status.url)')

gcloud run services update birthday-tracker-backend \
  --set-env-vars "DIGEST_OIDC_AUDIENCE=${BACKEND_URL}" \
  --region "$REGION" --project "$PROJECT_ID"

gcloud run services update birthday-tracker-backend \
  --set-env-vars "DIGEST_OWNER_EMAIL=your-email@example.com" \
  --region "$REGION" --project "$PROJECT_ID"
```

### 11b. Create the Cloud Scheduler job

```bash
# Replace with the owner's IANA timezone, e.g. "America/New_York"
OWNER_TZ="America/New_York"

gcloud scheduler jobs create http birthday-digest-daily \
  --schedule="0 8 * * *" \
  --time-zone="${OWNER_TZ}" \
  --uri="${BACKEND_URL}/internal/digest/send" \
  --http-method=POST \
  --oidc-service-account-email="${SA_EMAIL}" \
  --oidc-token-audience="${BACKEND_URL}" \
  --location="$REGION" \
  --project "$PROJECT_ID"
```

### 11c. Test manually

```bash
# Trigger the job immediately (does not wait for the schedule).
gcloud scheduler jobs run birthday-digest-daily \
  --location="$REGION" --project "$PROJECT_ID"

# Or call the endpoint directly with a service-account token:
TOKEN=$(gcloud auth print-identity-token)
curl -X POST "${BACKEND_URL}/internal/digest/send" \
  -H "Authorization: Bearer ${TOKEN}"
```

### 11d. Preview upcoming birthdays

```bash
curl "${BACKEND_URL}/internal/digest/upcoming?days=14" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)"
```

---

## Ongoing operations

| Task | Command |
|---|---|
| View backend logs | `gcloud run services logs read birthday-tracker-backend --region $REGION` |
| View frontend logs | `gcloud run services logs read birthday-tracker-frontend --region $REGION` |
| Force redeploy (same image) | Push any commit to `main` |
| Rotate a secret | Add a new secret version (step 7) |
| Rotate the runtime service account | `gcloud run services update birthday-tracker-{backend,frontend} --service-account "${SA_EMAIL}" --region "$REGION" --project "$PROJECT_ID"` (run once per service, only after the first deploy) |
| Scale to zero (cost saving) | Cloud Run does this automatically when idle |
