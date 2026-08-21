from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_orchestrator import schedule_followup_candidates


BRAND_NAME = "Phase 5.4.2.3 Orchestrator Idempotency Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()

TEST_NOW = datetime(
    2026,
    8,
    20,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
outreach_id = None

try:
    # ---------------------------------------------------------
    # FIXTURE
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (%s, %s)
        RETURNING brand_id;
        """,
        (BRAND_NAME, NORMALIZED_NAME),
    )

    brand_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO leads (
            brand_id,
            status
        )
        VALUES (%s, 'follow_up_due')
        RETURNING lead_id;
        """,
        (brand_id,),
    )

    lead_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            channel,
            message_text,
            status,
            last_sent_at
        )
        VALUES (
            %s,
            'email',
            'Orchestrator idempotency test',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            TEST_NOW - timedelta(days=5),
        ),
    )

    outreach_id = cur.fetchone()[0]

    conn.commit()

    # ---------------------------------------------------------
    # FIRST RUN
    # ---------------------------------------------------------

    first = schedule_followup_candidates(
        limit=10,
        delay_days=3,
        attempt_number=1,
        now=TEST_NOW,
    )

    print("FIRST RUN:")
    print(first)

    first_match = [
        item
        for item in first
        if item["lead_id"] == str(lead_id)
    ]

    assert len(first_match) == 1
    assert first_match[0]["status"] == "scheduled"

    # ---------------------------------------------------------
    # SECOND RUN
    # ---------------------------------------------------------

    second = schedule_followup_candidates(
        limit=10,
        delay_days=3,
        attempt_number=1,
        now=TEST_NOW,
    )

    print()
    print("SECOND RUN:")
    print(second)

    second_match = [
        item
        for item in second
        if item["lead_id"] == str(lead_id)
    ]

    # Candidate repository should exclude it because an
    # active follow-up now exists.
    assert second_match == []

    # ---------------------------------------------------------
    # DATABASE VERIFICATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT
            COUNT(*)
        FROM followups
        WHERE lead_id = %s
          AND attempt_number = 1
          AND status = 'scheduled';
        """,
        (lead_id,),
    )

    count = cur.fetchone()[0]

    print()
    print("ACTIVE FOLLOW-UP COUNT:")
    print(count)

    assert count == 1

    print()
    print(
        "PHASE 5.4.2.3 ORCHESTRATOR IDEMPOTENCY TEST PASSED"
    )

finally:
    cur.execute(
        """
        DELETE FROM followups
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    if outreach_id is not None:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE outreach_id = %s;
            """,
            (outreach_id,),
        )

    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (lead_id,),
        )

    if brand_id is not None:
        cur.execute(
            """
            DELETE FROM brands
            WHERE brand_id = %s;
            """,
            (brand_id,),
        )

    conn.commit()

    cur.close()
    conn.close()
