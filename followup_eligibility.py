"""
Follow-up Eligibility Rules.

Phase 5.3 / 5.5.7:
    - Determine whether a lead is eligible for follow-up scheduling.
    - Keep follow-up business rules separate from database operations.
    - Block follow-up when the authoritative conversation is
      classified as not_interested.
"""

MAX_FOLLOWUP_ATTEMPTS = 2


ELIGIBLE_LEAD_STATUSES = {
    "follow_up_due",
}


TERMINAL_OR_NON_ELIGIBLE_STATUSES = {
    "new_lead",
    "qualified",
    "watch",
    "rejected",
    "contact_found",
    "manual_sourcing",
    "message_drafted",
    "waiting_for_approval",
    "approved_ready_to_send",
    "message_rejected",
    "sent",
    "replied",
    "interested",
    "not_interested",
    "negotiating",
    "deal_confirmed",
    "wrong_contact",
    "no_response",
    "do_not_contact",
    "completed",
}


NON_ELIGIBLE_CONVERSATION_CLASSIFICATIONS = {
    "not_interested",
}


def is_followup_eligible(
    lead_status: str,
    attempt_number: int = 1,
    has_active_followup: bool = False,
    conversation_classification: str | None = None,
):
    """
    Determine whether a lead can receive a follow-up.

    A not_interested conversation always blocks follow-up,
    regardless of the lead status.
    """

    if not lead_status or not lead_status.strip():
        raise ValueError("lead_status is required.")

    if attempt_number < 1:
        raise ValueError(
            "attempt_number must be >= 1."
        )

    if conversation_classification is not None:
        classification = (
            conversation_classification.strip()
        )

        if classification in (
            NON_ELIGIBLE_CONVERSATION_CLASSIFICATIONS
        ):
            return False

    if attempt_number > MAX_FOLLOWUP_ATTEMPTS:
        return False

    if has_active_followup:
        return False

    return lead_status.strip() in ELIGIBLE_LEAD_STATUSES
