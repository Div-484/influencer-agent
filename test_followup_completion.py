from db import get_connection
from followup_completion import mark_followup_sent_for_outreach


conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
outreach_id = None
followup_id = None

try:
    # ---------------------------------------------------------
    # BRAND
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.4.3.5 Completion Test Brand',
            'phase 5.4.3.5 completion test brand'
        )
        RETURNING brand_id;
        """
    )

    brand_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # CONTACT
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (
            %s,
            'Completion Test Contact',
            'phase5435@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )

    contact_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # LEAD
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
    # OUTREACH = SENT
    # ---------------------------------------------------------

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
            'Completed follow-up test message',
            'sent',
            NOW()
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            contact_id,
        ),
    )

    outreach_id = cur.fetchone()[0]

    # ---------------------------------------------------------
    # FOLLOWUP = SCHEDULED
    # ---------------------------------------------------------

    cur.execute(
        """
        INSERT INTO followups (
            lead_id,
            scheduled_for,
            attempt_number,
            status,
            outreach_id
        )
        VALUES (
            %s,
            NOW(),
            1,
            'scheduled',
            %s
        )
        RETURNING followup_id;
        """,
        (
            lead_id,
            outreach_id,
        ),
    )

    followup_id = cur.fetchone()[0]

    conn.commit()

    # ---------------------------------------------------------
    # MARK FOLLOW-UP SENT
    # ---------------------------------------------------------

    result = mark_followup_sent_for_outreach(
        outreach_id=str(outreach_id),
    )

    print("COMPLETION RESULT:")
    print(result)

    assert result["status"] == "sent"
    assert result["followup_id"] == str(
        followup_id
    )
    assert result["outreach_id"] == str(
        outreach_id
    )

    # ---------------------------------------------------------
    # DATABASE VERIFICATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT
            f.followup_id,
            f.outreach_id,
            f.status,
            o.status
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
    assert row[2] == "sent"
    assert row[3] == "sent"

    # ---------------------------------------------------------
    # IDEMPOTENCY
    # ---------------------------------------------------------

    second = mark_followup_sent_for_outreach(
        outreach_id=str(outreach_id),
    )

    print()
    print("SECOND COMPLETION:")
    print(second)

    assert second["status"] == "not_updated"

    # ---------------------------------------------------------
    # NEGATIVE CASE
    # ---------------------------------------------------------

    cur.execute(
        """
        UPDATE followups
        SET status = 'scheduled'
        WHERE followup_id = %s;
        """,
        (followup_id,),
    )

    cur.execute(
        """
        UPDATE outreach
        SET status = 'approved',
            last_sent_at = NULL
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    conn.commit()

    failed_state = mark_followup_sent_for_outreach(
        outreach_id=str(outreach_id),
    )

    print()
    print("OUTREACH NOT SENT RESULT:")
    print(failed_state)

    assert failed_state["status"] == "not_updated"

    cur.execute(
        """
        SELECT status
        FROM followups
        WHERE followup_id = %s;
        """,
        (followup_id,),
    )

    final_status = cur.fetchone()[0]

    print()
    print("FOLLOW-UP STATUS AFTER UNSENT OUTREACH:")
    print(final_status)

    assert final_status == "scheduled"

    print()
    print(
        "PHASE 5.4.3.5 FOLLOW-UP COMPLETION TEST PASSED"
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
