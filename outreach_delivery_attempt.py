"""
Outreach Delivery Attempt Tracking.

Phase 5.7.3:
    - Create one immutable delivery-attempt identity.
    - Record SMTP start.
    - Record SMTP success.
    - Record finalization.
    - Record failure.
    - Keep attempt history independent from outreach transaction state.
"""

from datetime import datetime, timezone

from db import get_connection


def _now():
    return datetime.now(timezone.utc)


def create_delivery_attempt(
    outreach_id: str,
    attempt_number: int,
):
    """
    Create a delivery attempt and commit it independently.

    This record must survive a later rollback in the
    outreach transaction.
    """

    if attempt_number < 1:
        raise ValueError(
            "attempt_number must be >= 1."
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO outreach_delivery_attempts (
                outreach_id,
                attempt_number,
                status,
                smtp_started_at
            )
            VALUES (
                %s,
                %s,
                'started',
                %s
            )
            RETURNING attempt_id;
            """,
            (
                outreach_id,
                attempt_number,
                _now(),
            ),
        )

        attempt_id = cur.fetchone()[0]

        conn.commit()

        return attempt_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def mark_smtp_succeeded(
    attempt_id: str,
):
    """
    Record successful SMTP delivery.

    This update is committed independently so SMTP success
    remains visible even if later database finalization fails.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE outreach_delivery_attempts
            SET
                status = 'smtp_succeeded',
                smtp_succeeded_at = %s
            WHERE attempt_id = %s
              AND status = 'started'
            RETURNING attempt_id;
            """,
            (
                _now(),
                attempt_id,
            ),
        )

        row = cur.fetchone()

        if row is None:
            raise RuntimeError(
                "Delivery attempt was not marked "
                "smtp_succeeded."
            )

        conn.commit()

        return row[0]

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def mark_finalized(
    attempt_id: str,
):
    """
    Record successful database finalization.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE outreach_delivery_attempts
            SET
                status = 'finalized',
                finalized_at = %s
            WHERE attempt_id = %s
              AND status = 'smtp_succeeded'
            RETURNING attempt_id;
            """,
            (
                _now(),
                attempt_id,
            ),
        )

        row = cur.fetchone()

        if row is None:
            raise RuntimeError(
                "Delivery attempt was not finalized."
            )

        conn.commit()

        return row[0]

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def mark_failed(
    attempt_id: str,
    error: str,
):
    """
    Record delivery-attempt failure.

    Important:
        - If SMTP has NOT succeeded yet, mark the attempt failed.
        - If SMTP already succeeded, preserve smtp_succeeded
          because the external delivery event actually happened.
        - In both cases preserve the error for diagnostics.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE outreach_delivery_attempts
            SET
                status = CASE
                    WHEN status = 'smtp_succeeded'
                        THEN 'smtp_succeeded'::outreach_delivery_attempt_status
                    WHEN status = 'finalized'
                        THEN 'finalized'::outreach_delivery_attempt_status
                    ELSE
                        'failed'::outreach_delivery_attempt_status
                END,
                last_error = %s
            WHERE attempt_id = %s
            RETURNING
                attempt_id,
                status;
            """,
            (
                str(error),
                attempt_id,
            ),
        )

        row = cur.fetchone()

        if row is None:
            raise RuntimeError(
                "Delivery attempt failure state "
                "could not be recorded."
            )

        conn.commit()

        return row

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

def get_next_attempt_number(
    outreach_id: str,
):
    """
    Return the next delivery-attempt number for an outreach.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT COALESCE(
                MAX(attempt_number),
                0
            ) + 1
            FROM outreach_delivery_attempts
            WHERE outreach_id = %s;
            """,
            (outreach_id,),
        )

        return cur.fetchone()[0]

    finally:
        cur.close()
        conn.close()