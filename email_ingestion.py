"""
Email Ingestion - converts an already-fetched email into
the normalized input expected by reply_processor.py.

Phase 2 scope:
    - Validate incoming email fields.
    - Normalize sender email.
    - Normalize body.
    - Preserve external message ID.
    - Do not access Gmail/IMAP/API.
    - Do not modify the database.
"""


def normalize_inbound_email(
    sender_email: str,
    body: str,
    external_message_id: str,
):
    """
    Normalize one inbound email into a standard dictionary.
    """

    if not sender_email or not sender_email.strip():
        raise ValueError("sender_email is required.")

    if not body or not body.strip():
        raise ValueError("body is required.")

    if not external_message_id or not external_message_id.strip():
        raise ValueError("external_message_id is required.")

    return {
        "sender_email": sender_email.strip().lower(),
        "body": body.strip(),
        "external_message_id": external_message_id.strip(),
    }
