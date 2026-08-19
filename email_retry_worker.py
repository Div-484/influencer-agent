"""
Email Retry Worker.

Phase 3.3:
    - Fetch due retries.
    - Recover the original email from the provider.
    - Mark retry as retrying.
    - Re-process the email.
    - Mark successful retries as completed.
    - Reschedule failed retries when attempts remain.
    - Exhaust retries when max attempts are reached.
    - Keep one retry failure from stopping other retries.
"""

from datetime import datetime, timedelta, timezone

from agent_run_logger import record_agent_run
from email_provider import EmailProvider
from email_reply_handler import handle_inbound_email
from email_retry_queue import (
    get_due_retries,

    mark_completed,
    mark_exhausted,
    schedule_next_retry,
)


DEFAULT_RETRY_DELAY_MINUTES = 5


def process_due_retries(
    provider: EmailProvider,
    limit: int = 10,
    retry_delay_minutes: int = DEFAULT_RETRY_DELAY_MINUTES,
):
    """
    Process retries that are currently due.

    Each retry is processed independently.
    A failure does not stop other retries.
    """

    if limit < 1:
        raise ValueError("limit must be >= 1.")

    if retry_delay_minutes < 0:
        raise ValueError(
            "retry_delay_minutes must be >= 0."
        )

    retries = get_due_retries(limit=limit)

    results = []

    for retry in retries:
        (
            retry_id,
            external_message_id,
            agent_name,
            attempt_number,
            max_attempts,
            scheduled_for,
            status,
            last_error,
        ) = retry

        try:


            email = provider.get_email(
                external_message_id
            )

            if email is None:
                error_message = (
                    "Email could not be recovered "
                    f"from provider: {external_message_id}"
                )

                if attempt_number >= max_attempts:
                    mark_exhausted(
                        retry_id,
                        error_message,
                    )

                    record_agent_run(
                        agent_name=agent_name,
                        status="failed",
                        input_ref=external_message_id,
                        error_message=error_message,
                    )

                    results.append(
                        {
                            "retry_id": str(retry_id),
                            "external_message_id": external_message_id,
                            "status": "exhausted",
                            "error": error_message,
                        }
                    )

                else:
                    next_scheduled_for = (
                        datetime.now(timezone.utc)
                        + timedelta(
                            minutes=retry_delay_minutes
                        )
                    )

                    schedule_next_retry(
                        retry_id,
                        error_message,
                        next_scheduled_for,
                    )

                    record_agent_run(
                        agent_name=agent_name,
                        status="failed",
                        input_ref=external_message_id,
                        error_message=error_message,
                    )

                    results.append(
                        {
                            "retry_id": str(retry_id),
                            "external_message_id": external_message_id,
                            "status": "scheduled",
                            "error": error_message,
                        }
                    )

                continue

            result = handle_inbound_email(
                email.sender_email,
                email.body,
                email.external_message_id,
            )

            if not result.get("matched"):
                raise RuntimeError(
                    result.get(
                        "reason",
                        "Inbound email could not be matched to a sent outreach.",
                    )
                )

            record_agent_run(
                agent_name=agent_name,
                status="success",
                input_ref=external_message_id,
                output_ref=str(
                    result.get("message_id")
                ),
            )

            mark_completed(retry_id)

            results.append(
                {
                    "retry_id": str(retry_id),
                    "external_message_id": external_message_id,
                    "status": "completed",
                    "result": result,
                }
            )

        except Exception as error:
            error_message = str(error)

            record_agent_run(
                agent_name=agent_name,
                status="failed",
                input_ref=external_message_id,
                error_message=error_message,
            )

            if attempt_number >= max_attempts:
                mark_exhausted(
                    retry_id,
                    error_message,
                )

                results.append(
                    {
                        "retry_id": str(retry_id),
                        "external_message_id": external_message_id,
                        "status": "exhausted",
                        "error": error_message,
                    }
                )

            else:
                next_scheduled_for = (
                    datetime.now(timezone.utc)
                    + timedelta(
                        minutes=retry_delay_minutes
                    )
                )

                schedule_next_retry(
                    retry_id,
                    error_message,
                    next_scheduled_for,
                )

                results.append(
                    {
                        "retry_id": str(retry_id),
                        "external_message_id": external_message_id,
                        "status": "scheduled",
                        "error": error_message,
                    }
                )

    return results
