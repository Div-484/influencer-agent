"""
Reply Classifier - deterministic classification for inbound replies.

Phase 2 scope:
    interested
    not_interested
    question
    negotiating
    no_response

This module only classifies text.
It does not modify the database.
"""


CLASSIFICATIONS = (
    "interested",
    "not_interested",
    "question",
    "negotiating",
    "no_response",
)


def classify_reply(body: str) -> str:
    """
    Classify an inbound reply using deterministic rules.

    Returns one of the supported conversation classifications.
    """
    if not body or not body.strip():
        return "no_response"

    text = " ".join(body.lower().split())

    negotiating_terms = (
        "budget",
        "rate",
        "pricing",
        "price",
        "cost",
        "fee",
        "payment",
        "paid",
        "compensation",
        "negotiate",
        "negotiation",
        "offer",
        "counter offer",
        "terms",
    )

    not_interested_terms = (
        "not interested",
        "no thanks",
        "not a fit",
        "pass for now",
        "decline",
        "declining",
        "do not contact",
        "don't contact",
        "unsubscribe",
    )

    interested_terms = (
        "interested",
        "sounds good",
        "sounds great",
        "love to",
        "would love to",
        "let's discuss",
        "lets discuss",
        "happy to discuss",
        "open to",
        "yes",
        "sure",
        "interested in collaborating",
    )

    question_mark = "?" in body

    if any(term in text for term in not_interested_terms):
        return "not_interested"

    if any(term in text for term in negotiating_terms):
        return "negotiating"

    if any(term in text for term in interested_terms):
        return "interested"

    if question_mark:
        return "question"

    return "question"
