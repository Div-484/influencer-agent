from datetime import datetime, timedelta, timezone

from db import get_connection
from followup_context import get_followup_context


conn = get_connection()
cur = conn.cursor()

brand_id = None
contact_id = None
lead_id = None
original_outreach_id = None
conversation_id = None
followup_id = None

try:
    # =====================================================
    # BRAND
    # =====================================================

    cur.execute(
        """
        INSERT INTO brands (
            name,
            normalized_name
        )
        VALUES (
            'Phase 5.5.1 Context Test Brand',
            'phase 5.5.1 context test brand'
        )
        RETURNING brand_id;
        """
    )

    brand_id = cur.fetchone()[0]

    # =====================================================
    # CONTACT
    # =====================================================

    cur.execute(
        """
        INSERT INTO contacts (
            brand_id,
            name,
            email
        )
        VALUES (
            %s,
            'Context Test Contact',
            'phase551@example.invalid'
        )
        RETURNING contact_id;
        """,
        (brand_id,),
    )

    contact_id = cur.fetchone()[0]

    # =====================================================
    # LEAD
    # =====================================================

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

    # =====================================================
    # ORIGINAL SENT OUTREACH
    # =====================================================

    sent_at = datetime.now(timezone.utc) - timedelta(days=4)

    cur.execute(
        """
        INSERT INTO outreach (
            lead_id,
            contact_id,
            channel,
            message_text,
            status,
            approved_by,
            last_sent_at
        )
        VALUES (
            %s,
            %s,
            'email',
            'Hi Context, would you be interested in discussing a collaboration?',
            'sent',
            'Phase5-Test-Reviewer',
            %s
        )
        RETURNING outreach_id;
        """,
        (
            lead_id,
            contact_id,
            sent_at,
        ),
    )

    original_outreach_id = cur.fetchone()[0]

    # =====================================================
    # CONVERSATION
    # =====================================================

    cur.execute(
        """
        INSERT INTO conversations (
            outreach_id
        )
        VALUES (
            %s
        )
        RETURNING conversation_id;
        """,
        (original_outreach_id,),
    )

    conversation_id = cur.fetchone()[0]

    # =====================================================
    # ORIGINAL OUTBOUND MESSAGE
    #
    # Use only columns already proven by send_agent.py.
    # =====================================================

    cur.execute(
        """
        INSERT INTO messages (
            conversation_id,
            direction,
            body,
            sent_at
        )
        VALUES (
            %s,
            'outbound',
            %s,
            %s
        )
        RETURNING message_id;
        """,
        (
            conversation_id,
            'Hi Context, would you be interested in discussing a collaboration?',
            sent_at,
        ),
    )

    # =====================================================
    # INBOUND REPLY
    # =====================================================

    reply_at = sent_at + timedelta(days=1)

    cur.execute(
        """
        INSERT INTO messages (
            conversation_id,
            direction,
            body,
            sent_at
        )
        VALUES (
            %s,
            'inbound',
            %s,
            %s
        )
        RETURNING message_id;
        """,
        (
            conversation_id,
            'Yes, please send me more details about the collaboration.',
            reply_at,
        ),
    )

    # =====================================================
    # PREVIOUS FOLLOW-UP
    # =====================================================

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
            'sent',
            %s
        )
        RETURNING followup_id;
        """,
        (
            lead_id,
            original_outreach_id,
        ),
    )

    # =====================================================
    # CURRENT FOLLOW-UP
    # =====================================================

    cur.execute(
        """
        INSERT INTO followups (
            lead_id,
            scheduled_for,
            attempt_number,
            status
        )
        VALUES (
            %s,
            NOW(),
            2,
            'scheduled'
        )
        RETURNING followup_id;
        """,
        (lead_id,),
    )

    followup_id = cur.fetchone()[0]

    conn.commit()

    print("===== FIXTURE CREATED =====")
    print("BRAND:", brand_id)
    print("LEAD:", lead_id)
    print("ORIGINAL OUTREACH:", original_outreach_id)
    print("CONVERSATION:", conversation_id)
    print("CURRENT FOLLOWUP:", followup_id)

finally:
    cur.close()
    conn.close()


# =========================================================
# CONTEXT RETRIEVAL
# =========================================================

context = get_followup_context(
    str(followup_id)
)

try:
    print()
    print("===== CONTEXT RESULT =====")

    print("FOUND:", context["found"])

    assert context["found"] is True

    assert (
        context["followup"]["followup_id"]
        == str(followup_id)
    )

    assert (
        context["lead"]["lead_id"]
        == str(lead_id)
    )

    assert (
        context["brand"]["brand_id"]
        == str(brand_id)
    )

    assert context["contact"] is not None

    assert context["previous_outreach"] is not None

    assert (
        context["previous_outreach"]["outreach_id"]
        == str(original_outreach_id)
    )

    assert len(context["previous_followups"]) == 1

    assert context["conversation"] is not None

    assert (
        context["conversation"]["conversation_id"]
        == str(conversation_id)
    )

    assert len(context["messages"]) == 2

    directions = [
        message["direction"]
        for message in context["messages"]
    ]

    assert "outbound" in directions
    assert "inbound" in directions

    print()
    print("FOLLOW-UP:")
    print(context["followup"])

    print()
    print("BRAND:")
    print(context["brand"])

    print()
    print("CONTACT:")
    print(context["contact"])

    print()
    print("PREVIOUS OUTREACH:")
    print(context["previous_outreach"])

    print()
    print("PREVIOUS FOLLOW-UPS:")
    print(context["previous_followups"])

    print()
    print("CONVERSATION:")
    print(context["conversation"])

    print()
    print("MESSAGES:")

    for message in context["messages"]:
        print(message)

    print()
    print("CASE 1 - FOLLOW-UP CONTEXT FOUND: PASS")
    print("CASE 2 - LEAD CONTEXT FOUND: PASS")
    print("CASE 3 - BRAND CONTEXT FOUND: PASS")
    print("CASE 4 - CONTACT CONTEXT FOUND: PASS")
    print("CASE 5 - PREVIOUS OUTREACH FOUND: PASS")
    print("CASE 6 - PREVIOUS FOLLOW-UP FOUND: PASS")
    print("CASE 7 - CONVERSATION FOUND: PASS")
    print("CASE 8 - MESSAGE HISTORY FOUND: PASS")
    print()
    print("PHASE 5.5.1 CONTEXT RETRIEVAL TEST PASSED")

finally:
    cleanup_conn = get_connection()
    cleanup_cur = cleanup_conn.cursor()
    try:
        cleanup_cur.execute(
            """
            DELETE FROM brands
            WHERE normalized_name = 'phase 5.5.1 context test brand';
            """
        )
        cleanup_conn.commit()
        print()
        print("CLEANUP: test fixture deleted")
    finally:
        cleanup_cur.close()
        cleanup_conn.close()
