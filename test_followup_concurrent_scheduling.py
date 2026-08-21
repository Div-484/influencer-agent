from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup


BRAND_NAME = "Phase 5.4.2.1 Concurrent Scheduling Test Brand"
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

SCHEDULED_FOR = TEST_NOW + timedelta(days=3)

conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
outreach_id = None
created_followup_ids = []

try:
    # ---------------------------------------------------------
    # CREATE TEST BRAND
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

    # ---------------------------------------------------------
    # CREATE FOLLOW-UP-DUE LEAD
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO leads (
            brand_id,
            status
        )
        VALUES (
            %s,
            'follow_up_due'
        )
        RETURNING lead_id;
        """,
        (brand_id,),
    )

    lead_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # CREATE OUTREACH
    # ---------------------------------------------------------

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
            'Concurrent scheduling test',
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

finally:
    cur.close()
    conn.close()


# -------------------------------------------------------------
# WORKER
# -------------------------------------------------------------

def worker(worker_name):
    try:
        result = schedule_followup(
            lead_id=str(lead_id),
            scheduled_for=SCHEDULED_FOR,
            attempt_number=1,
        )

        return {
            "worker": worker_name,
            "status": "created",
            "followup_id": str(result[0]),
        }

    except Exception as error:
        return {
            "worker": worker_name,
            "status": "duplicate_or_error",
            "error_type": type(error).__name__,
            "error": str(error),
        }


# -------------------------------------------------------------
# CONCURRENT EXECUTION
# -------------------------------------------------------------

results = []

with ThreadPoolExecutor(max_workers=2) as executor:

    futures = [
        executor.submit(
            worker,
            "worker_1",
        ),
        executor.submit(
            worker,
            "worker_2",
        ),
    ]

    for future in as_completed(futures):
        results.append(
            future.result()
        )


print("===== CONCURRENT RESULTS =====")

for result in results:
    print(result)


# -------------------------------------------------------------
# DATABASE VERIFICATION
# -------------------------------------------------------------

conn = get_connection()
cur = conn.cursor()

try:
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

    scheduled_count = cur.fetchone()[0]

    print()
    print("ACTIVE FOLLOW-UP COUNT:")
    print(scheduled_count)

    # Exactly one active follow-up must exist.
    assert scheduled_count == 1

    cur.execute(
        """
        SELECT
            followup_id,
            lead_id,
            attempt_number,
            status,
            scheduled_for
        FROM followups
        WHERE lead_id = %s
        ORDER BY created_at;
        """,
        (lead_id,),
    )

    rows = cur.fetchall()

    print()
    print("DATABASE ROWS:")

    for row in rows:
        print(row)

    # Exactly one row should exist.
    assert len(rows) == 1

    assert rows[0][2] == 1
    assert rows[0][3] == "scheduled"

    created_count = sum(
        1
        for result in results
        if result["status"] == "created"
    )

    duplicate_or_error_count = sum(
        1
        for result in results
        if result["status"] == "duplicate_or_error"
    )

    print()
    print("CREATED COUNT:")
    print(created_count)

    print("DUPLICATE / ERROR COUNT:")
    print(duplicate_or_error_count)

    # Exactly one worker may create the record.
    assert created_count == 1

    # The other worker must encounter the DB uniqueness protection.
    assert duplicate_or_error_count == 1

    print()
    print(
        "PHASE 5.4.2.1 CONCURRENT SCHEDULING "
        "IDEMPOTENCY TEST PASSED"
    )

finally:
    # ---------------------------------------------------------
    # CLEANUP
    # ---------------------------------------------------------

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
