"""
Follow-up Eligibility Repository.

Phase 5.5.7:
    - Read lead state from the database.
    - Read existing follow-up state.
    - Read the latest authoritative conversation classification.
    - Block follow-up when the latest conversation is not_interested.
    - Keep database access separate from pure business rules.
"""

from db import get_connection
from followup_eligibility import (
    MAX_FOLLOWUP_ATTEMPTS,
    is_followup_eligible,
)


def get_followup_eligibility(
    lead_id: str,
    attempt_number: int = 1,
):
    """
    Determine follow-up eligibility using current database state.

    Rules:

        1. Lead must exist.
        2. No active scheduled follow-up may exist.
        3. Maximum follow-up attempts must not be exceeded.
        4. Lead status must be follow_up_due.
        5. Latest authoritative conversation must not be
           classified as not_interested.
    """

    if not lead_id or not lead_id.strip():
        raise ValueError("lead_id is required.")

    if attempt_number < 1:
        raise ValueError(
            "attempt_number must be >= 1."
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        # =====================================================
        # LEAD
        # =====================================================

        cur.execute(
            """
            SELECT status
            FROM leads
            WHERE lead_id = %s
            LIMIT 1;
            """,
            (lead_id.strip(),),
        )

        lead_row = cur.fetchone()

        if not lead_row:
            return {
                "eligible": False,
                "reason": "lead_not_found",
            }

        lead_status = lead_row[0]

        # =====================================================
        # ACTIVE FOLLOW-UP
        # =====================================================

        cur.execute(
            """
            SELECT COUNT(*)
            FROM followups
            WHERE lead_id = %s
              AND status = 'scheduled';
            """,
            (lead_id.strip(),),
        )

        active_followup_count = cur.fetchone()[0]

        if active_followup_count > 0:
            return {
                "eligible": False,
                "reason": "active_followup_exists",
            }

        # =====================================================
        # MAX ATTEMPTS
        # =====================================================

        if attempt_number > MAX_FOLLOWUP_ATTEMPTS:
            return {
                "eligible": False,
                "reason": "max_attempts_reached",
            }

        # =====================================================
        # LEAD STATUS
        # =====================================================

        eligible = is_followup_eligible(
            lead_status=lead_status,
            attempt_number=attempt_number,
            has_active_followup=False,
        )

        if not eligible:
            return {
                "eligible": False,
                "reason": "invalid_lead_status",
                "lead_status": lead_status,
            }

        # =====================================================
        # LATEST AUTHORITATIVE CONVERSATION
        #
        # The latest sent outreach is the authoritative
        # outreach for follow-up context.
        # =====================================================

        cur.execute(
            """
            SELECT
                c.classification
            FROM outreach o
            JOIN conversations c
                ON c.outreach_id = o.outreach_id
            WHERE o.lead_id = %s
              AND o.status = 'sent'
            ORDER BY
                o.last_sent_at DESC NULLS LAST,
                o.created_at DESC
            LIMIT 1;
            """,
            (lead_id.strip(),),
        )

        conversation_row = cur.fetchone()

        conversation_classification = (
            conversation_row[0]
            if conversation_row
            else None
        )

        # =====================================================
        # NOT INTERESTED GUARD
        # =====================================================

        if (
            conversation_classification
            == "not_interested"
        ):
            return {
                "eligible": False,
                "reason": "conversation_not_interested",
                "lead_status": lead_status,
                "conversation_classification":
                    conversation_classification,
            }

        # =====================================================
        # ELIGIBLE
        # =====================================================

        return {
            "eligible": True,
            "reason": "eligible",
            "lead_status": lead_status,
            "conversation_classification":
                conversation_classification,
        }

    finally:
        cur.close()
        conn.close()
