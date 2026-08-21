"""
Follow-up Context Retrieval.

Phase 5.5.1:
    - Retrieve complete context for a scheduled follow-up.
    - Keep context retrieval separate from message generation.
    - Use latest sent outreach as the authoritative previous outreach.
    - Include conversation and message history when available.
    - Read-only database operation.
"""

from db import get_connection


def get_followup_context(followup_id: str):
    """
    Retrieve all relevant context for one follow-up.

    Returns:
        dict containing:
            followup
            lead
            brand
            contact
            previous_outreach
            previous_followups
            conversation
            messages
    """

    if not followup_id or not followup_id.strip():
        raise ValueError("followup_id is required.")

    followup_id = followup_id.strip()

    conn = get_connection()
    cur = conn.cursor()

    try:
        # =====================================================
        # FOLLOW-UP + LEAD + BRAND
        # =====================================================

        cur.execute(
            """
            SELECT
                f.followup_id,
                f.lead_id,
                f.attempt_number,
                f.status,
                f.scheduled_for,
                f.outreach_id,

                l.status,
                l.brand_id,

                b.name

            FROM followups f

            JOIN leads l
                ON l.lead_id = f.lead_id

            JOIN brands b
                ON b.brand_id = l.brand_id

            WHERE f.followup_id = %s
            LIMIT 1;
            """,
            (followup_id,),
        )

        row = cur.fetchone()

        if not row:
            return {
                "found": False,
                "reason": "followup_not_found",
                "followup_id": followup_id,
            }

        (
            db_followup_id,
            lead_id,
            attempt_number,
            followup_status,
            scheduled_for,
            linked_outreach_id,
            lead_status,
            brand_id,
            brand_name,
        ) = row

        # =====================================================
        # CONTACT
        # =====================================================

        cur.execute(
            """
            SELECT
                c.contact_id,
                c.name,
                c.email
            FROM contacts c
            JOIN outreach o
                ON o.contact_id = c.contact_id
            WHERE o.lead_id = %s
            ORDER BY
                CASE
                    WHEN o.status = 'sent' THEN 0
                    ELSE 1
                END,
                o.last_sent_at DESC NULLS LAST,
                o.created_at DESC
            LIMIT 1;
            """,
            (lead_id,),
        )

        contact_row = cur.fetchone()

        contact = None

        if contact_row:
            contact = {
                "contact_id": str(contact_row[0]),
                "name": contact_row[1],
                "email": contact_row[2],
            }

        # =====================================================
        # LATEST SENT OUTREACH
        # =====================================================

        cur.execute(
            """
            SELECT
                o.outreach_id,
                o.contact_id,
                o.channel,
                o.message_text,
                o.status,
                o.last_sent_at,
                o.created_at
            FROM outreach o
            WHERE o.lead_id = %s
              AND o.status = 'sent'
            ORDER BY
                o.last_sent_at DESC NULLS LAST,
                o.created_at DESC
            LIMIT 1;
            """,
            (lead_id,),
        )

        previous_outreach_row = cur.fetchone()

        previous_outreach = None

        if previous_outreach_row:
            previous_outreach = {
                "outreach_id": str(previous_outreach_row[0]),
                "contact_id": (
                    str(previous_outreach_row[1])
                    if previous_outreach_row[1]
                    else None
                ),
                "channel": previous_outreach_row[2],
                "message_text": previous_outreach_row[3],
                "status": previous_outreach_row[4],
                "last_sent_at": previous_outreach_row[5],
                "created_at": previous_outreach_row[6],
            }

        # =====================================================
        # PREVIOUS FOLLOW-UPS
        # =====================================================

        cur.execute(
            """
            SELECT
                f.followup_id,
                f.attempt_number,
                f.status,
                f.scheduled_for,
                f.outreach_id,
                o.message_text,
                o.status,
                o.last_sent_at
            FROM followups f
            LEFT JOIN outreach o
                ON o.outreach_id = f.outreach_id
            WHERE f.lead_id = %s
              AND f.followup_id <> %s
            ORDER BY
                f.attempt_number ASC,
                f.created_at ASC;
            """,
            (
                lead_id,
                db_followup_id,
            ),
        )

        previous_followups = []

        for followup_row in cur.fetchall():
            previous_followups.append(
                {
                    "followup_id": str(followup_row[0]),
                    "attempt_number": followup_row[1],
                    "status": followup_row[2],
                    "scheduled_for": followup_row[3],
                    "outreach_id": (
                        str(followup_row[4])
                        if followup_row[4]
                        else None
                    ),
                    "message_text": followup_row[5],
                    "outreach_status": followup_row[6],
                    "last_sent_at": followup_row[7],
                }
            )

        # =====================================================
        # CONVERSATION FOR AUTHORITATIVE OUTREACH
        # =====================================================

        conversation = None
        messages = []

        if previous_outreach:
            cur.execute(
                """
                SELECT
                    conversation_id,
                    outreach_id,
                    classification,
                    created_at,
                    updated_at
                FROM conversations
                WHERE outreach_id = %s
                ORDER BY created_at
                LIMIT 1;
                """,
                (previous_outreach["outreach_id"],),
            )

            conversation_row = cur.fetchone()

            if conversation_row:
                conversation = {
                    "conversation_id": str(
                        conversation_row[0]
                    ),
                    "outreach_id": str(
                        conversation_row[1]
                    ),
                    "classification": conversation_row[2],
                    "created_at": conversation_row[3],
                    "updated_at": conversation_row[4],
                }

                # =================================================
                # MESSAGE HISTORY
                # =================================================

                cur.execute(
                    """
                    SELECT
                        message_id,
                        direction,
                        body,
                        sent_at,
                        external_message_id
                    FROM messages
                    WHERE conversation_id = %s
                    ORDER BY sent_at ASC, message_id ASC;
                    """,
                    (conversation["conversation_id"],),
                )

                for message_row in cur.fetchall():
                    messages.append(
                        {
                            "message_id": str(
                                message_row[0]
                            ),
                            "direction": message_row[1],
                            "body": message_row[2],
                            "sent_at": message_row[3],
                            "external_message_id": (
                                message_row[4]
                            ),
                        }
                    )

        # =====================================================
        # FINAL CONTEXT
        # =====================================================

        return {
            "found": True,
            "followup": {
                "followup_id": str(db_followup_id),
                "lead_id": str(lead_id),
                "attempt_number": attempt_number,
                "status": followup_status,
                "scheduled_for": scheduled_for,
                "outreach_id": (
                    str(linked_outreach_id)
                    if linked_outreach_id
                    else None
                ),
            },
            "lead": {
                "lead_id": str(lead_id),
                "status": lead_status,
                "brand_id": str(brand_id),
            },
            "brand": {
                "brand_id": str(brand_id),
                "name": brand_name,
            },
            "contact": contact,
            "previous_outreach": previous_outreach,
            "previous_followups": previous_followups,
            "conversation": conversation,
            "messages": messages,
        }

    finally:
        cur.close()
        conn.close()
