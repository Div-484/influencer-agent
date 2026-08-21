from unittest.mock import patch

from db import get_connection
import send_agent


conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
outreach_id = None
followup_id = None

try:
    # =========================================================
    # TEST BRAND
    # =========================================================

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.4.3.7 Failure Brand',
            'phase 5.4.3.7 failure brand'
        )
        RETURNING brand_id;
        """
    )

    brand_id = cur.fetchone()[0]

    # =========================================================
    # TEST CONTACT
    # =========================================================

    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (
            %s,
            'Failure Test Contact',
            'phase5437@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )

    contact_id = cur.fetchone()[0]

    # =========================================================
    # TEST LEAD
    # =========================================================

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

    # =========================================================
    # APPROVED OUTREACH
    # =========================================================

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            contact_id,
            channel,
            message_text,
            status,
            approved_by
        )
        VALUES (
            %s,
            %s,
            'email',
            'Phase 5.4.3.7 failure-path test message',
            'approved',
            'Phase5-Test-Reviewer'
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            contact_id,
        ),
    )

    outreach_id = cur.fetchone()[0]

    # =========================================================
    # LINKED FOLLOW-UP
    # =========================================================

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

    print("TEST FIXTURE CREATED")
    print("OUTREACH:", outreach_id)
    print("FOLLOWUP:", followup_id)

    # =========================================================
    # SIMULATE SMTP FAILURE
    # =========================================================

    with patch(
        "send_agent.send_email"
    ) as mock_send:

        mock_send.side_effect = RuntimeError(
            "SIMULATED SMTP FAILURE"
        )

        send_agent.run(
            dry_run=False
        )

        print()
        print(
            "SMTP CALL COUNT:",
            mock_send.call_count,
        )

        assert mock_send.call_count == 1

        print(
            "CASE 1 - SMTP FAILURE TRIGGERED: PASS"
        )

    # =========================================================
    # DATABASE VERIFICATION
    # =========================================================

    cur.execute(
        """
        SELECT
            o.status,
            o.last_sent_at,
            f.status
        FROM outreach o
        JOIN followups f
            ON f.outreach_id = o.outreach_id
        WHERE o.outreach_id = %s;
        """,
        (outreach_id,),
    )

    state = cur.fetchone()

    print()
    print("FAILURE STATE:")
    print(state)

    assert state is not None

    outreach_status = state[0]
    last_sent_at = state[1]
    followup_status = state[2]

    # Outreach must remain approved.
    assert outreach_status == "approved"

    print(
        "CASE 2 - OUTREACH REMAINS APPROVED: PASS"
    )

    # Failed send must not set last_sent_at.
    assert last_sent_at is None

    print(
        "CASE 3 - LAST_SENT_AT REMAINS NULL: PASS"
    )

    # Follow-up must remain scheduled.
    assert followup_status == "scheduled"

    print(
        "CASE 4 - FOLLOW-UP REMAINS SCHEDULED: PASS"
    )

    # =========================================================
    # CONVERSATION MUST NOT EXIST
    # =========================================================

    cur.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    conversation_count = cur.fetchone()[0]

    print()
    print(
        "CONVERSATION COUNT:",
        conversation_count,
    )

    assert conversation_count == 0

    print(
        "CASE 5 - NO CONVERSATION CREATED: PASS"
    )

    print()
    print(
        "PHASE 5.4.3.7 FAILURE-PATH TEST PASSED"
    )

finally:
    # =========================================================
    # CLEANUP
    # =========================================================

    if outreach_id is not None:
        cur.execute(
            """
            DELETE FROM messages
            WHERE conversation_id IN (
                SELECT conversation_id
                FROM conversations
                WHERE outreach_id = %s
            );
            """,
            (outreach_id,),
        )

        cur.execute(
            """
            DELETE FROM conversations
            WHERE outreach_id = %s;
            """,
            (outreach_id,),
        )

    if followup_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = %s;
            """,
            (followup_id,),
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
