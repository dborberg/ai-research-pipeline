#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-research-pipeline}"
REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-ai-research-pipeline}"
IMAGE_NAME="${IMAGE_NAME:-ai-research-pipeline}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
JOB_SERVICE_ACCOUNT="${JOB_SERVICE_ACCOUNT:-}"
CPU="${CLOUD_RUN_JOB_CPU:-2}"
MEMORY="${CLOUD_RUN_JOB_MEMORY:-2Gi}"
TASK_TIMEOUT="${CLOUD_RUN_JOB_TIMEOUT:-3600s}"
MAX_RETRIES="${CLOUD_RUN_JOB_MAX_RETRIES:-1}"

if [[ $# -gt 0 ]]; then
  IMAGE_URI="$1"
else
  IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
fi

if [[ -z "$JOB_SERVICE_ACCOUNT" ]]; then
  echo "JOB_SERVICE_ACCOUNT must be set."
  exit 1
fi

SECRETS_SPEC="OPENAI_API_KEY=OPENAI_API_KEY:latest,EMAIL_USER=EMAIL_USER:latest,EMAIL_PASSWORD=EMAIL_PASSWORD:latest,EMAIL_TO=EMAIL_TO:latest"
COMMON_ENV_VARS="PYTHONUNBUFFERED=1"
COMMON_ARGS=(
  "--project=${PROJECT_ID}"
  "--region=${REGION}"
  "--image=${IMAGE_URI}"
  "--service-account=${JOB_SERVICE_ACCOUNT}"
  "--cpu=${CPU}"
  "--memory=${MEMORY}"
  "--max-retries=${MAX_RETRIES}"
  "--task-timeout=${TASK_TIMEOUT}"
  "--tasks=1"
  "--parallelism=1"
  "--set-secrets=${SECRETS_SPEC}"
)

ensure_repository() {
  if gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    return
  fi

  gcloud artifacts repositories create "$REPOSITORY" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --repository-format=docker \
    --description="Container images for ai-research-pipeline"
}

deploy_job() {
  local job_name="$1"
  local extra_env_vars="$2"
  shift
  shift

  local job_args=("${COMMON_ARGS[@]}" "--set-env-vars=${COMMON_ENV_VARS}")
  if [[ -n "$extra_env_vars" ]]; then
    job_args=("${COMMON_ARGS[@]}" "--set-env-vars=${COMMON_ENV_VARS},${extra_env_vars}")
  fi

  if gcloud run jobs describe "$job_name" --project="$PROJECT_ID" --region="$REGION" >/dev/null 2>&1; then
    gcloud run jobs update "$job_name" "${job_args[@]}" "$@"
  else
    gcloud run jobs create "$job_name" "${job_args[@]}" "$@"
  fi
}

ensure_repository

deploy_job ai-research-daily "" \
  --command=python \
  --args=run_pipeline.py

deploy_job ai-research-daily-dry-run "DB_URL=sqlite:////tmp/ai_research_dry_run.db" \
  --command=python \
  --args=run_pipeline.py,--dry-run

deploy_job ai-research-weekly-wholesaler "" \
  --command=python \
  --args=run_weekly_investment_pipeline.py,--mode,WHOLESALER

deploy_job ai-research-weekly-thematic "" \
  --command=python \
  --args=run_weekly_investment_pipeline.py,--mode,THEMATIC

deploy_job ai-research-weekly-signal "" \
  --command=python \
  --args=run_weekly_investment_pipeline.py,--mode,SIGNAL

deploy_job ai-research-monthly "" \
  --command=python \
  --args=run_monthly_pipeline.py