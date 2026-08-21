from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup

from psycopg2.errors import UniqueViolation


BRAND_NAME = "Phase 5.2.5 Idempotency Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
followup_id = None

try:
    # 1. Create test brand.
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

    # 2. Create test lead.
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

    # 3. First follow-up.
    first = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=scheduled_for,
        attempt_number=1,
    )

    followup_id = first[0]

    print("FIRST FOLLOW-UP CREATED:")
    print(first)

    # 4. Attempt duplicate active follow-up.
    try:
        schedule_followup(
            lead_id=str(lead_id),
            scheduled_for=scheduled_for,
            attempt_number=1,
        )

        raise AssertionError(
            "Duplicate scheduled follow-up was not rejected."
        )

    except UniqueViolation as error:
        print()
        print("DUPLICATE REJECTED:")
        print(type(error).__name__)
        print(str(error).splitlines()[0])

    # 5. Verify only one active attempt exists.
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
    print("DATABASE VERIFICATION:")
    print(count)

    assert count == 1

    # 6. Attempt 2 should still be allowed.
    second = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=scheduled_for,
        attempt_number=2,
    )

    print()
    print("SECOND ATTEMPT CREATED:")
    print(second)

    print()
    print("PHASE 5.2.5 FOLLOW-UP IDEMPOTENCY TEST PASSED")

finally:
    # Delete all follow-ups for this test lead.
    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE lead_id = %s;
            """,
            (lead_id,),
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
