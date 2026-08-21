"""
Follow-up Due Transition Service.

Phase 5.3.4:
    - Identify leads whose latest outreach is old enough for follow-up.
    - Do not transition leads when the latest outreach has an inbound reply.
    - Preserve protected lifecycle states.
    - Use the latest sent outreach as the authoritative outreach.
"""

from datetime import datetime, timedelta, timezone

from db import get_connection


DEFAULT_FOLLOWUP_WAIT_DAYS = 3


def transition_due_leads(
    wait_days: int = DEFAULT_FOLLOWUP_WAIT_DAYS,
    now: datetime | None = None,
):
    """
    Transition sent leads to follow_up_due when:

        1. Their latest sent outreach is older than wait_days.
        2. That latest outreach has no inbound reply.
        3. The lead is still in sent status.

    Protected lifecycle states are therefore not overwritten.
    """

    if wait_days < 1:
        raise ValueError(
            "wait_days must be >= 1."
        )

    if now is None:
        now = datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware."
        )

    cutoff = now - timedelta(days=wait_days)

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            WITH latest_sent AS (
                SELECT DISTINCT ON (o.lead_id)
                    o.lead_id,
                    o.outreach_id,
                    o.last_sent_at
                FROM outreach o
                WHERE o.status = 'sent'
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
            )

            UPDATE leads l
            SET
                status = 'follow_up_due',
                updated_at = NOW()
            FROM latest_sent ls
            WHERE l.lead_id = ls.lead_id
              AND l.status = 'sent'
              AND ls.last_sent_at <= %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM replied_latest rr
                  WHERE rr.lead_id = l.lead_id
              )
            RETURNING
                l.lead_id,
                l.status;
            """,
            (cutoff,),
        )

        rows = cur.fetchall()

        conn.commit()

        return rows

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
