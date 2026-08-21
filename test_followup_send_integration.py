from datetime import datetime, timezone
from unittest.mock import patch

import send_agent
from db import get_connection


conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
outreach_id = None
followup_id = None

try:
    # =========================================================
    # BRAND
    # =========================================================

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.4.3.6 Send Integration Brand',
            'phase 5.4.3.6 send integration brand'
        )
        RETURNING brand_id;
        """
    )

    brand_id = cur.fetchone()[0]

    # =========================================================
    # CONTACT
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
            'Send Integration Contact',
            'phase5436@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )

    contact_id = cur.fetchone()[0]

    # =========================================================
    # LEAD
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
    # APPROVED FOLLOW-UP OUTREACH
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
            'Phase 5.4.3.6 follow-up test message',
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

    print("TEST FIXTURE CREATED:")
    print("OUTREACH:", outreach_id)
    print("FOLLOWUP:", followup_id)

    # =========================================================
    # MOCK SMTP
    # IMPORTANT: run() MUST be INSIDE this block.
    # =========================================================

    with patch("send_agent.send_email") as mock_send:

        mock_send.return_value = None

        send_agent.run(
            dry_run=False
        )

        print()
        print(
            "SMTP CALL COUNT:",
            mock_send.call_count,
        )

        assert mock_send.call_count >= 1

        test_call_found = any(
            len(call.args) >= 1
            and str(call.args[0]) == "phase5436@example.invalid"
            for call in mock_send.call_args_list
        )

        assert test_call_found

        print(
            "CASE 1 - TEST OUTREACH SMTP CALLED: PASS"
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
    print("SEND INTEGRATION STATE:")
    print(state)

    assert state is not None

    outreach_status = state[0]
    last_sent_at = state[1]
    followup_status = state[2]

    assert outreach_status == "sent"
    print(
        "CASE 2 - OUTREACH MARKED SENT: PASS"
    )

    assert last_sent_at is not None
    print(
        "CASE 3 - LAST_SENT_AT SET: PASS"
    )

    assert followup_status == "sent"
    print(
        "CASE 4 - FOLLOW-UP MARKED SENT: PASS"
    )

    # =========================================================
    # CONVERSATION
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
        "CASE 5 - CONVERSATION CREATED: PASS"
    )

    # =========================================================
    # OUTBOUND MESSAGE
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
        "CASE 6 - OUTBOUND MESSAGE CREATED: PASS"
    )

    print()
    print(
        "PHASE 5.4.3.6 SEND INTEGRATION TEST PASSED"
    )

finally:
    # =========================================================
    # CLEAN MESSAGES
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

    # =========================================================
    # CLEAN CONVERSATIONS
    # =========================================================

    if outreach_id is not None:
        cur.execute(
            """
            DELETE FROM conversations
            WHERE outreach_id = %s;
            """,
            (outreach_id,),
        )

    # =========================================================
    # CLEAN FOLLOW-UP
    # =========================================================

    if followup_id is not None:
        cur.execute(
            """
            DELETE FROM followups
            WHERE followup_id = %s;
            """,
            (followup_id,),
        )

    # =========================================================
    # CLEAN OUTREACH
    # =========================================================

    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM outreach
            WHERE lead_id = %s;
            """,
            (lead_id,),
        )

    # =========================================================
    # CLEAN LEAD
    # =========================================================

    if lead_id is not None:
        cur.execute(
            """
            DELETE FROM leads
            WHERE lead_id = %s;
            """,
            (lead_id,),
        )

    # =========================================================
    # CLEAN CONTACT
    # =========================================================

    if contact_id is not None:
        cur.execute(
            """
            DELETE FROM contacts
            WHERE contact_id = %s;
            """,
            (contact_id,),
        )

    # =========================================================
    # CLEAN BRAND
    # =========================================================

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
