"""
Mock Email Provider.

Phase 3.1:
    - Simulates an email provider.
    - Used for deterministic testing.
    - Does not connect to any external service.
"""

from email_provider import InboundEmail


class MockEmailProvider:
    """
    In-memory email provider used for testing.
    """

    def __init__(self, emails: list[InboundEmail] | None = None):
        self._emails = emails or []

    def fetch_new_emails(self) -> list[InboundEmail]:
        """
        Return the currently configured test emails.
        """
        return list(self._emails)
