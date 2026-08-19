"""
Email Retry Queue.

Phase 3.3:
    - Schedule failed email processing for retry.
    - Fetch retryable emails whose scheduled time has arrived.
    - Mark retries as processing/completed/exhausted.
    - Keep retry queue database operations separate from pipeline logic.
"""

from datetime import datetime, timezone

from db import get_connection


VALID_STATUSES = {
    "scheduled",
    "retrying",
    "completed",
    "exhausted",
}


def schedule_retry(
    external_message_id: str,
    agent_name: str,
    error_message: str,
    attempt_number: int = 1,
    max_attempts: int = 3,
    scheduled_for: datetime | None = None,
):
    """
    Create a retry entry for a failed email.
    """

    if not external_message_id or not external_message_id.strip():
        raise ValueError("external_message_id is required.")

    if not agent_name or not agent_name.strip():
        raise ValueError("agent_name is required.")

    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1.")

    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1.")

    if attempt_number > max_attempts:
        raise ValueError(
            "attempt_number cannot exceed max_attempts."
        )

    if scheduled_for is None:
        scheduled_for = datetime.now(timezone.utc)

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO email_retry_queue (
                external_message_id,
                agent_name,
                attempt_number,
                max_attempts,
                scheduled_for,
                status,
                last_error
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                'scheduled',
                %s
            )
            RETURNING retry_id;
            """,
            (
                external_message_id.strip(),
                agent_name.strip(),
                attempt_number,
                max_attempts,
                scheduled_for,
                error_message,
            ),
        )

        retry_id = cur.fetchone()[0]

        conn.commit()

        return retry_id

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def get_due_retries(limit: int = 10):
    """
    Atomically claim retries that are ready to be processed.

    PostgreSQL row locking with SKIP LOCKED prevents concurrent
    workers from claiming the same retry.
    """

    if limit < 1:
        raise ValueError("limit must be >= 1.")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            WITH due_retries AS (
                SELECT retry_id
                FROM email_retry_queue
                WHERE status = 'scheduled'
                  AND scheduled_for <= NOW()
                ORDER BY scheduled_for
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE email_retry_queue AS q
            SET
                status = 'retrying',
                updated_at = NOW()
            FROM due_retries AS d
            WHERE q.retry_id = d.retry_id
            RETURNING
                q.retry_id,
                q.external_message_id,
                q.agent_name,
                q.attempt_number,
                q.max_attempts,
                q.scheduled_for,
                q.status,
                q.last_error;
            """,
            (limit,),
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

def mark_retrying(retry_id: str):
    """
    Mark a scheduled retry as currently being processed.
    """

    return _update_retry_status(
        retry_id,
        "retrying",
    )


def mark_completed(retry_id: str):
    """
    Mark a retry as successfully completed.
    """

    return _update_retry_status(
        retry_id,
        "completed",
    )


def mark_exhausted(
    retry_id: str,
    error_message: str | None = None,
):
    """
    Mark a retry as permanently exhausted.
    """

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE email_retry_queue
            SET
                status = 'exhausted',
                last_error = %s,
                updated_at = NOW()
            WHERE retry_id = %s
            RETURNING retry_id;
            """,
            (
                error_message,
                retry_id,
            ),
        )

        row = cur.fetchone()

        if not row:
            raise ValueError(
                f"Retry not found: {retry_id}"
            )

        conn.commit()

        return row[0]

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


def _update_retry_status(
    retry_id: str,
    status: str,
):
    """
    Update retry status.
    """

    if status not in VALID_STATUSES:
        raise ValueError(
            f"Unsupported retry status: {status}"
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE email_retry_queue
            SET
                status = %s::email_retry_status,
                updated_at = NOW()
            WHERE retry_id = %s
            RETURNING retry_id;
            """,
            (
                status,
                retry_id,
            ),
        )

        row = cur.fetchone()

        if not row:
            raise ValueError(
                f"Retry not found: {retry_id}"
            )

        conn.commit()

        return row[0]

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

def schedule_next_retry(
    retry_id: str,
    error_message: str,
    scheduled_for: datetime,
):
    """
    Move a retry to its next scheduled attempt.

    The current attempt is incremented by one.
    The retry remains scheduled until the worker processes it again.
    """

    if not retry_id or not retry_id.strip():
        raise ValueError("retry_id is required.")

    if not error_message:
        error_message = ""

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE email_retry_queue
            SET
                attempt_number = attempt_number + 1,
                scheduled_for = %s,
                status = 'scheduled',
                last_error = %s,
                updated_at = NOW()
            WHERE retry_id = %s
              AND status = 'retrying'
              AND attempt_number < max_attempts
            RETURNING
                retry_id,
                attempt_number,
                max_attempts,
                status;
            """,
            (
                scheduled_for,
                error_message,
                retry_id,
            ),
        )

        row = cur.fetchone()

        if not row:
            raise ValueError(
                f"Retry cannot be rescheduled: {retry_id}"
            )

        conn.commit()

        return row

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
