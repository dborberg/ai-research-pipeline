import argparse
import os

from dotenv import load_dotenv

from app.db import fetch_weekly_digests, init_db
from app.reporting import get_latest_completed_friday, get_openai_client
from app.send_email import send_report
from run_weekly_pipeline import THEMATIC_TITLE, WHOLESALER_TITLE, _generate_and_store_weekly_reports


WHOLESALER_TYPE = "wholesaler"
THEMATIC_TYPE = "thematic"
SIGNAL_TYPE = "signal_command_brief"


def _get_stored_weekly_digest_content(week_start, digest_type):
    rows = fetch_weekly_digests(digest_type=digest_type, limit=12)
    for row in rows:
        if str(row["week_start"]) == week_start.isoformat():
            return row["content"]
    return None


def _load_or_generate_reports(mode, week_start):
    digest_type_map = {
        "WHOLESALER": WHOLESALER_TYPE,
        "THEMATIC": THEMATIC_TYPE,
        "SIGNAL": SIGNAL_TYPE,
    }

    stored_reports = {
        WHOLESALER_TYPE: _get_stored_weekly_digest_content(week_start, WHOLESALER_TYPE),
        THEMATIC_TYPE: _get_stored_weekly_digest_content(week_start, THEMATIC_TYPE),
        SIGNAL_TYPE: _get_stored_weekly_digest_content(week_start, SIGNAL_TYPE),
    }

    if mode == "WHOLESALER" and all(stored_reports.values()):
        return {
            "wholesaler": stored_reports[WHOLESALER_TYPE],
            "thematic": stored_reports[THEMATIC_TYPE],
            "signal": stored_reports[SIGNAL_TYPE],
        }

    if mode != "WHOLESALER" and stored_reports[digest_type_map[mode]]:
        return {
            "wholesaler": stored_reports[WHOLESALER_TYPE],
            "thematic": stored_reports[THEMATIC_TYPE],
            "signal": stored_reports[SIGNAL_TYPE],
        }

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set")

    client = get_openai_client(api_key)
    generated = _generate_and_store_weekly_reports(client, week_start)
    return {
        "wholesaler": generated[WHOLESALER_TYPE],
        "thematic": generated[THEMATIC_TYPE],
        "signal": generated[SIGNAL_TYPE],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    args = parser.parse_args()

    load_dotenv()
    init_db()

    week_start = get_latest_completed_friday()

    if args.mode not in {"WHOLESALER", "THEMATIC", "SIGNAL"}:
        raise RuntimeError("--mode must be one of WHOLESALER, THEMATIC, SIGNAL")

    reports = _load_or_generate_reports(args.mode, week_start)

    subject_map = {
        "WHOLESALER": WHOLESALER_TITLE,
        "THEMATIC": THEMATIC_TITLE,
        "SIGNAL": f"[WEEKLY - SIGNAL] AI Signal Command Brief - Week Ending {week_start.isoformat()}",
    }
    content_map = {
        "WHOLESALER": reports["wholesaler"],
        "THEMATIC": reports["thematic"],
        "SIGNAL": reports["signal"],
    }

    send_report(subject_map[args.mode], content_map[args.mode])


if __name__ == "__main__":
    main()
