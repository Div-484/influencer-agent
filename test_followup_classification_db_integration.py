from db import get_connection
from followup_context import get_followup_context
from followup_agent import generate_followup_message


conn = get_connection()
cur = conn.cursor()

brand_id = None
lead_id = None
contact_id = None
outreach_id = None
conversation_id = None
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
            'Phase 5.5.6 DB Classification Brand',
            'phase 5.5.6 db classification brand'
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
            'DB Classification Contact',
            'phase556@example.invalid'
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
    # ORIGINAL SENT OUTREACH
    # =========================================================

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
            'Original collaboration proposal.',
            'sent',
            'Phase5-Test',
            NOW() - INTERVAL '5 days'
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
    # CONVERSATION
    # =========================================================

    cur.execute(
        """
        INSERT INTO conversations (
            outreach_id,
            classification
        )
        VALUES (
            %s,
            'interested'
        )
        RETURNING conversation_id;
        """,
        (outreach_id,),
    )

    conversation_id = cur.fetchone()[0]

    # =========================================================
    # OUTBOUND MESSAGE
    # =========================================================

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
            'Original collaboration proposal.',
            NOW() - INTERVAL '5 days'
        );
        """,
        (conversation_id,),
    )

    # =========================================================
    # INBOUND REPLY
    # =========================================================

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
            'Yes, I am interested. Please share the next steps.',
            NOW() - INTERVAL '4 days'
        );
        """,
        (conversation_id,),
    )

    # =========================================================
    # FOLLOW-UP
    # =========================================================

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
            1,
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
    print("OUTREACH:", outreach_id)
    print("CONVERSATION:", conversation_id)
    print("FOLLOWUP:", followup_id)

    # =========================================================
    # CONTEXT RETRIEVAL
    # =========================================================

    print()
    print("===== DB CONTEXT RETRIEVAL =====")

    context = get_followup_context(
        followup_id=str(followup_id)
    )

    assert context["found"] is True

    print("FOUND:", context["found"])

    # =========================================================
    # CASE 1 - CLASSIFICATION
    # =========================================================

    classification = (
        context["conversation"]["classification"]
    )

    print()
    print("CLASSIFICATION:", classification)

    assert classification == "interested"

    print(
        "CASE 1 - DB CLASSIFICATION RETRIEVED: PASS"
    )

    # =========================================================
    # CASE 2 - MESSAGE HISTORY
    # =========================================================

    messages = context["messages"]

    print()
    print("MESSAGE COUNT:", len(messages))

    assert len(messages) == 2

    assert any(
        message["direction"] == "inbound"
        and "interested" in message["body"]
        for message in messages
    )

    print(
        "CASE 2 - INBOUND MESSAGE RETRIEVED: PASS"
    )

    # =========================================================
    # GENERATION
    # =========================================================

    print()
    print("===== GENERATION FROM DB CONTEXT =====")

    generated = generate_followup_message(
        context
    )

    print(generated)

    assert "Thanks for your interest" in generated
    assert "next step" in generated

    print(
        "CASE 3 - CLASSIFICATION-AWARE GENERATION: PASS"
    )

    # =========================================================
    # CASE 4 - NO PERSISTENCE
    # =========================================================

    cur.execute(
        """
        SELECT COUNT(*)
        FROM outreach
        WHERE lead_id = %s;
        """,
        (lead_id,),
    )

    outreach_count = cur.fetchone()[0]

    print()
    print("OUTREACH COUNT:", outreach_count)

    assert outreach_count == 1

    print(
        "CASE 4 - GENERATOR DID NOT PERSIST OUTREACH: PASS"
    )

    print()
    print(
        "PHASE 5.5.6 DB CLASSIFICATION INTEGRATION TEST PASSED"
    )

finally:

    # =========================================================
    # CLEANUP
    # =========================================================

    try:
        conn.rollback()

        if followup_id:
            cur.execute(
                """
                DELETE FROM followups
                WHERE followup_id = %s;
                """,
                (followup_id,),
            )

        if conversation_id:
            cur.execute(
                """
                DELETE FROM conversations
                WHERE conversation_id = %s;
                """,
                (conversation_id,),
            )

        if outreach_id:
            cur.execute(
                """
                DELETE FROM outreach
                WHERE outreach_id = %s;
                """,
                (outreach_id,),
            )

        if lead_id:
            cur.execute(
                """
                DELETE FROM leads
                WHERE lead_id = %s;
                """,
                (lead_id,),
            )

        if contact_id:
            cur.execute(
                """
                DELETE FROM contacts
                WHERE contact_id = %s;
                """,
                (contact_id,),
            )

        if brand_id:
            cur.execute(
                """
                DELETE FROM brands
                WHERE brand_id = %s;
                """,
                (brand_id,),
            )

        conn.commit()

        print()
        print("CLEANUP: PASS")

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()