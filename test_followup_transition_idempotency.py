from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_due_transition import transition_due_leads


BRAND_NAME = "Phase 5.3.4.4 Idempotency Test Brand"
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
    # CREATE FIXTURE
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
        (
            BRAND_NAME,
            NORMALIZED_NAME,
        ),
    )

    brand_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO leads (
            brand_id,
            status
        )
        VALUES (
            %s,
            'sent'
        )
        RETURNING lead_id;
        """,
        (brand_id,),
    )

    lead_id = cur.fetchone()[0]

    old_sent_time = TEST_NOW - timedelta(days=5)

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
            'Phase 5.3.4.4 idempotency test',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            old_sent_time,
        ),
    )

    outreach_id = cur.fetchone()[0]

    conn.commit()

    # ---------------------------------------------------------
    # FIRST RUN
    # ---------------------------------------------------------

    first_result = transition_due_leads(
        wait_days=3,
        now=TEST_NOW,
    )

    print("FIRST TRANSITION:")
    print(first_result)

    assert len(first_result) == 1
    assert str(first_result[0][0]) == str(lead_id)
    assert first_result[0][1] == "follow_up_due"

    # ---------------------------------------------------------
    # SECOND RUN
    # ---------------------------------------------------------

    second_result = transition_due_leads(
        wait_days=3,
        now=TEST_NOW,
    )

    print()
    print("SECOND TRANSITION:")
    print(second_result)

    assert second_result == []

    # ---------------------------------------------------------
    # THIRD RUN
    # ---------------------------------------------------------

    third_result = transition_due_leads(
        wait_days=3,
        now=TEST_NOW,
    )

    print()
    print("THIRD TRANSITION:")
    print(third_result)

    assert third_result == []

    # ---------------------------------------------------------
    # DATABASE VERIFICATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT
            status
        FROM leads
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    final_status = cur.fetchone()[0]

    print()
    print("FINAL LEAD STATUS:")
    print(final_status)

    assert final_status == "follow_up_due"

    print()
    print("PHASE 5.3.4.4 TRANSITION IDEMPOTENCY TEST PASSED")

finally:
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
