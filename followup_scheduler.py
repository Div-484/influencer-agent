"""
Follow-up Scheduling Service.

Phase 5.2 / 5.4.2.2:
    - Schedule follow-ups for eligible leads.
    - Validate follow-up attempt numbers.
    - Handle duplicate active scheduling idempotently.
    - Preserve database-level uniqueness protection.
"""

from datetime import datetime

import psycopg2

from db import get_connection


DEFAULT_FOLLOWUP_DELAY_DAYS = 3
MAX_FOLLOWUP_ATTEMPTS = 2

ACTIVE_ATTEMPT_CONSTRAINT = (
    "idx_followups_active_attempt"
)


def schedule_followup(
    lead_id: str,
    scheduled_for: datetime,
    attempt_number: int = 1,
):
    """
    Schedule one follow-up for a lead.

    Returns:
        Database row when created.

    Raises:
        ValueError for invalid input.
        RuntimeError for a duplicate active follow-up.
        Original database exception for unrelated failures.
    """

    if not lead_id or not lead_id.strip():
        raise ValueError("lead_id is required.")

    if not isinstance(scheduled_for, datetime):
        raise ValueError(
            "scheduled_for must be a datetime."
        )

    if scheduled_for.tzinfo is None:
        raise ValueError(
            "scheduled_for must be timezone-aware."
        )

    if attempt_number < 1:
        raise ValueError(
            "attempt_number must be >= 1."
        )

    if attempt_number > MAX_FOLLOWUP_ATTEMPTS:
        raise ValueError(
            "attempt_number exceeds maximum follow-up attempts."
        )

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO followups (
                lead_id,
                scheduled_for,
                attempt_number,
                status
            )
            VALUES (
                %s,
                %s,
                %s,
                'scheduled'
            )
            RETURNING
                followup_id,
                lead_id,
                scheduled_for,
                attempt_number,
                status;
            """,
            (
                lead_id.strip(),
                scheduled_for,
                attempt_number,
            ),
        )

        row = cur.fetchone()

        conn.commit()

        return row

    except psycopg2.errors.UniqueViolation as error:
        conn.rollback()

        constraint_name = getattr(
            error.diag,
            "constraint_name",
            None,
        )

        if constraint_name == ACTIVE_ATTEMPT_CONSTRAINT:
            raise RuntimeError(
                "follow-up already scheduled for "
                f"lead_id={lead_id.strip()}, "
                f"attempt_number={attempt_number}."
            ) from error

        raise

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()
