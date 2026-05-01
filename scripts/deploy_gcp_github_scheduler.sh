#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-research-pipeline}"
REGION="${REGION:-us-central1}"
TIME_ZONE="${TIME_ZONE:-America/Chicago}"
GITHUB_OWNER="${GITHUB_OWNER:-dborberg}"
GITHUB_REPO="${GITHUB_REPO:-ai-research-pipeline}"
GITHUB_REF="${GITHUB_REF:-main}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

DAILY_CRON="${DAILY_CRON:-30 6 * * *}"
WEEKLY_WHOLESALER_CRON="${WEEKLY_WHOLESALER_CRON:-0 8 * * 5}"
WEEKLY_THEMATIC_CRON="${WEEKLY_THEMATIC_CRON:-15 8 * * 5}"
WEEKLY_SIGNAL_CRON="${WEEKLY_SIGNAL_CRON:-30 8 * * 5}"
MONTHLY_CRON="${MONTHLY_CRON:-0 10 1 * *}"

if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "GITHUB_TOKEN must be set to a fine-grained token that can dispatch workflows for ${GITHUB_OWNER}/${GITHUB_REPO}."
  exit 1
fi

URI_BASE="https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows"
HEADERS="Authorization=Bearer ${GITHUB_TOKEN},Accept=application/vnd.github+json,Content-Type=application/json,X-GitHub-Api-Version=2022-11-28"
TEMP_DIR=""

ensure_scheduler_api() {
  gcloud services enable cloudscheduler.googleapis.com --project="$PROJECT_ID" >/dev/null
}

create_payload() {
  local path="$1"
  local body="$2"
  printf '%s' "$body" > "$path"
}

upsert_http_job() {
  local job_name="$1"
  local schedule="$2"
  local description="$3"
  local uri="$4"
  local body_file="$5"

  if gcloud scheduler jobs describe "$job_name" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$job_name" \
      --location="$REGION" \
      --project="$PROJECT_ID" \
      --schedule="$schedule" \
      --time-zone="$TIME_ZONE" \
      --uri="$uri" \
      --http-method=POST \
      --description="$description" \
      --update-headers="$HEADERS" \
      --message-body-from-file="$body_file" \
      --attempt-deadline=30s \
      --max-retry-attempts=3 \
      --min-backoff=30s \
      --max-backoff=600s \
      --max-doublings=3 >/dev/null
  else
    gcloud scheduler jobs create http "$job_name" \
      --location="$REGION" \
      --project="$PROJECT_ID" \
      --schedule="$schedule" \
      --time-zone="$TIME_ZONE" \
      --uri="$uri" \
      --http-method=POST \
      --description="$description" \
      --headers="$HEADERS" \
      --message-body-from-file="$body_file" \
      --attempt-deadline=30s \
      --max-retry-attempts=3 \
      --min-backoff=30s \
      --max-backoff=600s \
      --max-doublings=3 >/dev/null
  fi
}

main() {
  ensure_scheduler_api

  TEMP_DIR="$(mktemp -d)"
  trap 'rm -rf "${TEMP_DIR:-}"' EXIT

  create_payload "$TEMP_DIR/daily.json" "{\"ref\":\"${GITHUB_REF}\",\"inputs\":{\"scheduled_run\":\"true\"}}"
  create_payload "$TEMP_DIR/weekly-wholesaler.json" "{\"ref\":\"${GITHUB_REF}\",\"inputs\":{\"mode\":\"WHOLESALER\",\"scheduled_run\":\"true\"}}"
  create_payload "$TEMP_DIR/weekly-thematic.json" "{\"ref\":\"${GITHUB_REF}\",\"inputs\":{\"mode\":\"THEMATIC\",\"scheduled_run\":\"true\"}}"
  create_payload "$TEMP_DIR/weekly-signal.json" "{\"ref\":\"${GITHUB_REF}\",\"inputs\":{\"mode\":\"SIGNAL\",\"scheduled_run\":\"true\"}}"
  create_payload "$TEMP_DIR/monthly.json" "{\"ref\":\"${GITHUB_REF}\",\"inputs\":{\"scheduled_run\":\"true\"}}"

  upsert_http_job \
    ai-research-gh-daily \
    "$DAILY_CRON" \
    "Trigger the daily GitHub workflow from Cloud Scheduler" \
    "${URI_BASE}/daily_pipeline.yml/dispatches" \
    "$TEMP_DIR/daily.json"

  upsert_http_job \
    ai-research-gh-weekly-wholesaler \
    "$WEEKLY_WHOLESALER_CRON" \
    "Trigger the weekly wholesaler GitHub workflow from Cloud Scheduler" \
    "${URI_BASE}/weekly_digests.yml/dispatches" \
    "$TEMP_DIR/weekly-wholesaler.json"

  upsert_http_job \
    ai-research-gh-weekly-thematic \
    "$WEEKLY_THEMATIC_CRON" \
    "Trigger the weekly thematic GitHub workflow from Cloud Scheduler" \
    "${URI_BASE}/weekly_digests.yml/dispatches" \
    "$TEMP_DIR/weekly-thematic.json"

  upsert_http_job \
    ai-research-gh-weekly-signal \
    "$WEEKLY_SIGNAL_CRON" \
    "Trigger the weekly signal GitHub workflow from Cloud Scheduler" \
    "${URI_BASE}/weekly_digests.yml/dispatches" \
    "$TEMP_DIR/weekly-signal.json"

  upsert_http_job \
    ai-research-gh-monthly \
    "$MONTHLY_CRON" \
    "Trigger the monthly GitHub workflow from Cloud Scheduler" \
    "${URI_BASE}/monthly_digests.yml/dispatches" \
    "$TEMP_DIR/monthly.json"

  echo "Cloud Scheduler jobs created or updated in ${PROJECT_ID}/${REGION}."
  echo "Scheduler jobs are ready for workflow_dispatch-based automation."
}

main "$@"
