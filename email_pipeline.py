"""
Email Processing Pipeline.

Phase 3.1:
    - Fetch emails from an EmailProvider.
    - Pass each email through the existing reply handler.
    - Keep provider-specific logic separate from processing logic.
"""

from email_provider import EmailProvider
from email_reply_handler import handle_inbound_email


def process_new_emails(provider: EmailProvider):
    """
    Fetch and process all currently available inbound emails.
    """

    emails = provider.fetch_new_emails()

    results = []

    for email in emails:
        result = handle_inbound_email(
            email.sender_email,
            email.body,
            email.external_message_id,
        )

        results.append(result)

    return results
