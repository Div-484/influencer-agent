from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup


BRAND_NAME = "Phase 5.2.4 Duplicate Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
followup_ids = []

try:
    # Create fixture.
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
            brand_id
        )
        VALUES (%s)
        RETURNING lead_id;
        """,
        (brand_id,),
    )

    lead_id = cur.fetchone()[0]

    conn.commit()

    scheduled_for = (
        datetime.now(timezone.utc)
        + timedelta(days=3)
    )

    # First scheduling.
    first = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=scheduled_for,
        attempt_number=1,
    )

    followup_ids.append(first[0])

    print("FIRST FOLLOW-UP CREATED:")
    print(first)

    # Second scheduling with the same lead + attempt.
    duplicate = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=scheduled_for,
        attempt_number=1,
    )

    followup_ids.append(duplicate[0])

    print()
    print("DUPLICATE FOLLOW-UP CREATED:")
    print(duplicate)

    # Current schema is expected to allow this.
    # This proves why database-level protection is needed.
    assert first[0] != duplicate[0]

    cur.execute(
        """
        SELECT
            COUNT(*)
        FROM followups
        WHERE lead_id = %s
          AND attempt_number = 1;
        """,
        (lead_id,),
    )

    count = cur.fetchone()[0]

    print()
    print("DATABASE DUPLICATE COUNT:")
    print(count)

    assert count == 2

    print()
    print(
        "PHASE 5.2.4 DUPLICATE GAP CONFIRMED"
    )

finally:
    if followup_ids:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = ANY(%s::uuid[]);
            """,
            (followup_ids,),
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
