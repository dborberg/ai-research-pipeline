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
2. `ai-research-daily-dry-run`
3. `ai-research-weekly-wholesaler`
4. `ai-research-weekly-thematic`
5. `ai-research-weekly-signal`
6. `ai-research-monthly`

All jobs use the same container image and set runtime secrets from Secret Manager.

The `ai-research-daily-dry-run` job is intentionally isolated from production state:

1. It runs `python run_pipeline.py --dry-run`.
2. It uses a temporary SQLite database at `/tmp/ai_research_dry_run.db`.
3. It does not send email.
4. It is not scheduled by default.

This is the safe path for inspecting a GCP-produced daily digest without mutating the production digest history used by the next scheduled run.

## Important runtime constraint

Deployment to Cloud Run Jobs is wired, but the batch architecture still writes state to local disk:

1. `data/ai_research.db`
2. `outputs/`

Cloud Run Jobs have ephemeral storage. That means code deployment is now connected, but full production execution from Cloud Run is still not equivalent to the current GitHub Actions runtime until persistence is moved off local files.

Current safe interpretation:

1. GitHub to GCP deployment is set up.
2. Scheduled execution should remain in GitHub Actions until persistence is migrated.

## Interim scheduler recommendation

If you want more reliable trigger timing before moving persistence off SQLite, use GCP Cloud Scheduler to dispatch the existing GitHub workflows.

This is the recommended interim architecture because it improves schedule reliability without changing the current stateful runtime behavior:

1. Cloud Scheduler becomes the authoritative clock.
2. GitHub Actions remains the execution runtime and still persists `outputs/` and `data/ai_research.db` back into the repository.
3. Weekly, monthly, and the local dashboard continue to read the same repo-backed state they use today.

This repository now supports that cutover safely:

1. The daily, weekly, and monthly workflows accept `workflow_dispatch` payloads marked with `scheduled_run=true`.
2. Duplicate guards treat those GCP-triggered dispatches like scheduled runs.
3. Cloud Scheduler can be the sole scheduler while GitHub Actions remains the execution runtime.

Operational note:

1. If you keep native GitHub `schedule:` blocks, GitHub will still emit `schedule` events even when Cloud Scheduler is the intended clock.
2. If you want Cloud Scheduler to be the only visible trigger source, remove or disable the GitHub `schedule:` blocks rather than relying on skip guards alone.
3. In the current dispatch-only model, the workflows are manually dispatchable for testing and scheduler-dispatchable for production automation.

## One-time Cloud Scheduler setup

You need a GitHub token that can dispatch workflows for `dborberg/ai-research-pipeline`.

Recommended token shape:

1. Fine-grained personal access token.
2. Repository access limited to `dborberg/ai-research-pipeline`.
3. Permissions sufficient to trigger Actions workflows.

Important note:

1. The token is sent as an HTTP header by Cloud Scheduler.
2. That means it becomes part of the Scheduler job configuration, so use a dedicated low-scope token only for workflow dispatch.
3. Do not reuse your normal interactive GitHub token for this.

Then run:

```bash
export PROJECT_ID=ai-research-pipeline
export REGION=us-central1
export GITHUB_TOKEN=YOUR_GITHUB_TRIGGER_TOKEN
bash scripts/deploy_gcp_github_scheduler.sh
```

This creates these Cloud Scheduler jobs in `us-central1` using `America/Chicago` time:

1. `ai-research-gh-daily` at `6:30 AM`
2. `ai-research-gh-weekly-wholesaler` at `8:00 AM Friday`
3. `ai-research-gh-weekly-thematic` at `8:15 AM Friday`
4. `ai-research-gh-weekly-signal` at `8:30 AM Friday`
5. `ai-research-gh-monthly` at `10:00 AM` on the first day of the month

The script is idempotent and updates existing jobs in place.

## Cutover steps

After the scheduler jobs exist, cut over in this order:

1. Manually test one scheduler job with `gcloud scheduler jobs run ai-research-gh-daily --location=us-central1`.
2. Confirm the corresponding GitHub workflow starts via `workflow_dispatch`.
3. If GitHub native cron is still enabled in your workflows and you want guard-based skipping during transition, set the GitHub repository variable `USE_GCP_SCHEDULER=true`.
4. If you want Cloud Scheduler to be the only active trigger source, remove the `schedule:` blocks from the workflows after validation.

Verification guidance:

1. In a dispatch-only setup, GitHub Actions history should show `workflow_dispatch` events for production automation.
2. If `schedule` events are still appearing, GitHub cron is still enabled somewhere in the workflow configuration.

Example variable command:

```bash
gh variable set USE_GCP_SCHEDULER \
  --repo dborberg/ai-research-pipeline \
  --body true
```

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

## Safe daily output test in GCP

After the jobs are deployed, you can manually execute the isolated test job:

```bash
gcloud run jobs execute ai-research-daily-dry-run \
  --project=ai-research-pipeline \
  --region=us-central1 \
  --wait
```

Then inspect the digest output from Cloud Logging:

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="ai-research-daily-dry-run"' \
  --project=ai-research-pipeline \
  --limit=100 \
  --format='value(textPayload)'
```

This test path is designed not to disrupt the next scheduled daily production run.

## Next architecture step

To make the Cloud Run Jobs themselves the production scheduler target, move persistence off SQLite and local output files first.

## Cloud SQL recommendation

Moving persistence to Cloud SQL is recommended soon, but it is not required for the interim GCP-triggered GitHub scheduling build.

Recommended timing:

1. Do the Cloud Scheduler cutover now if schedule reliability is the immediate pain.
2. Move persistence to Cloud SQL next if you want a single authoritative production state for daily, weekly, monthly, and the dashboard.
3. Only after that move the production runtime itself from GitHub Actions to Cloud Run Jobs.

In other words:

1. Cloud Scheduler now.
2. Cloud SQL next.
3. Full Cloud Run production after the data layer is migrated.

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
