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
            'Phase 5.4.3.8 Retry Safety Brand',
            'phase 5.4.3.8 retry safety brand'
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
            'Retry Safety Contact',
            'phase5438@example.invalid'
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
            'Phase 5.4.3.8 retry safety test message',
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
    # ATTEMPT 1 — INTENTIONAL FAILURE
    # =========================================================

    print()
    print("===== ATTEMPT 1: SIMULATED FAILURE =====")

    with patch(
        "send_agent.send_email"
    ) as mock_send:

        mock_send.side_effect = RuntimeError(
            "SIMULATED RETRY FAILURE"
        )

        send_agent.run(
            dry_run=False
        )

        print(
            "SMTP CALL COUNT:",
            mock_send.call_count,
        )

        assert mock_send.call_count == 1

        print(
            "CASE 1 - FIRST SEND FAILED: PASS"
        )

    # Verify failure state.

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

    first_state = cur.fetchone()

    print()
    print("STATE AFTER FAILED ATTEMPT:")
    print(first_state)

    assert first_state is not None
    assert first_state[0] == "approved"
    assert first_state[1] is None
    assert first_state[2] == "scheduled"

    print(
        "CASE 2 - FAILED STATE PRESERVED: PASS"
    )

    # =========================================================
    # ATTEMPT 2 — SUCCESSFUL RETRY
    # =========================================================

    print()
    print("===== ATTEMPT 2: SUCCESSFUL RETRY =====")

    with patch(
        "send_agent.send_email"
    ) as mock_send:

        mock_send.return_value = None

        send_agent.run(
            dry_run=False
        )

        print(
            "SMTP CALL COUNT:",
            mock_send.call_count,
        )

        assert mock_send.call_count == 1

        print(
            "CASE 3 - RETRY SMTP CALLED ONCE: PASS"
        )

    # =========================================================
    # VERIFY SUCCESSFUL RETRY
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

    success_state = cur.fetchone()

    print()
    print("STATE AFTER SUCCESSFUL RETRY:")
    print(success_state)

    assert success_state is not None

    assert success_state[0] == "sent"

    print(
        "CASE 4 - OUTREACH MARKED SENT: PASS"
    )

    assert success_state[1] is not None

    print(
        "CASE 5 - LAST_SENT_AT SET: PASS"
    )

    assert success_state[2] == "sent"

    print(
        "CASE 6 - FOLLOW-UP MARKED SENT: PASS"
    )

    # =========================================================
    # CONVERSATION COUNT
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

    assert conversation_count == 1

    print(
        "CASE 7 - ONE CONVERSATION CREATED: PASS"
    )

    # =========================================================
    # OUTBOUND MESSAGE COUNT
    # =========================================================

    cur.execute(
        """
        SELECT COUNT(*)
        FROM messages m
        JOIN conversations c
            ON c.conversation_id = m.conversation_id
        WHERE c.outreach_id = %s
          AND m.direction = 'outbound';
        """,
        (outreach_id,),
    )

    message_count = cur.fetchone()[0]

    print()
    print(
        "OUTBOUND MESSAGE COUNT:",
        message_count,
    )

    assert message_count == 1

    print(
        "CASE 8 - ONE OUTBOUND MESSAGE CREATED: PASS"
    )

    # =========================================================
    # ATTEMPT 3 — SHOULD NOT RESEND
    # =========================================================

    print()
    print("===== ATTEMPT 3: ALREADY SENT =====")

    with patch(
        "send_agent.send_email"
    ) as mock_send:

        mock_send.return_value = None

        send_agent.run(
            dry_run=False
        )

        print(
            "SMTP CALL COUNT:",
            mock_send.call_count,
        )

        assert mock_send.call_count == 0

        print(
            "CASE 9 - NO DUPLICATE SMTP SEND: PASS"
        )

    # =========================================================
    # FINAL DUPLICATE VERIFICATION
    # =========================================================

    cur.execute(
        """
        SELECT COUNT(*)
        FROM conversations
        WHERE outreach_id = %s;
        """,
        (outreach_id,),
    )

    final_conversation_count = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM messages m
        JOIN conversations c
            ON c.conversation_id = m.conversation_id
        WHERE c.outreach_id = %s
          AND m.direction = 'outbound';
        """,
        (outreach_id,),
    )

    final_message_count = cur.fetchone()[0]

    print()
    print("FINAL COUNTS:")
    print(
        "CONVERSATIONS:",
        final_conversation_count,
    )
    print(
        "OUTBOUND MESSAGES:",
        final_message_count,
    )

    assert final_conversation_count == 1
    assert final_message_count == 1

    print(
        "CASE 10 - NO DUPLICATE CONVERSATION/MESSAGE: PASS"
    )

    print()
    print(
        "PHASE 5.4.3.8 RETRY SAFETY TEST PASSED"
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
