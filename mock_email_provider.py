"""
Mock Email Provider.

Phase 3.3:
    - Simulates an email provider.
    - Supports new-email fetching.
    - Supports retrieving an email by external message ID.
    - Used for deterministic retry testing.
    - Does not connect to any external service.
"""

from email_provider import InboundEmail


class MockEmailProvider:
    """
    In-memory email provider used for testing.
    """

    def __init__(
        self,
        emails: list[InboundEmail] | None = None,
    ):
        self._emails = emails or []

    def fetch_new_emails(self) -> list[InboundEmail]:
        """
        Return the currently configured test emails.
        """
        return list(self._emails)

    def get_email(
        self,
        external_message_id: str,
    ) -> InboundEmail | None:
        """
        Return an email matching the external message ID.
        """

        for email in self._emails:
            if email.external_message_id == external_message_id:
                return email

        return None
