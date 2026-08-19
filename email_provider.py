"""
Email Provider Abstraction.

Phase 3.1:
    - Define a standard inbound email structure.
    - Define the provider interface.
    - Keep provider-specific logic outside the reply pipeline.

This module does not connect to Gmail, IMAP, or any external service.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class InboundEmail:
    """
    Standard representation of an inbound email.
    """

    sender_email: str
    body: str
    external_message_id: str
    received_at: datetime


class EmailProvider(Protocol):
    """
    Interface that every email provider adapter must implement.
    """

    def fetch_new_emails(self) -> list[InboundEmail]:
        """
        Return newly available inbound emails.
        """
        ...
