import os
import subprocess
from functools import lru_cache


DEFAULT_GCP_PROJECT = "ai-research-pipeline"


def _get_gcp_project_id():
    for env_name in ("GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_ID", "PROJECT_ID"):
        value = (os.getenv(env_name) or "").strip()
        if value:
            return value
    return DEFAULT_GCP_PROJECT


@lru_cache(maxsize=16)
def _read_gcp_secret(secret_name, project_id):
    result = subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "access",
            "latest",
            f"--secret={secret_name}",
            f"--project={project_id}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"Unable to read {secret_name} from GCP Secret Manager for project {project_id}: {stderr or 'unknown error'}"
        )

    value = (result.stdout or "").strip()
    if not value:
        raise RuntimeError(
            f"GCP Secret Manager returned an empty value for {secret_name} in project {project_id}"
        )
    return value


def get_secret(secret_name, default=None, *, allow_gcp_fallback=True):
    value = (os.getenv(secret_name) or "").strip()
    if value:
        return value

    if not allow_gcp_fallback:
        return default

    try:
        value = _read_gcp_secret(secret_name, _get_gcp_project_id())
    except FileNotFoundError as exc:
        if default is not None:
            return default
        raise RuntimeError(
            "gcloud is required for local GCP secret fallback but was not found on PATH"
        ) from exc
    except RuntimeError:
        if default is not None:
            return default
        raise

    os.environ[secret_name] = value
    return value


def get_openai_api_key(default=None, *, allow_gcp_fallback=True):
    return get_secret(
        "OPENAI_API_KEY",
        default=default,
        allow_gcp_fallback=allow_gcp_fallback,
    )


def get_email_settings(*, allow_gcp_fallback=True):
    sender_email = get_secret("EMAIL_USER", allow_gcp_fallback=allow_gcp_fallback)
    receiver_email = get_secret("EMAIL_TO", allow_gcp_fallback=allow_gcp_fallback)
    app_password = get_secret("EMAIL_PASSWORD", allow_gcp_fallback=allow_gcp_fallback)
    return sender_email, receiver_email, app_password