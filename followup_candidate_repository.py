"""
Follow-up Candidate Repository.

Phase 5.4.1:
    - Retrieve leads eligible for follow-up execution.
    - Use the latest sent email outreach.
    - Exclude leads that already have an active follow-up.
    - Exclude leads with inbound replies on the latest outreach.
    - Keep database retrieval separate from scheduling/execution logic.
"""

from db import get_connection


ACTIVE_FOLLOWUP_STATUSES = {
    "scheduled",
}


def get_followup_candidates(limit: int = 10):
    """
    Return leads that are currently eligible for follow-up execution.

    Candidate requirements:

        - lead status = follow_up_due
        - latest sent email outreach exists
        - latest outreach has no inbound reply
        - no active scheduled follow-up exists
    """

    if limit < 1:
        raise ValueError("limit must be >= 1.")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            WITH latest_sent AS (
                SELECT DISTINCT ON (o.lead_id)
                    o.lead_id,
                    o.outreach_id,
                    o.contact_id,
                    o.message_text,
                    o.last_sent_at
                FROM outreach o
                WHERE o.status = 'sent'
                  AND o.channel = 'email'
                  AND o.last_sent_at IS NOT NULL
                ORDER BY
                    o.lead_id,
                    o.last_sent_at DESC
            ),

            replied_latest AS (
                SELECT DISTINCT
                    ls.lead_id
                FROM latest_sent ls
                JOIN conversations c
                    ON c.outreach_id = ls.outreach_id
                JOIN messages m
                    ON m.conversation_id = c.conversation_id
                WHERE m.direction = 'inbound'
            ),

            active_followups AS (
                SELECT DISTINCT
                    f.lead_id
                FROM followups f
                WHERE f.status = 'scheduled'
            )

            SELECT
                l.lead_id,
                l.brand_id,
                l.status AS lead_status,
                ls.outreach_id,
                ls.contact_id,
                ls.message_text,
                ls.last_sent_at
            FROM leads l
            JOIN latest_sent ls
                ON ls.lead_id = l.lead_id
            LEFT JOIN replied_latest rr
                ON rr.lead_id = l.lead_id
            LEFT JOIN active_followups af
                ON af.lead_id = l.lead_id
            WHERE l.status = 'follow_up_due'
              AND rr.lead_id IS NULL
              AND af.lead_id IS NULL
            ORDER BY
                ls.last_sent_at ASC
            LIMIT %s;
            """,
            (limit,),
        )

        return cur.fetchall()

    finally:
        cur.close()
        conn.close()
