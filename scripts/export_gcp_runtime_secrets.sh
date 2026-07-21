#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${GITHUB_ENV:-}" ]]; then
  echo "GITHUB_ENV must be set."
  exit 1
fi

PROJECT_ID="${PROJECT_ID:-ai-research-pipeline}"

if [[ $# -eq 0 ]]; then
  set -- OPENAI_API_KEY EMAIL_USER EMAIL_PASSWORD EMAIL_TO
fi

for secret_name in "$@"; do
  secret_value="$(gcloud secrets versions access latest --secret="$secret_name" --project="$PROJECT_ID")"
  if [[ -z "$secret_value" ]]; then
    echo "Secret $secret_name is empty or unavailable in project $PROJECT_ID."
    exit 1
  fi

  {
    echo "${secret_name}<<EOF"
    echo "$secret_value"
    echo "EOF"
  } >> "$GITHUB_ENV"
done