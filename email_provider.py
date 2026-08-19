"""
Email Provider Abstraction.

Phase 3.3:
    - Define a standard inbound email structure.
    - Define the provider interface.
    - Support fetching new emails.
    - Support retrieving an email by external message ID.
    - Keep provider-specific logic outside the processing pipeline.
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

    def get_email(
        self,
        external_message_id: str,
    ) -> InboundEmail | None:
        """
        Return an email by its external provider message ID.

        Return None when the email cannot be found.
        """
        ...
