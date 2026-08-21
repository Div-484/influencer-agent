"""
Follow-up Completion Service.

Phase 5.4.3.5:
    - Mark a follow-up as sent after its linked outreach
      has been successfully sent.
    - Never mark a follow-up sent before outreach success.
    - Support both standalone usage and same-transaction usage
      from the Send Agent.
"""

from db import get_connection


def mark_followup_sent_for_outreach(
    outreach_id: str,
    cur=None,
):
    """
    Mark the linked follow-up as sent.

    When `cur` is provided, the caller's existing database
    transaction is used. This is required when outreach.status
    was changed to 'sent' but has not yet been committed.

    When `cur` is not provided, this function creates and manages
    its own database connection for standalone usage.
    """

    if not outreach_id or not outreach_id.strip():
        raise ValueError(
            "outreach_id is required."
        )

    outreach_id = outreach_id.strip()

    own_connection = cur is None

    if own_connection:
        conn = get_connection()
        cur = conn.cursor()
    else:
        conn = None

    try:
        cur.execute(
            """
            UPDATE followups f
            SET status = 'sent'
            FROM outreach o
            WHERE f.outreach_id = o.outreach_id
              AND o.outreach_id = %s
              AND o.status = 'sent'
              AND f.status = 'scheduled'
            RETURNING
                f.followup_id,
                f.outreach_id,
                f.status;
            """,
            (outreach_id,),
        )

        row = cur.fetchone()

        if own_connection:
            conn.commit()

        if row is None:
            return {
                "status": "not_updated",
                "outreach_id": outreach_id,
            }

        return {
            "status": "sent",
            "followup_id": str(row[0]),
            "outreach_id": str(row[1]),
            "followup_status": row[2],
        }

    except Exception:
        if own_connection:
            conn.rollback()
        raise

    finally:
        if own_connection:
            cur.close()
            conn.close()
