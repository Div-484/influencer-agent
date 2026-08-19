"""
Reply Status Mapping - maps reply classifications to lead statuses.

This module contains business rules only.
It does not modify the database.
"""


CLASSIFICATION_TO_LEAD_STATUS = {
    "interested": "interested",
    "not_interested": "not_interested",
    "question": "replied",
    "negotiating": "negotiating",
    "no_response": "no_response",
}


def get_lead_status(classification: str) -> str:
    """
    Return the lead status associated with a reply classification.
    """
    if classification not in CLASSIFICATION_TO_LEAD_STATUS:
        raise ValueError(
            f"Unsupported reply classification: {classification}"
        )

    return CLASSIFICATION_TO_LEAD_STATUS[classification]
