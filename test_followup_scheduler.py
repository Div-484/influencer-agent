from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup


BRAND_NAME = "Phase 5.2 Scheduler Test Brand"
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

    # Commit fixture data because schedule_followup() uses a separate database connection.
    conn.commit()

    # 3. Schedule follow-up 3 days in the future.
    scheduled_for = (
        datetime.now(timezone.utc)
        + timedelta(days=3)
    )

    result = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=scheduled_for,
        attempt_number=1,
    )

    followup_id = result[0]

    print("SCHEDULED FOLLOW-UP:")
    print(result)

    # 4. Verify database state.
    cur.execute(
        """
        SELECT
            followup_id,
            lead_id,
            scheduled_for,
            attempt_number,
            status
        FROM followups
        WHERE followup_id = %s;
        """,
        (followup_id,),
    )

    row = cur.fetchone()

    print()
    print("DATABASE VERIFICATION:")
    print(row)

    assert row is not None
    assert row[0] == followup_id
    assert row[1] == lead_id
    assert row[3] == 1
    assert row[4] == "scheduled"

    print()
    print("PHASE 5.2.2 SCHEDULING TEST PASSED")

finally:
    # Cleanup follow-up first.
    if followup_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = %s;
            """,
            (followup_id,),
        )

    # Then lead.
    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (lead_id,),
        )

    # Then brand.
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
