from datetime import datetime, timezone, timedelta

from db import get_connection
from followup_scheduler import schedule_followup


BRAND_NAME = "Phase 5.2.3 Validation Test Brand"
NORMALIZED_NAME = BRAND_NAME.lower().strip()


def expect_value_error(label, fn):
    try:
        fn()
    except ValueError as error:
        print(f"{label}: PASS -> {error}")
        return

    raise AssertionError(
        f"{label}: expected ValueError"
    )


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

    future_time = (
        datetime.now(timezone.utc)
        + timedelta(days=3)
    )

    # 1. Empty lead ID.
    expect_value_error(
        "EMPTY LEAD ID",
        lambda: schedule_followup(
            lead_id="",
            scheduled_for=future_time,
            attempt_number=1,
        ),
    )

    # 2. scheduled_for is not datetime.
    expect_value_error(
        "INVALID SCHEDULED_FOR TYPE",
        lambda: schedule_followup(
            lead_id=str(lead_id),
            scheduled_for="tomorrow",
            attempt_number=1,
        ),
    )

    # 3. Naive datetime.
    naive_time = datetime.now()

    expect_value_error(
        "NAIVE DATETIME",
        lambda: schedule_followup(
            lead_id=str(lead_id),
            scheduled_for=naive_time,
            attempt_number=1,
        ),
    )

    # 4. Attempt number zero.
    expect_value_error(
        "ATTEMPT NUMBER ZERO",
        lambda: schedule_followup(
            lead_id=str(lead_id),
            scheduled_for=future_time,
            attempt_number=0,
        ),
    )

    # 5. Attempt number above configured maximum.
    expect_value_error(
        "ATTEMPT NUMBER ABOVE MAX",
        lambda: schedule_followup(
            lead_id=str(lead_id),
            scheduled_for=future_time,
            attempt_number=3,
        ),
    )

    # 6. Valid attempt 1.
    result_1 = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=future_time,
        attempt_number=1,
    )

    followup_ids.append(result_1[0])

    print("VALID ATTEMPT 1: PASS")
    print(result_1)

    # 7. Valid attempt 2.
    result_2 = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=future_time,
        attempt_number=2,
    )

    followup_ids.append(result_2[0])

    print("VALID ATTEMPT 2: PASS")
    print(result_2)

    print()
    print("PHASE 5.2.3 VALIDATION TEST PASSED")

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
