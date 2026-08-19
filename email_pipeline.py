"""
Email Processing Pipeline.

Phase 3.2:
    - Fetch emails from an EmailProvider.
    - Process each inbound email.
    - Record agent execution in agent_runs.
    - Track success and failure.
"""

import time

from agent_run_logger import record_agent_run
from email_provider import EmailProvider
from email_reply_handler import handle_inbound_email


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

            record_agent_run(
                agent_name="email_reply_processor",
                status="failed",
                input_ref=email.external_message_id,
                duration_ms=duration_ms,
                error_message=str(error),
            )

            results.append(
                {
                    "matched": False,
                    "external_message_id": email.external_message_id,
                    "error": str(error),
                }
            )

    return results
