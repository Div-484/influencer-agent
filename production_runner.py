"""
Production Execution Runner.

Phase 4.4.1:
    - Orchestrate inbound email processing.
    - Orchestrate automatic retry processing.
    - Keep provider-specific logic outside the runner.
    - Isolate cycle-level failures.
    - Support graceful shutdown.
"""

import time

from email_pipeline import process_new_emails
from email_provider import EmailProvider
from email_retry_runner import run_retry_cycle
from followup_runner import run_followup_cycle

DEFAULT_POLL_INTERVAL_SECONDS = 30
DEFAULT_RETRY_DELAY_MINUTES = 5
DEFAULT_BATCH_LIMIT = 10


def run_execution_cycle(
    provider: EmailProvider,
    limit: int = DEFAULT_BATCH_LIMIT,
    retry_delay_minutes: int = DEFAULT_RETRY_DELAY_MINUTES,
):
    """
    Execute one production processing cycle.

    New inbound emails and due retries are processed
    independently so one cycle failure does not prevent
    the other cycle from running.
    """

    results = {
        "new_emails": [],
        "retries": [],
        "errors": [],
        "followups": [],
    }

    try:
        results["new_emails"] = process_new_emails(
            provider
        )
    except Exception as error:
        results["errors"].append(
            {
                "stage": "new_emails",
                "error": str(error),
            }
        )

    try:
        results["retries"] = run_retry_cycle(
            provider=provider,
            limit=limit,
            retry_delay_minutes=retry_delay_minutes,
        )
    except Exception as error:
        results["errors"].append(
            {
                "stage": "retries",
                "error": str(error),
            }
        )

    try:
        results["followups"] = run_followup_cycle(
            limit=limit,
        )
    except Exception as error:
        results["errors"].append(
            {
                "stage": "followups",
                "error": str(error),
            }
        )

    return results


def run_production_loop(
    provider: EmailProvider,
    limit: int = DEFAULT_BATCH_LIMIT,
    retry_delay_minutes: int = DEFAULT_RETRY_DELAY_MINUTES,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    sleep_fn=time.sleep,
    should_stop_fn=lambda: False,
):
    """
    Continuously execute production processing cycles.

    The loop stops when should_stop_fn() returns True.
    """

    if limit < 1:
        raise ValueError("limit must be >= 1.")

    if retry_delay_minutes < 0:
        raise ValueError(
            "retry_delay_minutes must be >= 0."
        )

    if poll_interval_seconds < 1:
        raise ValueError(
            "poll_interval_seconds must be >= 1."
        )

    if not callable(sleep_fn):
        raise ValueError(
            "sleep_fn must be callable."
        )

    if not callable(should_stop_fn):
        raise ValueError(
            "should_stop_fn must be callable."
        )

    while not should_stop_fn():
        run_execution_cycle(
            provider=provider,
            limit=limit,
            retry_delay_minutes=retry_delay_minutes,
        )

        if should_stop_fn():
            break

        sleep_fn(poll_interval_seconds)
