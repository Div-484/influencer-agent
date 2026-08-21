from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_due_transition import transition_due_leads


BRAND_NAME = "Phase 5.3.4 Transition Test Brand V2"
NORMALIZED_NAME = BRAND_NAME.lower().strip()

TEST_NOW = datetime(
    2026,
    8,
    13,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)

conn = get_connection()
cur = conn.cursor()

brand_id = None
old_lead_id = None
recent_lead_id = None
protected_lead_id = None

try:
    # ---------------------------------------------------------
    # FIXTURE BRAND
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
    # OLD SENT LEAD
    # ---------------------------------------------------------

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

    old_lead_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # RECENT SENT LEAD
    # ---------------------------------------------------------

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

    recent_lead_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # PROTECTED LEAD
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO leads (
            brand_id,
            status
        )
        VALUES (
            %s,
            'interested'
        )
        RETURNING lead_id;
        """,
        (brand_id,),
    )

    protected_lead_id = cur.fetchone()[0]

    conn.commit()

    # ---------------------------------------------------------
    # OLD OUTREACH
    # Latest initially = 5 days old
    # ---------------------------------------------------------

    old_time = TEST_NOW - timedelta(days=5)

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
            'Old outreach',
            'sent',
            %s
        );
        """,
        (
            old_lead_id,
            old_time,
        ),
    )

    # ---------------------------------------------------------
    # RECENT OUTREACH
    # ---------------------------------------------------------

    recent_time = TEST_NOW - timedelta(hours=12)

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
            'Recent outreach',
            'sent',
            %s
        );
        """,
        (
            recent_lead_id,
            recent_time,
        ),
    )

    # ---------------------------------------------------------
    # PROTECTED LEAD HAS OLD OUTREACH
    # ---------------------------------------------------------

    protected_time = TEST_NOW - timedelta(days=10)

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
            'Protected outreach',
            'sent',
            %s
        );
        """,
        (
            protected_lead_id,
            protected_time,
        ),
    )

    # ---------------------------------------------------------
    # OLD LEAD: ADD NEWER OUTREACH
    #
    # Latest should now be 1 day old.
    # Therefore it must NOT transition.
    # ---------------------------------------------------------

    newer_time = TEST_NOW - timedelta(days=1)

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
            'Newer outreach',
            'sent',
            %s
        );
        """,
        (
            old_lead_id,
            newer_time,
        ),
    )

    conn.commit()

    # ---------------------------------------------------------
    # TEST 1
    #
    # Latest old_lead outreach = 1 day old
    # wait = 3 days
    # Expected: no transition
    # ---------------------------------------------------------

    result = transition_due_leads(
        wait_days=3,
        now=TEST_NOW,
    )

    print("TEST 1 RESULT:")
    print(result)

    transitioned_ids = {
        str(row[0])
        for row in result
    }

    assert str(old_lead_id) not in transitioned_ids
    assert str(recent_lead_id) not in transitioned_ids
    assert str(protected_lead_id) not in transitioned_ids

    print("TEST 1 PASSED")

    # ---------------------------------------------------------
    # Verify statuses remain unchanged
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (old_lead_id,),
    )

    assert cur.fetchone()[0] == "sent"

    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (recent_lead_id,),
    )

    assert cur.fetchone()[0] == "sent"

    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (protected_lead_id,),
    )

    assert cur.fetchone()[0] == "interested"

    # ---------------------------------------------------------
    # TEST 2
    #
    # Now create a genuinely latest old outreach.
    # Delete the newer 1-day-old outreach first.
    # Then insert a 5-day-old latest outreach.
    # ---------------------------------------------------------

    cur.execute(
        """
        DELETE FROM outreach
        WHERE lead_id = %s
          AND message_text = 'Newer outreach';
        """,
        (old_lead_id,),
    )

    latest_old_time = TEST_NOW - timedelta(days=5)

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
            'Latest expired outreach',
            'sent',
            %s
        );
        """,
        (
            old_lead_id,
            latest_old_time,
        ),
    )

    conn.commit()

    # ---------------------------------------------------------
    # TEST 2 EXECUTION
    # ---------------------------------------------------------

    result = transition_due_leads(
        wait_days=3,
        now=TEST_NOW,
    )

    print()
    print("TEST 2 RESULT:")
    print(result)

    transitioned_ids = {
        str(row[0])
        for row in result
    }

    assert str(old_lead_id) in transitioned_ids

    # ---------------------------------------------------------
    # Verify final state
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT status
        FROM leads
        WHERE lead_id = %s;
        """,
        (old_lead_id,),
    )

    final_status = cur.fetchone()[0]

    print()
    print("OLD LEAD FINAL STATUS:")
    print(final_status)

    assert final_status == "follow_up_due"

    print()
    print("PHASE 5.3.4.2 TRANSITION TEST PASSED")

finally:
    # Delete outreach first.
    if old_lead_id is not None:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE lead_id = %s;
            """,
            (old_lead_id,),
        )

    if recent_lead_id is not None:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE lead_id = %s;
            """,
            (recent_lead_id,),
        )

    if protected_lead_id is not None:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE lead_id = %s;
            """,
            (protected_lead_id,),
        )

    if old_lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (old_lead_id,),
        )

    if recent_lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (recent_lead_id,),
        )

    if protected_lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (protected_lead_id,),
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
