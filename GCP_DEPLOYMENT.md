# GCP deployment setup

## Current state

This repository is connected to GitHub and now includes a deployment workflow for Cloud Run Jobs:

- `.github/workflows/deploy_cloud_run_jobs.yml`
- `scripts/deploy_cloud_run_jobs.sh`

The intended path is:

1. Make code changes in VS Code.
2. Push to `main`.
3. GitHub Actions builds a container image and pushes it to Artifact Registry.
4. GitHub Actions updates the Cloud Run Jobs in project `ai-research-pipeline`.

## What the deploy workflow manages

The deploy script updates or creates these Cloud Run Jobs in `us-central1`:

1. `ai-research-daily`
2. `ai-research-weekly-wholesaler`
3. `ai-research-weekly-thematic`
4. `ai-research-weekly-signal`
5. `ai-research-monthly`

All jobs use the same container image and set runtime secrets from Secret Manager.

## Important runtime constraint

Deployment to Cloud Run Jobs is wired, but the batch architecture still writes state to local disk:

1. `data/ai_research.db`
2. `outputs/`

Cloud Run Jobs have ephemeral storage. That means code deployment is now connected, but full production execution from Cloud Run is still not equivalent to the current GitHub Actions runtime until persistence is moved off local files.

Current safe interpretation:

1. GitHub to GCP deployment is set up.
2. Scheduled execution should remain in GitHub Actions until persistence is migrated.

## Local gcloud bootstrap

Run these commands locally once:

```bash
gcloud auth login --update-adc
gcloud config set project ai-research-pipeline
gcloud auth application-default login
```

Verify:

```bash
gcloud auth list
gcloud config get-value project
```

## One-time GCP project setup

Enable required services:

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com
```

Create or confirm the runtime secrets:

```bash
printf '%s' 'YOUR_OPENAI_API_KEY' | gcloud secrets create OPENAI_API_KEY --data-file=-
printf '%s' 'YOUR_EMAIL_USER' | gcloud secrets create EMAIL_USER --data-file=-
printf '%s' 'YOUR_EMAIL_PASSWORD' | gcloud secrets create EMAIL_PASSWORD --data-file=-
printf '%s' 'YOUR_EMAIL_TO' | gcloud secrets create EMAIL_TO --data-file=-
```

If a secret already exists, add a new version instead:

```bash
printf '%s' 'NEW_VALUE' | gcloud secrets versions add OPENAI_API_KEY --data-file=-
```

Create the service accounts:

```bash
gcloud iam service-accounts create github-deployer \
  --display-name="GitHub deployer"

gcloud iam service-accounts create cloud-run-job-runner \
  --display-name="Cloud Run job runner"
```

Grant the GitHub deployer permissions:

```bash
gcloud projects add-iam-policy-binding ai-research-pipeline \
  --member="serviceAccount:github-deployer@ai-research-pipeline.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding ai-research-pipeline \
  --member="serviceAccount:github-deployer@ai-research-pipeline.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding ai-research-pipeline \
  --member="serviceAccount:github-deployer@ai-research-pipeline.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

Grant the runtime service account permissions:

```bash
gcloud projects add-iam-policy-binding ai-research-pipeline \
  --member="serviceAccount:cloud-run-job-runner@ai-research-pipeline.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## GitHub Workload Identity Federation

Create a workload identity pool and provider:

```bash
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions pool"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --display-name="GitHub provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref"
```

Allow your repository to impersonate the deployer service account:

```bash
PROJECT_NUMBER=$(gcloud projects describe ai-research-pipeline --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding \
  github-deployer@ai-research-pipeline.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/dborberg/ai-research-pipeline"
```

## GitHub repository secrets to add

Add these repository secrets in GitHub:

1. `GCP_WORKLOAD_IDENTITY_PROVIDER`
2. `GCP_DEPLOYER_SERVICE_ACCOUNT`
3. `CLOUD_RUN_JOB_SERVICE_ACCOUNT`

Expected values:

1. `GCP_WORKLOAD_IDENTITY_PROVIDER`: `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
2. `GCP_DEPLOYER_SERVICE_ACCOUNT`: `github-deployer@ai-research-pipeline.iam.gserviceaccount.com`
3. `CLOUD_RUN_JOB_SERVICE_ACCOUNT`: `cloud-run-job-runner@ai-research-pipeline.iam.gserviceaccount.com`

## Local deploy validation

Once authenticated, you can validate the same deploy path locally:

```bash
export PROJECT_ID=ai-research-pipeline
export REGION=us-central1
export JOB_SERVICE_ACCOUNT=cloud-run-job-runner@ai-research-pipeline.iam.gserviceaccount.com
bash scripts/deploy_cloud_run_jobs.sh
```

## Next architecture step

To make the Cloud Run Jobs themselves the production scheduler target, move persistence off SQLite and local output files first.

## Dashboard recommendation

The dashboard should eventually move to a Cloud Run Service if you want it always available, but it should not be treated as production-ready for Cloud Run in the current storage model.

Current blockers:

1. `app/db.py`, `run_pipeline.py`, `app/generate_digest.py`, and `app/enrich_articles.py` all depend on the same local database.
2. The dashboard reads from `weekly_clusters`, `weekly_digests`, `daily_digests`, and `monthly_reports` and therefore needs the same durable state as the batch jobs.
3. `streamlit_app.py` also relies on stored cluster history, so a stateless container with ephemeral disk will drift or reset.

What is prepared now:

1. The shared DB layer now supports `DB_URL` so the codebase can be pointed at managed storage later without another round of hardcoded path cleanup.
2. `Dockerfile.dashboard` runs the Streamlit dashboard on Cloud Run's required `PORT`.

Recommended migration sequence:

1. Move the database to a managed backend and set `DB_URL` for both jobs and the dashboard.
2. Validate that the batch jobs still populate the same tables in the managed database.
3. Deploy the dashboard as a Cloud Run Service using `Dockerfile.dashboard`.

Example dashboard deploy command after persistence is migrated:

```bash
gcloud run deploy ai-research-dashboard \
  --project=ai-research-pipeline \
  --region=us-central1 \
  --source=. \
  --dockerfile=Dockerfile.dashboard \
  --allow-unauthenticated
```
