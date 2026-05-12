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

## 8. Set the Cloud Run service identity

Both Cloud Run services must run as the deploy service account so they can
access Firestore and Secret Manager at runtime. The `deploy-cloudrun` action
in the workflow sets this automatically; to configure it manually:

```bash
gcloud run services update birthday-tracker-backend \
  --service-account "${SA_EMAIL}" \
  --region "$REGION" --project "$PROJECT_ID"

gcloud run services update birthday-tracker-frontend \
  --service-account "${SA_EMAIL}" \
  --region "$REGION" --project "$PROJECT_ID"
```

---

## 9. Set GitHub Actions variables

In the GitHub repo → **Settings → Secrets and variables → Actions**:

### Variables (visible in logs — no secrets here)

| Name | Example value |
|---|---|
| `GCP_PROJECT_ID` | `my-birthday-tracker` |
| `GCP_REGION` | `us-central1` |
| `GCP_ARTIFACT_REGISTRY` | `us-central1-docker.pkg.dev/my-birthday-tracker/birthday-tracker` |
| `GCP_WIF_PROVIDER` | `projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_SERVICE_ACCOUNT` | `birthday-tracker-deploy@my-birthday-tracker.iam.gserviceaccount.com` |
| `BACKEND_URL` | `https://birthday-tracker-backend-xxxx-uc.a.run.app` |
| `FRONTEND_URL` | `https://birthday-tracker-frontend-xxxx-uc.a.run.app` |

> `BACKEND_URL` and `FRONTEND_URL` are known after the first successful deploy.
> Use placeholder values initially, then update once the services are live.

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

## Ongoing operations

| Task | Command |
|---|---|
| View backend logs | `gcloud run services logs read birthday-tracker-backend --region $REGION` |
| View frontend logs | `gcloud run services logs read birthday-tracker-frontend --region $REGION` |
| Force redeploy (same image) | Push any commit to `main` |
| Rotate a secret | Add a new secret version (step 7) |
| Scale to zero (cost saving) | Cloud Run does this automatically when idle |
