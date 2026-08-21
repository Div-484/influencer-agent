from db import get_connection

conn = get_connection()
cur = conn.cursor()

try:
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_followups_active_attempt
        ON followups (lead_id, attempt_number)
        WHERE status = 'scheduled';
        """
    )

    conn.commit()

    print("FOLLOW-UP IDEMPOTENCY INDEX CREATED")

finally:
    cur.close()
    conn.close()
