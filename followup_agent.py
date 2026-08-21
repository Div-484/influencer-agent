"""
Follow-up Generator Agent.

Phase 5.5.2 / 5.5.5:
    - Generate a follow-up message from retrieved context.
    - Use conversation history when available.
    - Use conversation classification when available.
    - Consider previous follow-up attempts.
    - Keep generation separate from database access.
    - Do not send or persist messages.
"""


def _latest_inbound_message(messages):
    inbound = [
        message
        for message in messages
        if message.get("direction") == "inbound"
    ]

    if not inbound:
        return None

    return max(
        inbound,
        key=lambda message: message.get("sent_at")
    )


def _latest_outbound_message(messages):
    outbound = [
        message
        for message in messages
        if message.get("direction") == "outbound"
    ]

    if not outbound:
        return None

    return max(
        outbound,
        key=lambda message: message.get("sent_at")
    )


def generate_followup_message(context: dict) -> str:
    """
    Generate a context-aware follow-up message.

    Pure function:

        context -> message

    No database operations.
    No SMTP.
    No approval changes.
    """

    if not isinstance(context, dict):
        raise ValueError(
            "context must be a dictionary."
        )

    if not context.get("found"):
        raise ValueError(
            "follow-up context was not found."
        )

    followup = context.get("followup") or {}
    brand = context.get("brand") or {}
    contact = context.get("contact") or {}
    previous_outreach = context.get(
        "previous_outreach"
    )
    previous_followups = context.get(
        "previous_followups"
    ) or []
    conversation = context.get(
        "conversation"
    ) or {}
    messages = context.get(
        "messages"
    ) or []

    if not followup.get("followup_id"):
        raise ValueError(
            "follow-up context is missing followup_id."
        )

    contact_name = (
        contact.get("name")
        or "there"
    )

    brand_name = (
        brand.get("name")
        or "our collaboration"
    )

    classification = (
        conversation.get("classification")
        if conversation
        else None
    )

    latest_inbound = _latest_inbound_message(
        messages
    )

    latest_outbound = _latest_outbound_message(
        messages
    )

    # =========================================================
    # CASE 0:
    # NOT INTERESTED
    #
    # Do not create a sales follow-up after an explicit
    # rejection. The caller should treat this as a business
    # rule violation / non-sendable state.
    # =========================================================

    if classification == "not_interested":
        raise ValueError(
            "Cannot generate follow-up for a "
            "not_interested conversation."
        )

    # =========================================================
    # CASE 1:
    # NEGOTIATING
    # =========================================================

    if classification == "negotiating":
        return (
            f"Hi {contact_name},\n\n"
            f"Thanks for discussing the collaboration "
            f"with {brand_name}. I wanted to follow up "
            f"on the details and see if there are any "
            f"questions or terms you'd like to discuss "
            f"further.\n\n"
            f"Happy to continue the conversation and "
            f"work through the details.\n\n"
            f"Best"
        )

    # =========================================================
    # CASE 2:
    # QUESTION
    # =========================================================

    if classification == "question":
        return (
            f"Hi {contact_name},\n\n"
            f"Thanks for getting back to me regarding "
            f"the potential collaboration with "
            f"{brand_name}. I wanted to follow up and "
            f"make sure you have everything needed to "
            f"evaluate the opportunity.\n\n"
            f"Happy to provide any additional details "
            f"or clarification that would be helpful.\n\n"
            f"Best"
        )

    # =========================================================
    # CASE 3:
    # INTERESTED
    # =========================================================

    if classification == "interested":
        return (
            f"Hi {contact_name},\n\n"
            f"Thanks for your interest in collaborating "
            f"with {brand_name}. I wanted to follow up "
            f"and see what would be the best next step "
            f"for discussing the opportunity.\n\n"
            f"Happy to share the relevant details and "
            f"move the conversation forward.\n\n"
            f"Best"
        )

    # =========================================================
    # CASE 4:
    # INBOUND EXISTS BUT CLASSIFICATION IS UNKNOWN
    #
    # Safer than treating the conversation as no-response.
    # =========================================================

    if latest_inbound:
        inbound_body = (
            latest_inbound.get("body")
            or ""
        ).strip()

        if inbound_body:
            return (
                f"Hi {contact_name},\n\n"
                f"Thanks for getting back to me. "
                f"I wanted to follow up on our conversation "
                f"regarding a potential collaboration with "
                f"{brand_name}.\n\n"
                f"Please let me know if you'd like me to "
                f"share any additional details.\n\n"
                f"Best"
            )

    # =========================================================
    # CASE 5:
    # PREVIOUS FOLLOW-UP EXISTS
    # =========================================================

    sent_followups = [
        item
        for item in previous_followups
        if item.get("status") == "sent"
    ]

    if sent_followups:
        return (
            f"Hi {contact_name},\n\n"
            f"Just following up once more regarding our "
            f"potential collaboration with {brand_name}. "
            f"I wanted to see if this is something you'd "
            f"be open to discussing.\n\n"
            f"Happy to share more details if helpful.\n\n"
            f"Best"
        )

    # =========================================================
    # CASE 6:
    # ORIGINAL OUTREACH EXISTS
    # =========================================================

    if previous_outreach:
        return (
            f"Hi {contact_name},\n\n"
            f"Just following up on my previous message "
            f"about a potential collaboration with "
            f"{brand_name}. I wanted to check whether "
            f"this is something you'd be open to discussing.\n\n"
            f"Happy to share more details if helpful.\n\n"
            f"Best"
        )

    # =========================================================
    # CASE 7:
    # FALLBACK
    # =========================================================

    if latest_outbound:
        return (
            f"Hi {contact_name},\n\n"
            f"I wanted to follow up regarding our potential "
            f"collaboration with {brand_name}.\n\n"
            f"Please let me know if you'd be open to "
            f"discussing this further.\n\n"
            f"Best"
        )

    raise ValueError(
        "Insufficient context to generate follow-up."
    )
