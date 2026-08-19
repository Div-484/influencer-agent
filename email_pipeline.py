"""
Email Processing Pipeline.

Phase 3.3:
    - Fetch emails from an EmailProvider.
    - Process each inbound email.
    - Record agent execution in agent_runs.
    - Schedule failed emails for retry.
"""

import time

from agent_run_logger import record_agent_run
from email_provider import EmailProvider
from email_reply_handler import handle_inbound_email
from email_retry_queue import schedule_retry


DEFAULT_MAX_ATTEMPTS = 3


def process_new_emails(provider: EmailProvider):
    """
    Fetch and process all currently available inbound emails.

    Each email is processed independently.
    A failure for one email does not stop the remaining emails.
    """

    emails = provider.fetch_new_emails()

    results = []

    for email in emails:
        started_at = time.perf_counter()

        try:
            result = handle_inbound_email(
                email.sender_email,
                email.body,
                email.external_message_id,
            )

            duration_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            record_agent_run(
                agent_name="email_reply_processor",
                status="success",
                input_ref=email.external_message_id,
                output_ref=str(result.get("message_id")),
                duration_ms=duration_ms,
            )

            results.append(result)

        except Exception as error:
            duration_ms = int(
                (time.perf_counter() - started_at) * 1000
            )

            error_message = str(error)

            retry_id = None
            retry_error = None

            try:
                retry_id = schedule_retry(
                    external_message_id=email.external_message_id,
                    agent_name="email_reply_processor",
                    error_message=error_message,
                    attempt_number=1,
                    max_attempts=DEFAULT_MAX_ATTEMPTS,
                )
            except Exception as retry_exception:
                retry_error = str(retry_exception)

            try:
                record_agent_run(
                    agent_name="email_reply_processor",
                    status="failed",
                    input_ref=email.external_message_id,
                    duration_ms=duration_ms,
                    error_message=(
                        error_message
                        if retry_error is None
                        else f"{error_message}; "
                             f"Retry scheduling failed: {retry_error}"
                    ),
                )
            except Exception:
                pass

            result = {
                "matched": False,
                "external_message_id": email.external_message_id,
                "error": error_message,
            }

            if retry_id is not None:
                result["retry_id"] = str(retry_id)

            if retry_error is not None:
                result["retry_error"] = retry_error

            results.append(result)

    return results
