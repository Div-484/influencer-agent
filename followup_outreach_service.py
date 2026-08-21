"""
Follow-up Outreach Draft Service.

Phase 5.5.4:
    - Retrieve complete follow-up context.
    - Generate a context-aware follow-up message.
    - Create a drafted outreach record.
    - Link the generated outreach to the follow-up.
    - Never send email.
    - Never bypass human approval.
    - Prevent duplicate draft creation.
"""

from db import get_connection
from followup_context import get_followup_context
from followup_agent import generate_followup_message


FOLLOWUP_STATUS_SCHEDULED = "scheduled"
OUTREACH_STATUS_DRAFTED = "drafted"


def create_followup_outreach(
    followup_id: str,
):
    """
    Create a context-aware outreach draft for one scheduled follow-up.

    Flow:

        follow-up
            ↓
        context retrieval
            ↓
        message generation
            ↓
        outreach draft
            ↓
        follow-up/outreach link

    Database writes remain inside this service.
    Message generation itself remains pure.
    """

    if not followup_id or not followup_id.strip():
        raise ValueError(
            "followup_id is required."
        )

    followup_id = followup_id.strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        # =====================================================
        # LOCK FOLLOW-UP
        # =====================================================

        cur.execute(
            """
            SELECT
                followup_id,
                lead_id,
                attempt_number,
                status,
                outreach_id
            FROM followups
            WHERE followup_id = %s
            FOR UPDATE;
            """,
            (followup_id,),
        )

        row = cur.fetchone()

        if not row:
            return {
                "status": "not_found",
                "followup_id": followup_id,
            }

        (
            db_followup_id,
            lead_id,
            attempt_number,
            followup_status,
            existing_outreach_id,
        ) = row

        # =====================================================
        # ALREADY PROCESSED
        # =====================================================

        if existing_outreach_id is not None:
            return {
                "status": "already_processed",
                "followup_id": str(
                    db_followup_id
                ),
                "outreach_id": str(
                    existing_outreach_id
                ),
            }

        # =====================================================
        # STATUS VALIDATION
        # =====================================================

        if followup_status != FOLLOWUP_STATUS_SCHEDULED:
            return {
                "status": "invalid_status",
                "followup_id": str(
                    db_followup_id
                ),
                "followup_status": followup_status,
            }

        # =====================================================
        # RETRIEVE COMPLETE CONTEXT
        #
        # Context retrieval is read-only and separate
        # from generation.
        # =====================================================

        context = get_followup_context(
            followup_id=str(db_followup_id)
        )

        if not context.get("found"):
            return {
                "status": "context_not_found",
                "followup_id": str(
                    db_followup_id
                ),
                "reason": context.get(
                    "reason",
                    "context_not_found",
                ),
            }

        contact = context.get("contact")

        if not contact:
            return {
                "status": "missing_contact",
                "followup_id": str(
                    db_followup_id
                ),
            }

        previous_outreach = context.get(
            "previous_outreach"
        )

        if not previous_outreach:
            return {
                "status": "missing_previous_outreach",
                "followup_id": str(
                    db_followup_id
                ),
            }

        contact_id = contact.get("contact_id")

        if not contact_id:
            return {
                "status": "missing_contact",
                "followup_id": str(
                    db_followup_id
                ),
            }

        # =====================================================
        # GENERATE CONTEXT-AWARE MESSAGE
        # =====================================================

        message_text = generate_followup_message(
            context
        )

        if not message_text or not message_text.strip():
            raise ValueError(
                "Generated follow-up message is empty."
            )

        message_text = message_text.strip()

        # =====================================================
        # CREATE DRAFT OUTREACH
        # =====================================================

        cur.execute(
            """
            INSERT INTO outreach (
                lead_id,
                contact_id,
                channel,
                message_text,
                status
            )
            VALUES (
                %s,
                %s,
                'email',
                %s,
                'drafted'
            )
            RETURNING outreach_id;
            """,
            (
                lead_id,
                contact_id,
                message_text,
            ),
        )

        new_outreach_id = cur.fetchone()[0]

        # =====================================================
        # LINK FOLLOW-UP → OUTREACH
        # =====================================================

        cur.execute(
            """
            UPDATE followups
            SET outreach_id = %s
            WHERE followup_id = %s
              AND outreach_id IS NULL;
            """,
            (
                new_outreach_id,
                db_followup_id,
            ),
        )

        if cur.rowcount != 1:
            conn.rollback()

            return {
                "status": "link_conflict",
                "followup_id": str(
                    db_followup_id
                ),
            }

        # =====================================================
        # COMMIT
        # =====================================================

        conn.commit()

        return {
            "status": "drafted",
            "followup_id": str(
                db_followup_id
            ),
            "lead_id": str(lead_id),
            "outreach_id": str(
                new_outreach_id
            ),
            "attempt_number": attempt_number,
            "contact_id": str(contact_id),
            "message_text": message_text,
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
