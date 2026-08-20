"""
Email Retry Runner.

Phase 4.2:
    - Execute retry-processing cycles.
    - Continuously poll for due retries.
    - Support graceful shutdown.
    - Isolate cycle-level failures.
"""

import time

from email_provider import EmailProvider
from email_retry_worker import process_due_retries


DEFAULT_POLL_INTERVAL_SECONDS = 30


def run_retry_cycle(
    provider: EmailProvider,
    limit: int = 10,
    retry_delay_minutes: int = 5,
):
    """
    Execute one retry-processing cycle.
    """

    return process_due_retries(
        provider=provider,
        limit=limit,
        retry_delay_minutes=retry_delay_minutes,
    )


def run_retry_loop(
    provider: EmailProvider,
    limit: int = 10,
    retry_delay_minutes: int = 5,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    sleep_fn=time.sleep,
    should_stop_fn=lambda: False,
):
    """
    Continuously process due retries.

    The runner stops cleanly when should_stop_fn() returns True.

    Cycle-level failures are isolated so one failed cycle
    does not terminate the runner.
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
        raise ValueError("sleep_fn must be callable.")

    if not callable(should_stop_fn):
        raise ValueError(
            "should_stop_fn must be callable."
        )

    while not should_stop_fn():
        try:
            run_retry_cycle(
                provider=provider,
                limit=limit,
                retry_delay_minutes=retry_delay_minutes,
            )

        except Exception as error:
            print(
                f"Retry runner cycle failed: {error}"
            )

        if should_stop_fn():
            break

        sleep_fn(poll_interval_seconds)
