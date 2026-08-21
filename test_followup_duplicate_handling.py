from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup


BRAND_NAME = "Phase 5.4.2.2 Duplicate Handling Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()

NOW = datetime.now(timezone.utc)
SCHEDULED_FOR = NOW + timedelta(days=3)

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
outreach_id = None
followup_id = None

try:
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
            'Duplicate handling test',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            NOW - timedelta(days=5),
        ),
    )

    outreach_id = cur.fetchone()[0]

    conn.commit()

    first = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=SCHEDULED_FOR,
        attempt_number=1,
    )

    followup_id = first[0]

    print("FIRST SCHEDULE:")
    print(first)

    try:
        schedule_followup(
            lead_id=str(lead_id),
            scheduled_for=SCHEDULED_FOR,
            attempt_number=1,
        )

        raise AssertionError(
            "Duplicate scheduling was not rejected."
        )

    except RuntimeError as error:
        print()
        print("SECOND SCHEDULE:")
        print(type(error).__name__)
        print(str(error))

        assert "already scheduled" in str(
            error
        ).lower()

    cur.execute(
        """
        SELECT COUNT(*)
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
        "PHASE 5.4.2.2 DUPLICATE HANDLING TEST PASSED"
    )

finally:
    cur.execute(
        """
        DELETE FROM followups
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    if outreach_id:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE outreach_id = %s;
            """,
            (outreach_id,),
        )

    if lead_id:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (lead_id,),
        )

    if brand_id:
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
