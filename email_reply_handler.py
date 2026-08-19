"""
Email Reply Handler.

Connects the email ingestion normalization layer
to the reply processor.

This module does not read Gmail/IMAP.
It only orchestrates already-received email data.
"""

from email_ingestion import normalize_inbound_email
from reply_processor import process_inbound_reply


def handle_inbound_email(
    sender_email: str,
    body: str,
    external_message_id: str,
):
    """
    Normalize and process one inbound email.
    """

    email = normalize_inbound_email(
        sender_email,
        body,
        external_message_id,
    )

    return process_inbound_reply(
        email["sender_email"],
        email["body"],
        email["external_message_id"],
    )
