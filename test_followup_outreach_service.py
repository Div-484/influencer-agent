from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_scheduler import schedule_followup
from followup_outreach_service import create_followup_outreach


NOW = datetime.now(timezone.utc)

brand_id = None
lead_id = None
contact_id = None
outreach_id = None
followup_id = None

conn = get_connection()
cur = conn.cursor()

try:
    # BRAND
    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.4.3.3 Test Brand',
            'phase 5.4.3.3 test brand'
        )
        RETURNING brand_id;
        """
    )
    brand_id = cur.fetchone()[0]

    # CONTACT
    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (
            %s,
            'Test Contact',
            'phase5433@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )
    contact_id = cur.fetchone()[0]

    # LEAD
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

    # PREVIOUS SENT OUTREACH
    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            contact_id,
            channel,
            message_text,
            status,
            last_sent_at
        )
        VALUES (
            %s,
            %s,
            'email',
            'Original collaboration message',
            'sent',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            contact_id,
            NOW - timedelta(days=5),
        ),
    )
    outreach_id = cur.fetchone()[0]

    conn.commit()

    # SCHEDULE FOLLOW-UP
    followup = schedule_followup(
        lead_id=str(lead_id),
        scheduled_for=NOW - timedelta(minutes=1),
        attempt_number=1,
    )

    followup_id = followup[0]

    print("SCHEDULED FOLLOW-UP:")
    print(followup)

    # CREATE FOLLOW-UP OUTREACH
    result = create_followup_outreach(
        followup_id=str(followup_id),
    )

    print()
    print("FOLLOW-UP OUTREACH RESULT:")
    print(result)

    assert result["status"] == "drafted"

    new_outreach_id = result["outreach_id"]

    # DATABASE VERIFICATION
    cur.execute(
        """
        SELECT
            f.followup_id,
            f.outreach_id,
            f.status,
            o.status,
            o.channel,
            o.message_text
        FROM followups f
        JOIN outreach o
            ON o.outreach_id = f.outreach_id
        WHERE f.followup_id = %s;
        """,
        (followup_id,),
    )

    row = cur.fetchone()

    print()
    print("DATABASE VERIFICATION:")
    print(row)

    assert row is not None
    assert str(row[0]) == str(followup_id)
    assert str(row[1]) == str(new_outreach_id)
    assert row[2] == "scheduled"
    assert row[3] == "drafted"
    assert row[4] == "email"

    # IDEMPOTENCY
    second = create_followup_outreach(
        followup_id=str(followup_id),
    )

    print()
    print("SECOND EXECUTION:")
    print(second)

    assert second["status"] == "already_processed"
    assert second["outreach_id"] == str(new_outreach_id)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM outreach
        WHERE lead_id = %s
          AND message_text LIKE 'Hi Test%%';
        """,
        (lead_id,),
    )

    count = cur.fetchone()[0]

    print()
    print("FOLLOW-UP OUTREACH COUNT:")
    print(count)

    assert count == 1

    print()
    print(
        "PHASE 5.4.3.3 FOLLOW-UP OUTREACH "
        "DRAFT TEST PASSED"
    )

finally:
    if followup_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = %s;
            """,
            (followup_id,),
        )

    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM outreach
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

    if contact_id is not None:
        cur.execute(
            """
            DELETE FROM contacts
            WHERE contact_id = %s;
            """,
            (contact_id,),
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
